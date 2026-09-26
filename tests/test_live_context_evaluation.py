"""K3: the I3-2 counter picks one KST day and one run correctly. Temporary files only."""
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))
import candidate_context as ctx  # noqa: E402
import common as c  # noqa: E402
import live_context_evaluation as live  # noqa: E402

DAY = "2026-09-27"


def validation(status="draft_ready", core=1, accepted=2):
    claims = [{"kind": "fact", "core": i < core} for i in range(accepted)]
    return {"claims": claims, "rejected": [{"reason": "metric_not_in_quote"}], "context_status": status}


class LiveEvaluationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.history = self.tmp / "history"
        self.audit = self.tmp / "audit"
        self.history.mkdir()
        self.audit.mkdir()
        self.state = {"candidates": {"A": {"draft_status": "queued"}, "B": {"draft_status": "draft_ready"}}, "days": {}}
        (self.tmp / "model_budget.json").write_text(json.dumps({"days": {DAY: {"candidate_context": 3}}}))
        for patch in (mock.patch.object(ctx, "history_dir", return_value=self.history),
                      mock.patch.object(ctx, "load_state", side_effect=lambda: self.state),
                      mock.patch.object(c, "DATA_DIR", self.tmp)):
            patch.start()
            self.addCleanup(patch.stop)

    def ctx_record(self, context_id, generated_at, parser="context-check-v6"):
        (self.history / f"{context_id}.json").write_text(json.dumps(
            {"context_id": context_id, "generated_at": generated_at, "parser_version": parser}))

    def audit_copy(self, attempt, started_at, run_id="100-1", name=None, **fields):
        record = {"attempt_id": attempt, "started_at": started_at, "run_id": run_id, "ticker": "AAA",
                  "outcome": "answered", "parser_version": "context-check-v6", "code_sha": "abc",
                  "budget": {"requests_sent": 1}, "raw_response": {"available": True, "text": "{}"},
                  "validation": validation(), "context_id": None, **fields}
        (self.audit / f"{name or attempt}.json").write_text(json.dumps(record))

    def test_utc_times_are_counted_on_their_kst_day(self):
        """Codex's four boundaries plus the minutes around KST midnight."""
        for i, at in enumerate(("2026-09-26T15:01:00+00:00", "2026-09-27T03:00:00+00:00",
                                "2026-09-27T15:01:00+00:00", "2026-09-28T03:00:00+00:00",
                                "2026-09-26T14:59:59+00:00", "2026-09-26T15:00:00+00:00",
                                "2026-09-27T14:59:59+00:00", "2026-09-27T15:00:00+00:00",
                                "2026-09-27T09:00:00+09:00", "2026-09-27T12:00:00", "not a time")):
            self.ctx_record(f"CTX-{i}", at)
        result = live.collect(DAY)
        # in: 15:01Z(26), 03:00Z(27), 15:00:00Z(26), 14:59:59Z(27), 09:00+09 -> 5
        self.assertEqual(result["ctx_generated"]["in_day"], 5)
        self.assertEqual(result["ctx_generated"]["out_of_day"], 4)
        self.assertEqual(result["ctx_generated"]["time_unknown"], 2)  # naive and broken

    def test_one_run_once_per_attempt_and_other_runs_excluded(self):
        self.audit_copy("a1", "2026-09-27T00:20:00+00:00")
        self.audit_copy("a1", "2026-09-27T00:20:00+00:00", name="a1-copy")  # the same attempt twice
        self.audit_copy("a2", "2026-09-27T00:21:00+00:00", validation=validation("no_supported_claims", 0, 0))
        self.audit_copy("b1", "2026-09-27T05:00:00+00:00", run_id="200-1")
        self.audit_copy("next", "2026-09-27T15:30:00+00:00", run_id="300-1")  # the next KST day
        result = live.collect(DAY, self.audit, "100-1")
        self.assertEqual(result["audit_duplicates"], 1)
        self.assertEqual((result["run"]["attempts"], result["run"]["requests_sent"]), (2, 2))
        self.assertEqual(result["run"]["statuses"], {"draft_ready": 1, "no_supported_claims": 1})
        self.assertEqual((result["run"]["accepted"], result["run"]["core"]), (2, 1))
        self.assertEqual(result["run_excluded_other_runs"], 2)
        self.assertEqual(result["day_summary"]["runs"], {"100-1": 2, "200-1": 1})
        self.assertEqual(result["budget_vs_audit"]["audit_requests_day"], 3)
        self.assertEqual(result["budget_vs_audit"]["audit_requests_run"], 2)

    def test_a_run_across_midnight_keeps_its_attempts_and_shows_them(self):
        self.audit_copy("late", "2026-09-27T14:59:00+00:00")
        self.audit_copy("after", "2026-09-27T15:01:00+00:00")
        result = live.collect(DAY, self.audit, "100-1")
        self.assertEqual(result["run"]["attempts"], 2)
        self.assertEqual(result["day_summary"]["attempts"], 1)
        self.assertEqual(result["run_outside_day"], [("after", "2026-09-27T15:01:00+00:00")])

    def test_older_validator_is_shown_not_dropped(self):
        self.audit_copy("old", "2026-09-27T00:20:00+00:00", parser_version="context-check-v5")
        self.audit_copy("new", "2026-09-27T00:21:00+00:00")
        self.ctx_record("CTX-OLD", "2026-09-27T00:20:00+00:00", parser="context-check-v5")
        result = live.collect(DAY, self.audit, "100-1")
        self.assertEqual(result["run"]["by_parser"], {"context-check-v5": 1, "context-check-v6": 1})
        self.assertEqual(result["ctx_generated"]["in_day_by_parser"], {"context-check-v5": 1})

    def test_current_state_is_the_queue_not_the_runs_result(self):
        self.audit_copy("a1", "2026-09-27T00:20:00+00:00", validation=validation("no_supported_claims", 0, 0))
        self.state["candidates"]["A"]["draft_status"] = "draft_ready"  # changed later by another run
        result = live.collect(DAY, self.audit, "100-1")
        self.assertEqual(result["run"]["statuses"], {"no_supported_claims": 1})
        self.assertEqual(result["current_queue"], {"draft_ready": 2})

    def test_missing_truncated_and_null_sha_are_incomplete_evidence(self):
        self.assertEqual(live.collect(DAY, self.tmp / "nowhere", "100-1")["audit_evidence"], "missing")
        self.audit_copy("cut", "2026-09-27T00:20:00+00:00", truncated=True, code_sha=None,
                        raw_response={"dropped": True, "sha256": "x", "bytes": 9},
                        validation={"dropped": True, "sha256": "y", "bytes": 9})
        self.audit_copy("ok", "2026-09-27T00:21:00+00:00")
        (self.audit / "broken.json").write_text("{")
        result = live.collect(DAY, self.audit, "100-1")
        self.assertEqual(result["audit_evidence"], "incomplete")
        self.assertEqual(result["audit_unreadable"], 1)
        self.assertEqual(result["run"]["raw"], {"dropped": 1, "available": 1})  # a dropped raw is not 'available'
        self.assertEqual(result["run"]["code_sha"], ["abc", None])
        self.assertEqual(result["run"]["statuses"], {"-": 1, "draft_ready": 1})
        self.assertIn("run 100-1", live.render(result))

    def test_ctx_link_and_storage_are_reported(self):
        self.ctx_record("CTX-1", "2026-09-27T00:20:00+00:00")
        self.audit_copy("a1", "2026-09-27T00:20:00+00:00", context_id="CTX-1", ctx_stored=True)
        self.audit_copy("a2", "2026-09-27T00:21:00+00:00", context_id="CTX-2", ctx_stored=False)
        attempts = {a["attempt_id"]: a for a in live.collect(DAY, self.audit, "100-1")["attempts"]}
        self.assertEqual((attempts["a1"]["ctx_found"], attempts["a2"]["ctx_found"]), (True, False))


if __name__ == "__main__":
    unittest.main()
