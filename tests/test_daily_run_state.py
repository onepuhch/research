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

    def test_screen_failure_resumes_screen_only(self):
        state = finished({}, THU, {**all_ok(THU), "screen": "failed"})
        self.assertEqual(d.plan(state, THU, "auto"), ["screen"])

    def test_complete_day_runs_nothing(self):
        state = finished({}, THU, all_ok(THU))
        self.assertEqual(d.plan(state, THU, "auto"), [])
        self.assertTrue(d.complete(state, THU))

    def test_interrupted_step_is_not_done(self):
        state = finished({}, THU, {**all_ok(THU)})
        d.record_step(state, THU, "screen", "started", "r2", T)  # killed by the step timeout
        self.assertEqual(d.plan(state, THU, "auto"), ["screen"])

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
        self.assertEqual((entry["status"], entry["last_success_at"], entry["run_id"]), ("failed", first, "r2"))

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

    def test_commands_mode_writes_no_daily_record(self):
        env = self.plan_env("commands", "400")
        self.assertTrue(all(env[d.env_name(s)] == "false" for s in d.STEPS))
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
