"""S0-B: the six-hourly schedule resumes a partial or model-stopped extract (and context drafts)
the same KST day without the PC timer, within its waits and daily limits. Fake clock and state
only: no model, SEC or Telegram request."""
import contextlib
import io
import os
import pathlib
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common as c  # noqa: E402
import daily_run_state as d  # noqa: E402
import extract  # noqa: E402
from test_daily_run_state import EXTERNAL  # noqa: E402

THU = "2026-09-24"
DAILY = datetime(2026, 9, 24, 6, 0, tzinfo=timezone.utc)      # 15:00 KST, the delayed daily cron
EVENING = datetime(2026, 9, 24, 13, 30, tzinfo=timezone.utc)   # 22:30 KST, the 21:23 schedule, late
NEXT_SLOT = datetime(2026, 9, 24, 19, 30, tzinfo=timezone.utc)  # 04:30 KST: already the next KST day


def due(at):
    return "1 items due"


def nothing(at):
    return None


class RecoverTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data = pathlib.Path(tmp.name)
        for p in (mock.patch.object(c, "DATA_DIR", self.data),
                  mock.patch.object(d, "STATE_PATH", self.data / "daily_runs.json"),
                  mock.patch.dict(d.EXTERNAL, {k: (lambda k=k: EXTERNAL[k]) for k in EXTERNAL}),
                  mock.patch.object(c, "today", side_effect=lambda: self.day),
                  contextlib.redirect_stdout(io.StringIO())):
            p.__enter__()
            self.addCleanup(p.__exit__, None, None, None)
        self.day = THU

    def daily(self, extract="failed", outcome="model_unavailable", quality="unknown", context="success"):
        """Today's daily run r1: every step ran; extract as given and its own status record."""
        state = d.apply_plan({}, THU, "r1", "auto", "schedule", {s: "not_run" for s in d.required_steps(THU)},
                             DAILY, "sha", "pol")
        for step in d.required_steps(THU):
            status = {"extract": extract, "context": context}.get(step, "success")
            d.record_step(state, THU, step, "started", "r1", DAILY)
            if step == "notify" and extract != "success":
                d.record_step(state, THU, step, "blocked", "r1", DAILY, reason="extract failed")
                continue
            d.record_step(state, THU, step, status, "r1", DAILY + timedelta(minutes=1),
                          0 if status == "success" else 1, quality if step == "extract" and status == "success" else "unknown")
        c.atomic_json(self.data / "run_status.json", {"extract": {"run_id": "r1", "outcome": outcome,
                                                                   "status": "partial" if quality == "partial" else "degraded"}})
        return state

    def plan(self, state, at, extract_resume=due, draft_resume=nothing, notes=None):
        return d.plan_detail(state, THU if at.astimezone(d.KST).date().isoformat() == THU else
                             at.astimezone(d.KST).date().isoformat(), "recover", at, {}, frozenset(),
                             draft_resume, extract_resume, notes)

    def test_resumes_a_model_stopped_extract_and_its_users_only(self):
        state = self.daily()
        detail = self.plan(state, EVENING)
        self.assertEqual(detail, {"extract": "extract_resume", "notify": "dependency_rerun",
                                  "alerts": "dependency_rerun", "views": "dependency_rerun"})
        self.assertNotIn("collect", detail)
        self.assertNotIn("screen", detail)
        d.apply_plan(state, THU, "r2", "recover", "schedule", detail, EVENING, "sha", "pol")
        self.assertEqual(state["days"][THU]["recoveries"][0]["steps"], ["extract"])

    def test_a_partial_extract_is_resumed_but_a_complete_one_is_not(self):
        self.assertIn("extract", self.plan(self.daily("success", "partial", "partial"), EVENING))
        self.assertEqual(self.plan(self.daily("success", "ok", "complete"), EVENING), {})

    def test_other_extract_failures_are_not_resumed_here(self):
        notes = {}
        self.assertEqual(self.plan(self.daily(outcome="error"), EVENING, notes=notes), {})
        self.assertIn("not resumable", notes["extract"])
        # A status record of another run never makes this run resumable.
        state = self.daily()
        c.atomic_json(self.data / "run_status.json", {"extract": {"run_id": "r0", "outcome": "model_unavailable"}})
        self.assertEqual(self.plan(state, EVENING), {})

    def test_no_daily_record_means_no_recovery(self):
        notes = {}
        self.assertEqual(self.plan({}, EVENING, notes=notes), {})
        self.assertEqual(notes["recover"], "no daily run today")

    def test_waits_plan_nothing_and_say_why(self):
        notes = {}
        self.assertEqual(self.plan(self.daily(), EVENING, extract_resume=nothing, notes=notes), {})
        self.assertEqual(notes["extract"], "nothing to resume now")

    def test_two_recoveries_a_day_at_least_60_minutes_apart(self):
        state = self.daily()
        d.apply_plan(state, THU, "r2", "recover", "schedule", self.plan(state, EVENING), EVENING, "sha", "pol")
        notes = {}
        self.assertEqual(self.plan(state, EVENING + timedelta(minutes=59), notes=notes), {})
        self.assertIn("last recovery", notes["recover"])
        second = EVENING + timedelta(minutes=61)
        d.apply_plan(state, THU, "r3", "recover", "schedule", self.plan(state, second), second, "sha", "pol")
        notes = {}
        self.assertEqual(self.plan(state, second + timedelta(minutes=5), notes=notes), {})
        self.assertEqual(notes["recover"], "recover_max 2 used")

    def test_the_count_is_saved_before_steps_run_and_survives_a_restart(self):
        state = self.daily()
        d.save(d.apply_plan(state, THU, "r2", "recover", "schedule", self.plan(state, EVENING), EVENING, "sha", "pol"))
        # The run stops here; a new process reads the saved count.
        reloaded = d.load()
        self.assertEqual(len(reloaded["days"][THU]["recoveries"]), 1)
        self.assertEqual(reloaded["days"][THU]["steps"]["extract"]["execution_status"], "pending")

    def test_usual_schedule_gives_one_chance_and_a_midnight_delay_gives_none(self):
        state = self.daily()
        self.assertTrue(self.plan(state, EVENING))   # 15:00 daily -> 22:30 schedule: one chance
        self.day = "2026-09-25"
        notes = {}
        self.assertEqual(self.plan(state, NEXT_SLOT, notes=notes), {})  # next slot is another KST day
        self.assertEqual(notes["recover"], "no daily run today")
        self.assertEqual(self.plan(state, datetime(2026, 9, 24, 15, 10, tzinfo=timezone.utc)), {})  # 00:10 KST

    def test_context_drafts_resume_with_their_users(self):
        state = self.daily("success", "ok", "complete")
        detail = self.plan(state, EVENING, draft_resume=lambda at: "2 drafts waiting")
        self.assertEqual(detail, {"context": "draft_resume", "cards": "dependency_rerun",
                                  "alerts": "dependency_rerun", "views": "dependency_rerun"})

    def test_auto_also_resumes_a_partial_extract_and_counts_it(self):
        state = self.daily("success", "partial", "partial")
        detail = d.plan_detail(state, THU, "auto", EVENING, {}, frozenset(), None, due)
        self.assertEqual(detail["extract"], "extract_resume")
        d.apply_plan(state, THU, "r2", "auto", "workflow_dispatch", detail, EVENING, "sha", "pol")
        self.assertEqual(state["days"][THU]["recoveries"][0]["mode"], "auto")
        # Without a resume due, a partial extract is left alone (no generic 60-minute top-up).
        self.assertNotIn("extract", d.plan_detail(self.daily("success", "partial", "partial"), THU, "auto",
                                                  EVENING, {}, frozenset(), None, nothing))

    def test_explicit_commands_stay_commands_only(self):
        self.assertEqual(d.plan_detail(self.daily(), THU, "commands", EVENING), {})

    def test_a_failed_resumed_step_fails_the_recovery_run(self):
        state = self.daily()
        detail = self.plan(state, EVENING)
        d.apply_plan(state, THU, "r2", "recover", "schedule", detail, EVENING, "sha", "pol")
        d.record_step(state, THU, "extract", "started", "r2", EVENING)
        d.record_step(state, THU, "extract", "failed", "r2", EVENING + timedelta(minutes=1), 1)
        d.record_step(state, THU, "notify", "blocked", "r2", EVENING, reason="extract failed")
        for step in ("alerts", "views"):
            d.record_step(state, THU, step, "started", "r2", EVENING)
            d.record_step(state, THU, step, "success", "r2", EVENING + timedelta(minutes=2), 0)
        d.save(state)
        with mock.patch.dict(os.environ, {"DAILY_DAY": THU, "DAILY_RUN_ID": "r2", "DAILY_MODE": "recover"}):
            self.assertEqual(d.cmd_finish(), 1)
        with mock.patch.dict(os.environ, {"DAILY_DAY": THU, "DAILY_RUN_ID": "none", "DAILY_MODE": "recover"}):
            self.assertEqual(d.cmd_finish(), 0)  # a recover run that planned nothing owes nothing


class ResumeCheckTest(unittest.TestCase):
    """extract.extract_resume_check reads the item waits, the shared waits and the budget."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data = pathlib.Path(tmp.name)
        self.now = datetime(2026, 9, 24, 13, 30, tzinfo=timezone.utc)
        for p in (mock.patch.object(c, "DATA_DIR", self.data),
                  mock.patch.object(c, "today", return_value=THU)):
            p.__enter__()
            self.addCleanup(p.__exit__, None, None, None)

    def item(self, name, **record):
        return {"status": "retry", "attempts": 1, **record,
                "item": {"source_type": "edgar", "source_id": name, "title": f"{name} Inc (X)",
                         "published_at": THU, "raw_text": "Record backlog grew by 30 percent."}}

    def ledger(self, **records):
        c.atomic_json(self.data / "source_state.json", records)

    def budget(self, **state):
        c.atomic_json(self.data / "model_budget.json", {"days": {}, **state})

    def test_an_item_after_its_503_wait_is_due(self):
        self.ledger(a=self.item("a", reason="provider_overloaded", next_retry_at=(self.now - timedelta(minutes=1)).isoformat()))
        self.assertEqual(extract.extract_resume_check(self.now)[0], "1 items due")

    def test_the_12_hour_request_retry_is_kept_apart_from_the_503_wait(self):
        later = (self.now + timedelta(hours=5)).isoformat()
        self.ledger(a=self.item("a", reason="HTTPError", next_retry_at=later))
        why, note = extract.extract_resume_check(self.now)
        self.assertIsNone(why)
        self.assertIn("nothing due", note)

    def test_a_running_503_wait_or_a_429_block_or_no_budget_stops_it(self):
        self.ledger(a=self.item("a", status="deferred"))
        until = (self.now + timedelta(minutes=20)).isoformat()
        self.budget(overload={extract.GEMINI_MODEL: {"until": until}})
        self.assertEqual(extract.extract_resume_check(self.now), (None, f"provider_overloaded until {until}"))
        self.budget(blocked={"reason": "provider_rate_limited", "until": (self.now + timedelta(hours=2)).isoformat()})
        self.assertEqual(extract.extract_resume_check(self.now), (None, "provider_rate_limited"))
        self.budget(days={THU: {"extract": c.policy()["model_budget"]["extract"]}})
        with mock.patch.object(c, "today", return_value=THU):
            self.assertEqual(extract.extract_resume_check(self.now), (None, "extract budget used"))

    def test_items_outside_the_lookback_are_not_due(self):
        old = (date.fromisoformat(THU) - timedelta(days=c.policy()["signal_lookback_days"] + 1)).isoformat()
        record = self.item("a", status="deferred")
        record["item"]["published_at"] = old
        self.ledger(a=record)
        self.assertEqual(extract.extract_resume_check(self.now), (None, "nothing waiting"))


if __name__ == "__main__":
    unittest.main()
