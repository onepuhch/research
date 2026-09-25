import gzip
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import daily_run_state as d  # noqa: E402

THU = "2026-09-24"   # weekday
MON = "2026-09-28"   # weekly steps due
T = datetime(2026, 9, 24, 0, 20, tzinfo=timezone.utc)  # 09:20 KST Thursday


EXTERNAL = {"@tracking": "t0", "@evidence": "e0"}


def setUpModule():
    # Keep plans independent of the real ledger; tests change these values explicitly.
    global _external
    _external = mock.patch.dict(d.EXTERNAL, {k: (lambda k=k: EXTERNAL[k]) for k in EXTERNAL})
    _external.start()


def tearDownModule():
    _external.stop()


def finished(state, day, results, run_id="r1"):
    for step, status in results.items():
        d.record_step(state, day, step, "started", run_id, T)
        d.record_step(state, day, step, status, run_id, T + timedelta(minutes=1), 0 if status == "success" else 1)
    return state


def all_ok(day):
    return {s: "success" for s in d.required_steps(day)}


class PlanTest(unittest.TestCase):
    def test_required_steps_by_weekday(self):
        self.assertNotIn("weekly_report", d.required_steps(THU))
        self.assertEqual(d.required_steps(MON)[-2:], ["community", "weekly_report"])

    def test_fresh_day_runs_everything(self):
        self.assertEqual(d.plan({}, THU, "auto"), d.required_steps(THU))

    def test_collect_failure_resumes_collect_and_its_dependents_only(self):
        state = finished({}, THU, {**all_ok(THU), "collect": "failed"})
        self.assertEqual(d.plan(state, THU, "auto"), ["collect", "extract", "notify", "views"])

    def test_screen_failure_resumes_screen_and_the_views_that_read_it(self):
        state = finished({}, THU, {**all_ok(THU), "screen": "failed"})
        self.assertEqual(d.plan(state, THU, "auto"), ["screen", "cards", "views"])

    def test_complete_day_runs_nothing(self):
        state = finished({}, THU, all_ok(THU))
        self.assertEqual(d.plan(state, THU, "auto"), [])
        self.assertTrue(d.complete(state, THU))

    def test_interrupted_step_is_not_done(self):
        state = finished({}, THU, {**all_ok(THU)})
        d.record_step(state, THU, "screen", "started", "r2", T)  # killed by the step timeout
        self.assertEqual(d.plan(state, THU, "auto"), ["screen", "cards", "views"])

    def test_explicit_daily_reruns_everything_with_a_new_run(self):
        state = finished({}, THU, all_ok(THU))
        self.assertEqual(d.plan(state, THU, "daily"), d.required_steps(THU))
        d.start_run(state, THU, "r2", "daily", "workflow_dispatch", d.required_steps(THU), T, "sha", "pol")
        d.start_run(state, THU, "r3", "daily", "workflow_dispatch", d.required_steps(THU), T, "sha", "pol")
        self.assertEqual([r["run_id"] for r in state["days"][THU]["runs"]], ["r2", "r3"])

    def test_failed_rerun_keeps_last_success_time(self):
        state = finished({}, THU, {"screen": "success"}, "r1")
        first = state["days"][THU]["steps"]["screen"]["last_success_at"]
        finished(state, THU, {"screen": "failed"}, "r2")
        entry = state["days"][THU]["steps"]["screen"]
        self.assertEqual((entry["execution_status"], entry["last_success_at"], entry["run_id"]), ("failed", first, "r2"))
        self.assertEqual([a["execution_status"] for a in entry["attempts"]], ["success", "failed"])

    def test_commands_never_run_or_complete_the_day(self):
        self.assertEqual(d.plan({}, THU, "commands"), [])
        self.assertFalse(d.complete({}, THU))

    def test_monday_weekly_report_follows_views(self):
        state = finished({}, MON, {**all_ok(MON), "prices": "failed"})
        self.assertEqual(d.plan(state, MON, "auto"), ["prices", "views", "weekly_report"])

    def test_kst_midnight_boundary(self):
        self.assertEqual(d.kst_day(datetime(2026, 9, 24, 14, 59, tzinfo=timezone.utc)), "2026-09-24")
        self.assertEqual(d.kst_day(datetime(2026, 9, 24, 15, 0, tzinfo=timezone.utc)), "2026-09-25")
        # A run planned at 23:59 KST keeps writing to its own day; the next day starts fresh.
        state = finished({}, THU, all_ok(THU))
        self.assertEqual(d.plan(state, "2026-09-25", "auto"), d.required_steps("2026-09-25"))

    def test_unknown_mode_or_step_is_rejected(self):
        with self.assertRaises(ValueError):
            d.plan({}, THU, "full")
        with self.assertRaises(ValueError):
            d.record_step({}, THU, "nope", "success", "r1", T)

    def test_prune_keeps_recent_days(self):
        state = {"days": {"2026-06-01": {}, "2026-09-01": {}}}
        self.assertEqual(list(d.prune(state, THU)["days"]), ["2026-09-01"])


class ResumeAndRelationTest(unittest.TestCase):
    """Codex C follow-up: invalidation at plan time, required vs input relations, partial top-ups."""

    def begin(self, state, run_id, now=T, mode="auto"):
        detail = d.plan_detail(state, THU, mode, now)
        d.apply_plan(state, THU, run_id, mode, "workflow_dispatch", detail, now, "sha", "pol")
        return list(detail)

    def test_stop_after_eps_rerun_still_leaves_views_pending(self):
        # Reproduction: every step succeeded once, EPS needs a retry, plan is eps+views,
        # EPS succeeds and the run stops before views.
        state = finished({}, THU, {**all_ok(THU), "eps": "failed"})
        self.assertEqual(self.begin(state, "r2"), ["eps", "views"])
        d.record_step(state, THU, "eps", "started", "r2", T)
        d.record_step(state, THU, "eps", "success", "r2", T + timedelta(minutes=2), 0)
        self.assertEqual(d.plan(state, THU, "auto"), ["views"])
        self.assertFalse(d.complete(state, THU))

    def test_invalidation_alone_keeps_views_pending(self):
        state = finished({}, THU, {**all_ok(THU), "eps": "failed"})
        self.begin(state, "r2")
        entry = state["days"][THU]["steps"]["views"]
        self.assertEqual((entry["execution_status"], entry["planned_by"]), ("pending", "r2"))
        self.assertIsNotNone(entry["last_success_at"])  # the earlier success is kept, not used

    def test_new_input_revision_alone_makes_views_stale(self):
        state = finished({}, THU, all_ok(THU))
        finished(state, THU, {"returns": "success"}, "r2")  # returns only, views not planned
        self.assertEqual(d.plan_detail(state, THU, "auto"), {"views": "inputs_changed"})
        finished(state, THU, {"views": "success"}, "r2")
        self.assertEqual(d.plan(state, THU, "auto"), [])

    def test_failed_input_still_refreshes_views(self):
        state = finished({}, THU, all_ok(THU))
        finished(state, THU, {"screen": "failed"}, "r2")
        self.assertIn("views", d.plan(state, THU, "auto"))

    def test_new_tracking_or_evidence_redoes_cards_and_views_only(self):
        state = finished({}, THU, all_ok(THU))
        with mock.patch.dict(EXTERNAL, {"@tracking": "t1"}):
            self.assertEqual(d.plan_detail(state, THU, "auto"),
                             {"cards": "inputs_changed", "views": "dependency_rerun"})
        with mock.patch.dict(EXTERNAL, {"@evidence": "e1"}):
            self.assertEqual(d.plan(state, THU, "auto"), ["cards", "views"])

    def test_requested_redo_runs_the_step_and_its_users(self):
        state = finished({}, THU, all_ok(THU))
        self.assertEqual(d.plan_detail(state, THU, "auto", redo={"screen"}),
                         {"screen": "requested", "cards": "dependency_rerun", "views": "dependency_rerun"})
        with self.assertRaises(ValueError):
            d.plan(state, THU, "auto", redo={"everything"})

    def test_views_generator_version_change_rerenders(self):
        state = finished({}, THU, all_ok(THU))
        state["days"][THU]["steps"]["views"]["version"] = "views-v1"
        self.assertEqual(d.plan_detail(state, THU, "auto"), {"views": "inputs_changed"})

    def test_skipped_or_invalidated_extract_is_not_success(self):
        state = finished({}, THU, {**all_ok(THU), "collect": "failed"})
        self.begin(state, "r2")
        self.assertEqual(d.blocking(d.day_steps(state, THU), "extract")[0], "collect")
        # extract succeeded earlier today, but this plan invalidated it: notify must not use it.
        self.assertEqual(d.blocking(d.day_steps(state, THU), "notify")[0], "extract")
        self.assertIsNone(d.blocking(d.day_steps(state, THU), "views"))  # inputs never block

    def partial_screen(self, state, run_id, finished_at):
        d.record_step(state, THU, "screen", "started", run_id, finished_at - timedelta(minutes=14))
        d.record_step(state, THU, "screen", "success", run_id, finished_at, 0, "partial")

    def test_partial_top_up_waits_60_minutes_and_happens_once(self):
        state = finished({}, THU, all_ok(THU))
        self.partial_screen(state, "r1", T)
        finished(state, THU, {"cards": "success", "views": "success"}, "r1")
        self.assertEqual(d.plan(state, THU, "auto", T + timedelta(minutes=59)), [])
        later = T + timedelta(minutes=61)
        self.assertEqual(d.plan_detail(state, THU, "auto", later),
                         {"screen": "partial_retry", "cards": "dependency_rerun", "views": "dependency_rerun"})
        self.begin(state, "r2", later)
        self.assertEqual(state["days"][THU]["steps"]["screen"]["auto_retries"], 1)
        self.partial_screen(state, "r2", later + timedelta(minutes=20))
        finished(state, THU, {"cards": "success", "views": "success"}, "r2")
        self.assertEqual(d.plan(state, THU, "auto", later + timedelta(hours=3)), [])
        # The top-up is used up, but the data is still partial, never relabelled complete.
        self.assertTrue(d.complete(state, THU, later + timedelta(hours=3)))
        self.assertEqual(d.quality_summary(state, THU), {"screen": "partial"})

    def test_partial_policy_is_configurable(self):
        state = finished({}, THU, all_ok(THU))
        self.partial_screen(state, "r1", T)
        finished(state, THU, {"cards": "success", "views": "success"}, "r1")
        policy = {"partial_retry_max": 0, "partial_retry_min_gap_minutes": 60}
        self.assertEqual(d.plan(state, THU, "auto", T + timedelta(hours=5), policy), [])

    def test_schema_1_record_keeps_success_without_inventing_quality(self):
        old = {"schema_version": 1, "days": {THU: {"runs": [], "steps": {
            "screen": {"status": "success", "run_id": "r0", "exit_code": 0, "last_success_at": "x"}}}}}
        entry = d.migrate(old)["days"][THU]["steps"]["screen"]
        self.assertEqual((entry["execution_status"], entry["quality_status"]), ("success", "unknown"))
        self.assertNotIn("status", entry)

    def test_record_rejects_unknown_quality_or_pending(self):
        with self.assertRaises(ValueError):
            d.record_step({}, THU, "screen", "success", "r1", T, 0, "great")
        with self.assertRaises(ValueError):
            d.record_step({}, THU, "screen", "pending", "r1", T)


class ScreenQualityTest(unittest.TestCase):
    def setUp(self):
        import screen_revisions
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(screen_revisions, "SCREEN_DIR", Path(self.tmp.name))
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def snapshot(self, run_id, status):
        path = Path(self.tmp.name) / f"20260924T001000Z_{run_id}.json.gz"
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump({"run": {"run_id": run_id, "status": status}}, handle)

    def test_only_this_runs_snapshot_counts(self):
        self.snapshot("100-1", "success")
        self.assertEqual(d.screen_quality("101-1"), "unknown")  # an earlier success is not reused
        self.snapshot("101-1", "degraded")
        self.assertEqual(d.screen_quality("101-1"), "partial")
        self.assertEqual(d.screen_quality("100-1"), "complete")


class CliTest(unittest.TestCase):
    """The workflow path: plan -> step -> finish, against a temp state file."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "daily_runs.json"
        self.patch = mock.patch.object(d, "STATE_PATH", self.path)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def plan_env(self, mode, run_id):
        with mock.patch.dict("os.environ", {"GITHUB_RUN_ID": run_id, "GITHUB_RUN_ATTEMPT": "1"}), \
                mock.patch("builtins.print") as out, mock.patch.object(d, "datetime", wraps=datetime) as dt:
            dt.now.return_value = T
            d.main(["plan", "--mode", mode, "--event", "workflow_dispatch"])
        lines = [call.args[0] for call in out.call_args_list if not call.kwargs.get("file")]
        return dict(line.split("=", 1) for line in lines)

    def step(self, env, name, code):
        with mock.patch.dict("os.environ", {"DAILY_DAY": env["DAILY_DAY"], "DAILY_RUN_ID": env["DAILY_RUN_ID"]}), \
                mock.patch.object(d.subprocess, "run", return_value=mock.Mock(returncode=code)):
            return d.main(["step", name, "--", "python", "x.py"])

    def test_second_serial_dispatch_does_nothing_after_success(self):
        env = self.plan_env("auto", "100")
        self.assertEqual(env["RUN_COLLECT"], "true")
        for step in d.required_steps(env["DAILY_DAY"]):
            self.assertEqual(self.step(env, step, 0), 0)
        second = self.plan_env("auto", "101")
        self.assertTrue(all(second[d.env_name(s)] == "false" for s in d.STEPS))

    def test_step_exit_code_is_passed_through_and_recorded(self):
        env = self.plan_env("auto", "200")
        self.assertEqual(self.step(env, "screen", 3), 3)
        state = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(state["days"][env["DAILY_DAY"]]["steps"]["screen"]["exit_code"], 3)
        self.assertEqual(self.plan_env("auto", "201")["RUN_SCREEN"], "true")

    def test_rejected_push_means_no_remote_success_so_next_run_resumes(self):
        env = self.plan_env("auto", "300")
        for step in d.required_steps(env["DAILY_DAY"]):
            self.step(env, step, 0)
        self.path.unlink()  # The next runner checks out the remote, which never received this file.
        self.assertEqual(self.plan_env("auto", "301")["RUN_COLLECT"], "true")

    def test_collect_failure_blocks_extract_without_calling_it(self):
        env = self.plan_env("auto", "500")
        self.assertEqual(self.step(env, "collect", 1), 1)
        with mock.patch.dict("os.environ", {"DAILY_DAY": env["DAILY_DAY"], "DAILY_RUN_ID": env["DAILY_RUN_ID"]}), \
                mock.patch.object(d.subprocess, "run") as run, mock.patch("builtins.print"):
            self.assertEqual(d.main(["step", "extract", "--", "python", "x.py"]), 0)
            self.assertEqual(d.main(["step", "notify", "--", "python", "x.py"]), 0)
        run.assert_not_called()
        steps = json.loads(self.path.read_text(encoding="utf-8"))["days"][env["DAILY_DAY"]]["steps"]
        self.assertEqual((steps["extract"]["execution_status"], steps["extract"]["blocked_reason"],
                          steps["extract"]["dependency_run_id"]), ("blocked", "collect failed", "500-1"))
        self.assertEqual(steps["notify"]["blocked_reason"], "extract blocked")
        self.assertEqual(self.plan_env("auto", "501")["RUN_EXTRACT"], "true")

    def test_screen_quality_is_recorded_from_this_runs_snapshot(self):
        env = self.plan_env("auto", "600")
        probe = {"screen": lambda run_id: "partial" if run_id == "600-1" else "unknown"}
        with mock.patch.dict(d.QUALITY_PROBES, probe):
            self.step(env, "screen", 0)
        entry = json.loads(self.path.read_text(encoding="utf-8"))["days"][env["DAILY_DAY"]]["steps"]["screen"]
        self.assertEqual((entry["execution_status"], entry["quality_status"]), ("success", "partial"))

    def test_commands_mode_writes_no_daily_record(self):
        env = self.plan_env("commands", "400")
        self.assertTrue(all(env[d.env_name(s)] == "false" for s in d.STEPS))
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
