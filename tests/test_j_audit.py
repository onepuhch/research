"""J1: a pre-validation copy of every draft attempt, without changing requests, budget or cards."""
import hashlib
import json
import pathlib
import sys
import unittest
from unittest import mock
from urllib.error import HTTPError

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))
import candidate_context as ctx  # noqa: E402
import common as c  # noqa: E402
import company_filings as cf  # noqa: E402
import extract  # noqa: E402
from test_candidate_context import CIK, NOW, FakeResponse, RunFixture, claim, release_record  # noqa: E402

KEY = "SECRET-KEY-123"


class AuditTest(RunFixture):
    def setUp(self):
        super().setUp()
        cf.store_document(release_record())
        entry = {"status": "success", "ticker": "AAA", "document_ids": ["DOC-A"], "eps_target_period": "2027-12-31",
                 "issuer": {"cik": CIK, "name": "AAA Corp"}, "attempted_at": NOW.isoformat()}
        c.atomic_json(ctx.state_path(), {"candidates": {"CAN-0000000000000001": entry},
                                         "days": {}, "documents_by_source": {}})
        for patch in (mock.patch.object(c, "policy", return_value={**c.policy(), "max_model_calls": 20,
                                                                   "model_budget": {"candidate_context": 6}}),
                      mock.patch.object(c, "today", return_value="2026-09-25"),
                      mock.patch.object(c, "load_dotenv_value", return_value=KEY)):
            patch.start()
            self.addCleanup(patch.stop)
        self.answer = {"claims": [claim(), claim(metric="net income", period="Q9 2031", kind="guidance",
                                                subject="issuer", gaap="GAAP")],
                       "limitations": [], "next_check": ["3분기 실적 발표 확인"], "link": "temporal_context"}

    def gemini(self, request, timeout=None):
        self.sent = request
        body = json.dumps(self.answer)
        return FakeResponse(json.dumps({"candidates": [{"content": {"parts": [{"text": body}]}, "finishReason": "STOP"}],
                                        "usageMetadata": {"promptTokenCount": 10}}).encode(), "x")

    def audits(self):
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((self.data / "context_audit").rglob("*.json"))]

    def test_answer_is_kept_before_validation_with_reproducible_input(self):
        with mock.patch.object(extract, "urlopen", side_effect=self.gemini):
            report = ctx.run_drafts(NOW)
        [audit] = self.audits()
        self.assertEqual((audit["outcome"], audit["schema_version"], audit["candidate_id"]),
                         ("answered", 1, "CAN-0000000000000001"))
        # The refused item keeps every field the model gave, not the short excerpt.
        refused = audit["answer"]["claims"][1]
        self.assertEqual((refused["metric"], refused["period"], refused["kind"], refused["gaap"]),
                         ("net income", "Q9 2031", "guidance", "GAAP"))
        self.assertEqual(len(audit["validation"]["rejected"]), 1)
        self.assertEqual(audit["raw_response"]["text"], json.dumps(self.answer))
        self.assertEqual(audit["raw_response"]["finish_reason"], "STOP")
        # The prompt sent is the stored one, and it can be rebuilt from the stored documents.
        sent = json.loads(self.sent.data)["contents"][0]["parts"][0]["text"]
        self.assertEqual(audit["prompt"], sent)
        self.assertEqual(audit["prompt_sha256"], hashlib.sha256(sent.encode()).hexdigest())
        documents = [cf.load_document("DOC-A")]
        blocks, _ = ctx.relevant_blocks(documents)
        target = {"candidate_id": "CAN-0000000000000001", "ticker": "AAA", "eps_target_period": "2027-12-31",
                  "issuer_name": "AAA Corp"}
        self.assertEqual(ctx.draft_prompt(target, documents, blocks), audit["prompt"])
        self.assertEqual(audit["blocks"], blocks)
        self.assertEqual(audit["documents"][0]["raw_sha256"], documents[0]["raw_sha256"])
        # Requests and budget are what they were without the audit.
        self.assertEqual((report["requests"], audit["budget"]["requests_sent"]), (1, 1))
        self.assertEqual((audit["budget"]["candidate_context_before"], audit["budget"]["candidate_context_after"]),
                         (0, 1))
        self.assertTrue(ctx.history_dir().joinpath(audit["context_id"] + ".json").exists())

    def test_failure_keeps_type_and_status_but_no_url_or_key(self):
        url = f"https://generativelanguage.googleapis.com/x?key={KEY}"
        with mock.patch.object(extract, "urlopen", side_effect=HTTPError(url, 503, "busy", {}, None)):
            report = ctx.run_drafts(NOW)
        [audit] = self.audits()
        self.assertEqual((report["failed"], audit["outcome"], audit["error"]),
                         (1, "failed", {"type": "HTTPError", "http_status": 503}))
        self.assertFalse(audit["raw_response"]["available"])
        text = json.dumps(audit)
        self.assertNotIn(KEY, text)
        self.assertNotIn("googleapis", text)

    def test_an_injected_call_has_no_raw_text(self):
        ctx.run_drafts(NOW, call=lambda prompt: self.answer)
        [audit] = self.audits()
        self.assertEqual((audit["outcome"], audit["raw_response"]["available"]), ("answered", False))

    def test_a_copy_over_the_cap_says_truncated(self):
        with mock.patch.object(ctx, "AUDIT_MAX_BYTES", 3000), \
                mock.patch.object(extract, "urlopen", side_effect=self.gemini):
            ctx.run_drafts(NOW)
        path = next((self.data / "context_audit").rglob("*.json"))
        audit = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(audit["truncated"])
        self.assertGreater(audit["original_bytes"], 3000)
        self.assertTrue(audit["blocks"]["dropped"])
        self.assertLessEqual(len(json.dumps(audit, ensure_ascii=False, indent=1).encode()), 3000)

    def test_a_failed_audit_write_does_not_stop_the_draft(self):
        blocker = self.data / "not_a_dir"
        blocker.write_text("x")
        with mock.patch.object(ctx, "audit_dir", lambda day: blocker / day), \
                mock.patch.object(extract, "urlopen", side_effect=self.gemini):
            report = ctx.run_drafts(NOW)
        self.assertEqual((report["audit_write_failed"], report["requests"]), (1, 1))
        entry = ctx.load_state()["candidates"]["CAN-0000000000000001"]
        self.assertTrue(entry["context_id"].startswith("CTX-"))

    def test_budget_exhaustion_is_recorded_without_a_request(self):
        with mock.patch.object(c, "model_calls_remaining", return_value=0), \
                mock.patch.object(extract, "urlopen", side_effect=AssertionError("request")):
            report = ctx.run_drafts(NOW)
        self.assertEqual((report["deferred"], report["requests"]), (1, 0))
        self.assertEqual(self.audits(), [])  # nothing was attempted


if __name__ == "__main__":
    unittest.main()
