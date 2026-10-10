"""S0 acceptance review (2026-10-11): (1) a rerun that sends nothing keeps today's unresolved
failures, (2) auto obeys the same-day recovery limits, (3) an interrupted recovery is continued
without a new slot. Fake model, clock and state only."""
import os
import pathlib
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common as c  # noqa: E402
import daily_run_state as d  # noqa: E402
import extract  # noqa: E402
import test_s0_partial_extract as tp  # noqa: E402  (module imports: their tests are not collected twice)
import test_s0_recover as tr  # noqa: E402

http, EVENING, THU, due, nothing = tp.http, tr.EVENING, tr.THU, tr.due, tr.nothing


class UnresolvedFailureTest(tp.PartialExtractBase):
    def due_now(self, *keys):
        ledger = self.ledger()
        for key in keys:
            ledger[key]["next_retry_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        c.atomic_json(self.data / "source_state.json", ledger)

    def test_an_empty_rerun_keeps_a_503_with_no_answer_blocked(self):
        self.assertEqual(self.run_extract([self.item(0)], {"acc-0": http(503)}), 1)
        self.assertEqual(self.run_extract([], {}, "run-2"), 1)
        self.assertEqual((self.status()["outcome"], self.status()["open_unserved"]), ("model_unavailable", 1))

    def test_an_empty_rerun_keeps_a_401_an_error(self):
        self.assertEqual(self.run_extract([self.item(0), self.item(1)], {"acc-1": http(401)}), 1)
        self.assertEqual(self.run_extract([], {}, "run-2"), 1)
        self.assertEqual((self.status()["outcome"], self.status()["open_errors"]), ("error", 1))

    def test_a_rerun_without_budget_or_raw_file_keeps_the_open_503(self):
        self.assertEqual(self.run_extract([self.item(0)], {"acc-0": http(503)}), 1)
        self.due_now("acc-0")
        budget = c.ModelBudgetExhausted("extract")
        self.assertEqual(self.run_extract([], {"acc-0": budget}, "run-2"), 1)
        self.assertEqual(self.status()["outcome"], "model_unavailable")
        with mock.patch.object(extract, "RAW_LATEST", self.root / "missing" / "latest.json"), \
             mock.patch.object(extract, "load_seen_sources", return_value=set()), \
             mock.patch.object(extract, "load_edgar_extract_config", return_value=(40, [])), \
             mock.patch.object(c, "load_dotenv_value", return_value="fake"), \
             mock.patch.object(extract, "build_signal", side_effect=budget), \
             mock.patch.dict(os.environ, {"DAILY_RUN_ID": "run-3"}):
            self.assertEqual(extract.main(["extract"]), 1)
        self.assertEqual(self.status()["outcome"], "model_unavailable")

    def test_a_new_success_does_not_hide_a_same_day_error(self):
        self.assertEqual(self.run_extract([self.item(0)], {"acc-0": json_error()}), 1)
        self.assertEqual(self.run_extract([self.item(1)], {}, "run-2"), 1)
        self.assertEqual((self.status()["outcome"], self.status()["processed_today"]), ("error", 1))

    def test_a_later_outage_of_the_same_item_keeps_its_error(self):
        self.assertEqual(self.run_extract([self.item(0)], {"acc-0": http(401)}), 1)
        self.due_now("acc-0")
        self.assertEqual(self.run_extract([], {"acc-0": http(503)}, "run-2"), 1)
        self.assertEqual(self.ledger()["acc-0"]["failure_class"], "error")

    def test_an_answer_resolves_the_failure_and_keeps_the_evidence(self):
        self.assertEqual(self.run_extract([self.item(0)], {"acc-0": http(503)}), 1)
        self.due_now("acc-0")
        self.assertEqual(self.run_extract([], {}, "run-2"), 0)
        record = self.ledger()["acc-0"]
        self.assertNotIn("failure_class", record)
        self.assertEqual((record["resolved"]["failure_class"], record["resolved"]["by"], record["resolved"]["run"]),
                         ("unserved", "model answer", "run-2"))
        self.assertEqual(self.status()["outcome"], "ok")

    def test_a_failure_of_an_earlier_day_is_not_todays_outage(self):
        self.assertEqual(self.run_extract([self.item(0), self.item(1)], {"acc-1": http(401)}), 1)
        ledger = self.ledger()
        yesterday = (date.fromisoformat(c.today()) - timedelta(days=1)).isoformat()
        ledger["acc-1"]["failure_day"] = yesterday
        c.atomic_json(self.data / "source_state.json", ledger)
        self.assertEqual(self.run_extract([], {}, "run-2"), 0)  # acc-1 still waits for its 12 hours
        self.assertEqual(self.status()["outcome"], "ok")
        self.assertEqual(d.extract_quality("run-2"), "partial")  # waiting items keep it partial

    def test_a_429_wait_keeps_the_approved_rule(self):
        stop = c.ModelBudgetExhausted("provider_rate_limited")
        self.assertEqual(self.run_extract([self.item(0)], {"acc-0": stop}), 0)
        self.assertEqual(self.status()["outcome"], "ok")
        self.assertEqual(d.extract_quality("run-1"), "partial")


def json_error():
    import json
    return json.JSONDecodeError("bad", "x", 0)


class AutoLimitTest(tr.RecoverBase):
    def used(self, state, n=2, last=None):
        last = last or EVENING - timedelta(hours=2)
        state["days"][THU]["recoveries"] = [
            {"run_id": f"old-{i}", "started_at": (last - timedelta(hours=i)).isoformat()} for i in range(n)]

    def auto(self, state, at=EVENING, extract_resume=due, draft_resume=None, notes=None, redo=frozenset()):
        return d.plan_detail(state, THU, "auto", at, {}, redo, draft_resume, extract_resume, notes)

    def test_auto_does_not_rerun_a_model_stopped_extract_past_the_limit(self):
        state = self.daily()
        self.used(state)
        notes = {}
        self.assertEqual(self.auto(state, notes=notes), {})
        self.assertEqual(notes["extract"], "recover_max 2 used")

    def test_auto_respects_spacing_and_waits(self):
        state = self.daily()
        self.used(state, 1, last=EVENING - timedelta(minutes=59))
        self.assertEqual(self.auto(state), {})
        state = self.daily()
        notes = {}
        self.assertEqual(self.auto(state, extract_resume=nothing, notes=notes), {})
        self.assertEqual(notes["extract"], "nothing to resume now")

    def test_within_the_limit_auto_resumes_and_counts(self):
        state = self.daily()
        detail = self.auto(state)
        self.assertEqual(detail["extract"], "extract_resume")
        self.assertIn("notify", detail)  # blocked before, runs again with its resumed extract
        d.apply_plan(state, THU, "a2", "auto", "workflow_dispatch", detail, EVENING, "sha", "pol")
        self.assertEqual(len(state["days"][THU]["recoveries"]), 1)

    def test_other_needed_steps_still_run_past_the_limit(self):
        state = self.daily()
        self.used(state)
        d.record_step(state, THU, "prices", "started", "r1", EVENING)
        d.record_step(state, THU, "prices", "failed", "r1", EVENING, 1)
        detail = self.auto(state)
        self.assertIn("prices", detail)
        self.assertNotIn("extract", detail)
        self.assertNotIn("notify", detail)

    def test_auto_draft_resume_shares_the_limit_and_is_counted(self):
        state = self.daily("success", "ok", "complete")
        self.used(state)
        notes = {}
        self.assertEqual(self.auto(state, draft_resume=lambda at: "2 drafts waiting", notes=notes), {})
        self.assertEqual(notes["context"], "recover_max 2 used")
        state = self.daily("success", "ok", "complete")
        detail = self.auto(state, draft_resume=lambda at: "2 drafts waiting")
        self.assertEqual(detail["context"], "draft_resume")
        d.apply_plan(state, THU, "a2", "auto", "workflow_dispatch", detail, EVENING, "sha", "pol")
        self.assertEqual(state["days"][THU]["recoveries"][-1]["steps"], ["context"])

    def test_an_explicit_redo_keeps_its_meaning(self):
        state = self.daily()
        self.used(state)
        self.assertEqual(self.auto(state, redo=frozenset({"extract"}))["extract"], "requested")

    def test_the_first_daily_run_is_not_limited(self):
        detail = d.plan_detail({}, THU, "auto", EVENING, {}, frozenset(), None, nothing)
        self.assertEqual(detail["extract"], "not_run")


class ContinueRecoveryTest(tr.RecoverBase):
    def start(self, state, at=EVENING, run="r2", draft=False):
        detail = self.plan(state, at, draft_resume=(lambda a: "1 drafts waiting") if draft else nothing)
        d.apply_plan(state, THU, run, "recover", "schedule", detail, at, "sha", "pol")
        return detail

    def finish(self, state, run, *names, status="success"):
        for name in names:
            d.record_step(state, THU, name, "started", run, EVENING)
            d.record_step(state, THU, name, status, run, EVENING + timedelta(minutes=1), 0 if status == "success" else 1)

    def test_stopped_right_after_the_plan_is_continued_without_a_new_slot(self):
        state = self.daily()
        self.start(state)
        later = EVENING + timedelta(minutes=30)  # inside the 60-minute spacing: a continuation, not a new start
        detail = self.plan(state, later)
        self.assertEqual(detail, {"extract": "extract_resume_continue", "notify": "recovery_continue",
                                  "alerts": "recovery_continue", "views": "recovery_continue"})
        d.apply_plan(state, THU, "r3", "recover", "schedule", detail, later, "sha", "pol")
        record = state["days"][THU]["recoveries"]
        self.assertEqual((len(record), record[0]["continued_by"]), (1, ["r3"]))
        # Stopped again: the continuation's own steps are continued too.
        self.assertIn("extract", self.plan(state, later + timedelta(minutes=10)))

    def test_stopped_after_the_model_step_continues_only_the_rest(self):
        state = self.daily()
        self.start(state)
        self.finish(state, "r2", "extract")
        self.assertEqual(self.plan(state, EVENING + timedelta(minutes=30)),
                         {"notify": "recovery_continue", "alerts": "recovery_continue", "views": "recovery_continue"})
        self.finish(state, "r2", "notify", "alerts")
        self.assertEqual(self.plan(state, EVENING + timedelta(minutes=40)), {"views": "recovery_continue"})

    def test_a_continued_model_step_checks_its_wait_again(self):
        state = self.daily()
        self.start(state)
        notes = {}
        self.assertEqual(self.plan(state, EVENING + timedelta(minutes=30), extract_resume=nothing, notes=notes), {})
        self.assertEqual(notes["extract"], "continuation waits")
        self.assertEqual(notes["recover"], "interrupted recovery waits")

    def test_a_continued_draft_resume_stays_drafts_only_and_is_not_recounted(self):
        state = self.daily("success", "ok", "complete")
        self.start(state, draft=True)
        self.assertEqual(state["days"][THU]["steps"]["context"]["draft_resumes"], 1)
        detail = self.plan(state, EVENING + timedelta(minutes=30), draft_resume=lambda a: "1 drafts waiting")
        self.assertEqual(detail["context"], "draft_resume_continue")
        self.assertIn(detail["context"], d.DRAFTS_ONLY)
        d.apply_plan(state, THU, "r3", "recover", "schedule", detail, EVENING + timedelta(minutes=30), "sha", "pol")
        self.assertEqual(state["days"][THU]["steps"]["context"]["draft_resumes"], 1)

    def test_yesterdays_unfinished_recovery_is_not_continued_today(self):
        state = self.daily()
        self.start(state)
        self.day = "2026-09-25"
        notes = {}
        self.assertEqual(d.plan_detail(state, "2026-09-25", "recover", EVENING + timedelta(hours=24), {}, frozenset(),
                                       nothing, due, notes), {})
        self.assertEqual(notes["recover"], "no daily run today")


if __name__ == "__main__":
    unittest.main()
