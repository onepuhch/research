"""S0-A: a partial extract (some requests met a temporary model outage, others were answered
and stored today) succeeds as 'partial', so verified risk alerts are not held back; everything
else that fails still blocks them. No network, no delivery."""
import contextlib
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest import mock
from urllib.error import HTTPError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common as c  # noqa: E402
import daily_run_state as d  # noqa: E402
import extract  # noqa: E402
import notify  # noqa: E402
import test_candidate_alerts as ta  # noqa: E402  (module import: its tests are not collected twice)


def http(code):
    return HTTPError("https://example.invalid", code, "x", {}, None)


class PartialExtractTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name)
        self.data = self.root / "processed"
        self.data.mkdir()
        for p in (mock.patch.object(c, "DATA_DIR", self.data),
                  mock.patch.dict(os.environ, {"DAILY_RUN_ID": "run-1"}),
                  contextlib.redirect_stdout(io.StringIO())):
            p.__enter__()
            self.addCleanup(p.__exit__, None, None, None)

    def item(self, n):
        return {"source_type": "edgar", "source_id": f"acc-{n}", "title": f"Example {n} (EX{n})",
                "published_at": c.today(), "raw_text": f"Record backlog grew by {n}0 percent.",
                "url": f"https://example.org/{n}"}

    def run_extract(self, items, answers, run_id="run-1"):
        """answers: {source_id: None (model says no signal) | exception}; unlisted ids answer None."""
        payload = {"collected_at": datetime.now(timezone.utc).isoformat(), "items": items}

        def model(item, key):
            answer = answers.get(item["source_id"])
            if isinstance(answer, BaseException):
                raise answer
            return answer

        with mock.patch.object(extract, "load_payload", return_value=payload), \
             mock.patch.object(extract, "load_seen_sources", return_value=set()), \
             mock.patch.object(extract, "load_edgar_extract_config", return_value=(40, [])), \
             mock.patch.object(c, "load_dotenv_value", return_value="fake"), \
             mock.patch.object(extract, "GEMINI_SLEEP", 0), \
             mock.patch.dict(os.environ, {"DAILY_RUN_ID": run_id}), \
             mock.patch.object(extract, "build_signal", side_effect=model):
            return extract.main(["extract"])

    def ledger(self):
        return c.read_json(self.data / "source_state.json", {})

    def status(self):
        return c.read_json(self.data / "run_status.json", {})["extract"]

    def record_step(self, code, run_id="run-1"):
        """What the workflow wrapper records for this extract run, then whether notify may run."""
        state = d.record_step({}, c.today(), "collect", "success", "run-0", datetime.now(timezone.utc), 0)
        status = "success" if code == 0 else "failed"
        quality = d.extract_quality(run_id) if status == "success" else "unknown"
        d.record_step(state, c.today(), "extract", status, run_id, datetime.now(timezone.utc), code, quality)
        return state, d.blocking(d.day_steps(state, c.today()), "notify")

    def test_nine_answers_and_one_503_is_partial_and_opens_risk_alerts(self):
        items = [self.item(n) for n in range(10)]
        self.assertEqual(self.run_extract(items, {"acc-9": http(503)}), 0)
        status = self.status()
        self.assertEqual((status["status"], status["outcome"], status["processed_today"]), ("partial", "partial", 9))
        self.assertEqual((status["unserved_failed"], status["run_id"]), (1, "run-1"))
        waiting = self.ledger()["acc-9"]
        self.assertEqual((waiting["status"], waiting["reason"], waiting["http_status"]),
                         ("retry", "provider_overloaded", 503))
        # The overload wait (30 min here, no shared wait recorded), not the 12-hour request retry.
        wait = datetime.fromisoformat(waiting["next_retry_at"]) - datetime.now(timezone.utc)
        self.assertLess(wait, timedelta(minutes=31))
        state, blocked = self.record_step(0)
        self.assertIsNone(blocked)
        self.assertEqual(d.day_steps(state, c.today())["extract"]["quality_status"], "partial")

    def test_a_timeout_with_answers_is_partial(self):
        # 10/9: the first item timed out twice, the rest were answered, and notify was still blocked.
        items = [self.item(n) for n in range(3)]
        self.assertEqual(self.run_extract(items, {"acc-0": TimeoutError("slow")}), 0)
        self.assertEqual(self.status()["outcome"], "partial")
        record = self.ledger()["acc-0"]
        self.assertEqual(record["reason"], "TimeoutError")  # not an overload: keeps the 12-hour retry
        self.assertGreater(datetime.fromisoformat(record["next_retry_at"]) - datetime.now(timezone.utc),
                           timedelta(hours=11))

    def test_no_answer_and_a_503_blocks_risk_alerts(self):
        self.assertEqual(self.run_extract([self.item(0)], {"acc-0": http(503)}), 1)
        self.assertEqual((self.status()["status"], self.status()["outcome"]), ("degraded", "model_unavailable"))
        _state, blocked = self.record_step(1)
        self.assertEqual(blocked[0], "extract")

    def test_a_503_wait_with_no_answer_today_blocks(self):
        self.assertEqual(self.run_extract([self.item(0)], {"acc-0": c.ModelBudgetExhausted("provider_overloaded")}), 1)
        self.assertEqual(self.ledger()["acc-0"]["reason"], "provider_overloaded")
        self.assertEqual(self.status()["outcome"], "model_unavailable")

    def test_partial_day_stays_partial_when_the_resume_meets_only_503s(self):
        self.assertEqual(self.run_extract([self.item(0), self.item(1)], {"acc-1": http(503)}), 0)
        ledger = self.ledger()
        ledger["acc-1"]["next_retry_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        c.atomic_json(self.data / "source_state.json", ledger)
        # Same day, a later run: the collection file is gone and the model is still overloaded.
        self.assertEqual(self.run_extract([], {"acc-1": http(503)}, run_id="run-2"), 0)
        self.assertEqual((self.status()["outcome"], self.status()["processed_today"]), ("partial", 1))
        _state, blocked = self.record_step(0, "run-2")
        self.assertIsNone(blocked)

    def test_answers_from_an_earlier_day_do_not_count(self):
        self.assertEqual(self.run_extract([self.item(0)], {}), 0)
        ledger = self.ledger()
        yesterday = (date.fromisoformat(c.today()) - timedelta(days=1)).isoformat()
        ledger["acc-0"]["processed_day"] = yesterday
        c.atomic_json(self.data / "source_state.json", ledger)
        self.assertEqual(self.run_extract([self.item(1)], {"acc-1": http(503)}, run_id="run-2"), 1)
        self.assertEqual((self.status()["outcome"], self.status()["processed_today"]), ("model_unavailable", 0))

    def test_other_failures_are_errors_even_with_answers(self):
        items = [self.item(0), self.item(1)]
        self.assertEqual(self.run_extract(items, {"acc-1": json.JSONDecodeError("bad", "x", 0)}), 1)
        self.assertEqual(self.status()["outcome"], "error")
        self.assertEqual(self.run_extract([self.item(2), self.item(3)], {"acc-3": http(401)}, "run-2"), 1)
        self.assertEqual(self.status()["outcome"], "error")

    def test_a_ledger_write_failure_blocks(self):
        real = c.atomic_json

        def broken(path, value):
            if pathlib.Path(path).name == "source_state.json":
                raise OSError("disk full")
            return real(path, value)
        with mock.patch.object(c, "atomic_json", side_effect=broken):
            self.assertEqual(self.run_extract([self.item(0), self.item(1)], {"acc-1": http(503)}), 1)
        self.assertEqual(self.status()["status"], "failed")

    def test_a_status_from_another_run_is_never_this_runs_quality(self):
        self.assertEqual(self.run_extract([self.item(0), self.item(1)], {"acc-1": http(503)}), 0)
        self.assertEqual(d.extract_quality("run-1"), "partial")
        self.assertEqual(d.extract_quality("run-2"), "unknown")
        self.assertEqual(d.extract_quality(""), "unknown")
        # A clean run with nothing left waiting is complete; anything still waiting stays partial.
        ledger = self.ledger()
        ledger["acc-1"].update(status="rejected", reason="test")
        c.atomic_json(self.data / "source_state.json", ledger)
        self.assertEqual(self.run_extract([], {}, run_id="run-3"), 0)
        self.assertEqual(d.extract_quality("run-3"), "complete")

    def test_an_item_tried_but_never_processed_in_the_lookback_is_counted_as_expired(self):
        old = (date.fromisoformat(c.today()) - timedelta(days=c.policy()["signal_lookback_days"] + 1)).isoformat()
        c.atomic_json(self.data / "source_state.json", {
            "acc-old": {"status": "retry", "reason": "HTTPError", "attempts": 3, "item": {**self.item(9), "source_id": "acc-old",
                                                                                         "published_at": old}},
            "acc-new": {"status": "deferred", "attempts": 0, "item": {**self.item(8), "source_id": "acc-new",
                                                                       "published_at": old}}})
        self.assertEqual(self.run_extract([], {}), 0)
        self.assertEqual(self.ledger()["acc-old"]["reason"], "expired_unprocessed")
        self.assertNotEqual(self.ledger()["acc-new"]["reason"], "expired_unprocessed")
        self.assertEqual(self.status()["expired"], 1)

    def test_extract_partial_has_no_generic_60_minute_top_up(self):
        self.assertFalse(d.STEPS["extract"].partial_top_up)


class PartialThenResumeSendsOnceTest(ta.AlertTest):
    def test_a_risk_signal_is_sent_once_across_the_partial_run_and_its_resume(self):
        import promote
        c.write_rows("signal_log", [ta.signal(0)])
        promote.promote_signal(ta.signal(0))
        c.write_rows("signal_log", [ta.signal(1, entity_id="CIK:0000000000", signal_direction="negative", 티어="관망")])
        with mock.patch.object(notify, "deliver", side_effect=self.fake_deliver):
            self.assertEqual(notify.main(["notify"]), 0)   # after the partial extract
            self.assertEqual(notify.main(["notify"]), 0)   # after the same-day resume
        self.assertEqual(len(self.sent), 1)


if __name__ == "__main__":
    unittest.main()
