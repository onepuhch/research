"""Q2: shared waits after 503s, budget kept, drafts resumed from stored documents. Fake clock and HTTP only."""
import io
import json
import pathlib
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock
from urllib.error import HTTPError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common as c  # noqa: E402
import candidate_context as ctx  # noqa: E402
import company_filings as cf  # noqa: E402
import daily_run_state as d  # noqa: E402
import extract  # noqa: E402
from test_candidate_context import CIK, NOW, FakeResponse, RunFixture, claim, release_record  # noqa: E402

MODEL = extract.GEMINI_MODEL


def http_error(code):
    return HTTPError("https://generativelanguage.googleapis.com/x", code, "x", {}, io.BytesIO(b""))


class OverloadStateTest(RunFixture):
    def test_two_503s_start_a_wait_then_probes_lengthen_it_and_success_resets(self):
        t = NOW
        c.record_model_result(MODEL, "503", t, rand=lambda: 0.5)
        self.assertIsNone(c.model_overload(MODEL, t))  # one 503 is not overload yet
        entry = c.record_model_result(MODEL, "503", t, rand=lambda: 0.5)
        self.assertEqual((entry["stage"], entry["jitter_s"]), (1, 15.0))
        until = datetime.fromisoformat(entry["until"])
        self.assertEqual(until, t + timedelta(minutes=30, seconds=15))
        self.assertEqual(c.model_overload(MODEL, t)["until"], entry["until"])  # reading never moves it
        waits = []
        for _ in range(6):  # each probe after a wait fails again
            nxt = datetime.fromisoformat(c.record_model_result(MODEL, "503", t, rand=lambda: 0.0)["until"])
            waits.append(int((nxt - t).total_seconds() // 60))
            t = nxt
        self.assertEqual(waits, [60, 120, 240, 360, 360, 360])
        stages = json.loads((self.data / "model_budget.json").read_text(encoding="utf-8"))["overload"][MODEL]
        self.assertEqual(stages["stage"], 5)
        self.assertEqual(datetime.fromisoformat(stages["until"]) - datetime.fromisoformat(stages["last_at"]),
                         timedelta(minutes=360))  # capped
        c.record_model_result(MODEL, "ok", t)
        self.assertIsNone(c.model_overload(MODEL, t))
        self.assertEqual(c.record_model_result(MODEL, "503", t)["stage"], 0)  # counting starts over

    def test_429_block_comes_first_and_a_503_never_shortens_it(self):
        c.block_model_provider("provider_rate_limited", 3600)
        c.record_model_result(MODEL, "503")
        c.record_model_result(MODEL, "ok")
        self.assertIsNotNone(c.model_provider_blocked())
        with self.assertRaisesRegex(c.ModelBudgetExhausted, "rate_limited"):
            c.reserve_model_call("candidate_context", MODEL)


class OverloadCallTest(RunFixture):
    def setUp(self):
        super().setUp()
        patch = mock.patch.object(c, "policy", return_value={**c.policy(), "max_model_calls": 20,
                                                             "model_budget": {"candidate_context": 6, "extract": 11}})
        patch.start()
        self.addCleanup(patch.stop)

    def test_failed_requests_count_and_a_wait_sends_nothing(self):
        with mock.patch.object(extract, "urlopen", side_effect=http_error(503)), \
                mock.patch.object(c, "today", return_value="2026-09-25"):
            with self.assertRaises(HTTPError):  # 503, then its one retry 503: the wait starts
                extract.call_gemini_prompt("p", "k", "extract", max_attempts=2, sleep=lambda s: None)
            self.assertEqual(c.model_calls_today("2026-09-25"), 2)  # failed requests are counted
            with mock.patch.object(extract, "urlopen", side_effect=AssertionError("sent")):
                with self.assertRaisesRegex(c.ModelBudgetExhausted, "overloaded"):
                    extract.call_gemini_prompt("p", "k", "candidate_context")
        self.assertEqual(c.model_calls_today("2026-09-25"), 2)

    def test_kst_midnight_resets_the_budget_not_the_wait(self):
        with mock.patch.object(c, "today", return_value="2026-09-25"):
            for _ in range(2):
                c.record_model_result(MODEL, "503")
            c.record_model_call("candidate_context")
        with mock.patch.object(c, "today", return_value="2026-09-26"):
            self.assertEqual(c.model_calls_remaining("candidate_context"), 6)
            self.assertIsNotNone(c.model_overload(MODEL))


class DraftOverloadTest(RunFixture):
    def setUp(self):
        super().setUp()
        cf.store_document(release_record())
        entry = {"status": "success", "ticker": "AAA", "document_ids": ["DOC-A"], "eps_target_period": "2027-12-31",
                 "issuer": {"cik": CIK}, "attempted_at": NOW.isoformat()}
        state = {"candidates": {f"CAN-{i:016X}": {**entry, "ticker": f"T{i}"} for i in range(4)},
                 "days": {}, "documents_by_source": {}}
        c.atomic_json(ctx.state_path(), state)
        for patch in (mock.patch.object(c, "policy", return_value={**c.policy(), "max_model_calls": 20,
                                                                    "model_budget": {"candidate_context": 6}}),
                      mock.patch.object(c, "load_dotenv_value", return_value="key"),
                      mock.patch.object(c, "today", return_value="2026-09-25")):
            patch.start()
            self.addCleanup(patch.stop)
        self.sent = 0

    def answer(self, request, timeout=None):
        self.sent += 1
        body = json.dumps({"claims": [claim()], "limitations": [], "next_check": [], "link": "temporal_context"})
        return FakeResponse(json.dumps({"candidates": [{"content": {"parts": [{"text": body}]}}]}).encode(), "x")

    def overloaded(self, request, timeout=None):
        self.sent += 1
        raise http_error(503)

    def test_two_503s_defer_the_rest_and_nobody_waits_24_hours(self):
        with mock.patch.object(extract, "urlopen", side_effect=self.overloaded):
            report = ctx.run_drafts(NOW)
        self.assertEqual((self.sent, report["failed"], report["deferred"]), (2, 2, 2))
        entries = ctx.load_state()["candidates"]
        nexts = sorted(datetime.fromisoformat(e["draft_next_at"]) for e in entries.values())
        self.assertTrue(all(n - datetime.now(timezone.utc) < timedelta(hours=2) for n in nexts))
        self.assertEqual(sorted(e["draft_status"] for e in entries.values()),
                         ["failed", "failed", "provider_overloaded", "provider_overloaded"])
        self.assertEqual({e.get("draft_failure") for e in entries.values() if e["draft_status"] == "failed"},
                         {"provider_overloaded"})

    def test_a_bad_answer_is_not_overload(self):
        with mock.patch.object(extract, "urlopen", side_effect=http_error(400)):
            ctx.run_drafts(NOW)
        entries = ctx.load_state()["candidates"].values()
        self.assertTrue(all(e.get("draft_failure") == "failed" for e in entries if e.get("draft_status") == "failed"))
        self.assertIsNone(c.model_overload(MODEL))

    def test_resume_plan_and_drafts_only_run_with_no_sec_request(self):
        with mock.patch.object(extract, "urlopen", side_effect=self.overloaded):
            ctx.run_drafts(NOW)
        current = {cid: "2027-12-31" for cid in ctx.load_state()["candidates"]}
        index = {"candidates": [{"candidate_id": cid, "eps": {"eps_target_period": p}} for cid, p in current.items()],
                 "observed_at": NOW.isoformat(), "stale": []}
        later = datetime.now(timezone.utc) + timedelta(hours=2)
        with mock.patch("candidates.load_index", return_value=index), \
                mock.patch("candidates.current_freshness", return_value=[]):
            self.assertIsNone(ctx.draft_resume_due(datetime.now(timezone.utc)))  # still waiting
            self.assertEqual(ctx.draft_resume_due(later), "4 drafts waiting")
            import test_daily_run_state as td
            with mock.patch.dict(d.EXTERNAL, {k: (lambda k=k: td.EXTERNAL[k]) for k in td.EXTERNAL}):
                stale = td.finished({}, td.THU, td.all_ok(td.THU))
                detail = d.plan_detail(stale, td.THU, "auto", later, d.DEFAULT_POLICY, frozenset(), ctx.draft_resume_due)
                self.assertEqual(d.plan_detail(stale, td.THU, "auto", later, d.DEFAULT_POLICY), {})  # no resume hook
        self.assertEqual(detail.get("context"), "draft_resume")
        self.assertNotIn("screen", detail)
        self.assertIn("cards", detail)  # its input changes; alerts and views follow as before
        stale["days"][td.THU]["steps"]["context"]["draft_resumes"] = d.DEFAULT_POLICY["draft_resume_max"]
        with mock.patch.dict(d.EXTERNAL, {k: (lambda k=k: td.EXTERNAL[k]) for k in td.EXTERNAL}):
            self.assertNotIn("context", d.plan_detail(stale, td.THU, "auto", later, d.DEFAULT_POLICY, frozenset(),
                                                      lambda now: "waiting"))
        # the resumed step: drafts from stored documents, never an SEC request
        self.screen(["AAA"])
        with mock.patch.object(cf, "SecClient", side_effect=AssertionError("SEC client")):
            report = ctx.run_sources(NOW, drafts_only=True)
        self.assertEqual((report["drafts_only"], report["targets"]), (True, 1))


if __name__ == "__main__":
    unittest.main()
