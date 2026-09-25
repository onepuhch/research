"""F2: commands run before the daily plan, and finish reports unfinished required steps."""
import json
import pathlib
import sys
import unittest
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common as c  # noqa: E402
import daily_run_state as d  # noqa: E402
import telegram_cmd  # noqa: E402
from test_candidates import CandidateFixture  # noqa: E402

WORKFLOW = pathlib.Path(__file__).resolve().parents[1] / ".github" / "workflows" / "daily_discovery.yml"


def step_block(text, name):
    start = text.index(f"- name: {name}")
    end = text.find("\n      - name:", start + 1)
    return text[start:end if end > 0 else None]


class WorkflowTextTest(unittest.TestCase):
    def test_commands_precede_the_plan_and_cannot_stop_it(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertLess(text.index("- name: Process commands independently"),
                        text.index("- name: Plan today's remaining steps"))
        plan = step_block(text, "Plan today's remaining steps")
        self.assertIn("always() && steps.migrate.outcome == 'success'", plan)
        self.assertNotIn("steps.commands", plan)

    def test_git_identity_is_set_before_any_step_that_pushes(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertLess(text.index("- name: Configure the state commit identity"),
                        text.index("- name: Send new-candidate alerts"))

    def test_context_runs_after_screen_and_before_cards(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        order = [text.index(f"- name: {name}") for name in (
            "Screen US stocks for sustained estimate upgrades", "Research candidate sources (SEC filings and drafts)",
            "Build candidate cards", "Send new-candidate alerts (shared daily budget)", "Build research views")]
        self.assertEqual(order, sorted(order))
        self.assertIn("timeout-minutes: 6", step_block(text, "Research candidate sources (SEC filings and drafts)"))

    def test_state_is_persisted_even_when_finish_fails(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertLess(text.index("- name: Close today's run record"),
                        text.index("- name: Persist state even when a service fails"))
        self.assertIn("if: always() && steps.migrate.outcome == 'success'",
                      step_block(text, "Persist state even when a service fails"))


class TrackThenPlanTest(CandidateFixture):
    def setUp(self):
        super().setUp()
        patch = mock.patch.object(d, "STATE_PATH", c.DATA_DIR / "daily_runs.json")
        patch.start()
        self.addCleanup(patch.stop)
        self.day = d.kst_day(datetime.now(timezone.utc))
        self.complete_day("r0")

    def complete_day(self, run_id):
        """Every required step ran today on the current inputs."""
        state = d.load()
        now = datetime.now(timezone.utc)
        for step in d.plan(state, self.day, "auto") or []:
            d.record_step(state, self.day, step, "started", run_id, now)
            d.record_step(state, self.day, step, "success", run_id, now, 0)
        d.save(state)

    def plan_env(self, mode, run_id):
        with mock.patch.dict("os.environ", {"GITHUB_RUN_ID": run_id, "GITHUB_RUN_ATTEMPT": "1"}), \
                mock.patch("builtins.print") as out:
            d.main(["plan", "--mode", mode, "--event", "workflow_dispatch"])
        lines = [call.args[0] for call in out.call_args_list if not call.kwargs.get("file")]
        return dict(line.split("=", 1) for line in lines)

    def queue_track(self, update_id, mode):
        sent = []
        with mock.patch.dict("os.environ", {"DAILY_MODE": mode}), \
                mock.patch.object(telegram_cmd, "send_reply", lambda token, chat, message: sent.append(message)):
            telegram_cmd.process_updates("t", "allowed", [self.update(update_id, f"/track {self.aaa['candidate_id']}")])
        return sent[0]

    def test_track_in_an_auto_run_is_collected_in_the_same_run(self):
        self.assertEqual(d.plan(d.load(), self.day, "auto"), [])
        reply = self.queue_track(1, "auto")
        self.assertIn("이번 일간 실행에서", reply)
        env = self.plan_env("auto", "700")
        planned = {name for name in d.STEPS if env[d.env_name(name)] == "true"}
        self.assertEqual(planned, {"eps", "quarterly", "prices", "cards", "alerts", "views"})
        import collect_eps
        self.assertIn("AAA", [t["ticker"] for t in collect_eps.load_targets()])

    def test_repeating_the_same_track_does_not_recollect(self):
        self.queue_track(1, "auto")
        self.complete_day("r1")
        self.queue_track(2, "auto")  # same idea returned, ledger unchanged
        self.assertEqual(d.plan(d.load(), self.day, "auto"), [])

    def test_commands_mode_answers_next_auto_and_collects_nothing(self):
        reply = self.queue_track(1, "commands")
        self.assertIn("다음 auto 일간 실행", reply)
        env = self.plan_env("commands", "701")
        self.assertTrue(all(env[d.env_name(name)] == "false" for name in d.STEPS))


class FinishExitTest(unittest.TestCase):
    def run_finish(self, results, mode="auto", day="2026-09-24"):
        state = {"days": {day: {"runs": [{"run_id": "r1"}], "steps": {}}}}
        now = datetime(2026, 9, 24, 1, tzinfo=timezone.utc)
        for step, status in results.items():
            if status == "blocked":
                d.record_step(state, day, step, "blocked", "r1", now, reason="x")
            else:
                d.record_step(state, day, step, "started", "r1", now)
                if status != "started":
                    d.record_step(state, day, step, status, "r1", now, 0 if status == "success" else 1,
                                  "partial" if step == "screen" and status == "success" else "unknown")
        with mock.patch.object(d, "load", return_value=state), mock.patch.object(d, "save"), \
                mock.patch.dict("os.environ", {"DAILY_DAY": day, "DAILY_RUN_ID": "r1", "DAILY_MODE": mode}), \
                mock.patch("builtins.print"):
            return d.main(["finish"])

    def all_ok(self):
        return {s: "success" for s in d.required_steps("2026-09-24")}

    def test_blocked_only_run_fails(self):
        self.assertEqual(self.run_finish({**self.all_ok(), "notify": "blocked"}), 1)

    def test_started_or_failed_step_fails_and_complete_run_passes(self):
        self.assertEqual(self.run_finish({**self.all_ok(), "eps": "started"}), 1)
        self.assertEqual(self.run_finish({**self.all_ok(), "eps": "failed"}), 1)
        self.assertEqual(self.run_finish(self.all_ok()), 0)

    def test_partial_quality_is_not_an_execution_failure(self):
        self.assertEqual(self.run_finish(self.all_ok()), 0)  # screen recorded partial above

    def test_commands_run_never_fails_for_daily_steps(self):
        self.assertEqual(self.run_finish({"eps": "failed"}, mode="commands"), 0)


if __name__ == "__main__":
    unittest.main()
