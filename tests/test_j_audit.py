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

    def test_a_badly_typed_claim_is_refused_alone_and_the_copy_is_kept(self):
        """K2: Codex's reproduction (a list block_id) raised TypeError and left no audit file."""
        bad = claim()
        bad["block_id"] = []
        self.answer["claims"] = [bad, claim()]
        with mock.patch.object(extract, "urlopen", side_effect=self.gemini):
            report = ctx.run_drafts(NOW)
        [audit] = self.audits()
        self.assertEqual((audit["outcome"], audit["ctx_stored"]), ("answered", True))
        self.assertEqual(audit["answer"]["claims"][0]["block_id"], [])  # as the model sent it
        self.assertEqual([r["reason"] for r in audit["validation"]["rejected"]], ["invalid_field_type"])
        self.assertEqual(len(audit["validation"]["claims"]), 1)  # the good claim is kept
        self.assertEqual(report["requests"], 1)

    def test_malformed_shapes_offline(self):
        """K2: shapes a syntactically valid JSON answer can still have; nothing is converted into a fact."""
        blocks = [{"document_id": "DOC-A", "block_id": "p1", "text": "Revenue was $5 million in 2025."}]
        good = claim(quote="Revenue was $5 million in 2025.", block_id="p1", figures=["$5 million"], period="2025")
        variants = {"figures_object": {**good, "figures": {"a": "$5 million"}},
                    "figure_number": {**good, "figures": [5]},
                    "drivers_string": {**good, "drivers": "volume"},
                    "metric_list": {**good, "metric": ["revenue"]},
                    "period_number": {**good, "period": 2025},
                    "quote_dict": {**good, "quote": {"text": "Revenue"}}}
        for name, item in variants.items():
            with self.subTest(name):
                result = ctx.validate_draft({"claims": [item, good]}, blocks, {"ticker": "AAA"})
                self.assertEqual(([r["reason"] for r in result["rejected"]], len(result["claims"])),
                                 (["invalid_field_type"], 1))
        for answer in ([good], {"claims": {"x": good}}, {"claims": "text"}, {"next_check": {"q": "확인?"}},
                       {"next_check": [1, None, ["확인"]], "link": ["unconfirmed"]}):
            with self.subTest(answer=answer):
                result = ctx.validate_draft(answer, blocks, {"ticker": "AAA"})
                self.assertEqual((result["claims"], result["next_check"], result["link"]), ([], [], "unconfirmed"))

    def test_a_validator_bug_keeps_the_raw_answer_and_surfaces(self):
        """K2: an internal validator error is recorded with its type and is not turned into '0 drafts'."""
        with mock.patch.object(extract, "urlopen", side_effect=self.gemini), \
                mock.patch.object(ctx, "validate_draft", side_effect=RuntimeError("bug")):
            with self.assertRaises(RuntimeError):
                ctx.run_drafts(NOW)
        [audit] = self.audits()
        self.assertEqual((audit["outcome"], audit["validation_error"]), ("validation_error", {"type": "RuntimeError"}))
        self.assertEqual(audit["raw_response"]["text"], json.dumps(self.answer))
        self.assertEqual(audit["answer"], self.answer)
        self.assertNotIn("validation", audit)
        entry = ctx.load_state()["candidates"]["CAN-0000000000000001"]
        self.assertNotIn("context_id", entry)  # nothing was stored as a draft

    def test_audit_and_ctx_storage_are_separate_facts(self):
        with mock.patch.object(extract, "urlopen", side_effect=self.gemini), \
                mock.patch.object(ctx, "store_context", return_value=False):
            ctx.run_drafts(NOW)
        [audit] = self.audits()
        self.assertEqual((audit["outcome"], audit["ctx_stored"]), ("answered", False))

    def test_budget_exhaustion_is_recorded_without_a_request(self):
        with mock.patch.object(c, "model_calls_remaining", return_value=0), \
                mock.patch.object(extract, "urlopen", side_effect=AssertionError("request")):
            report = ctx.run_drafts(NOW)
        self.assertEqual((report["deferred"], report["requests"]), (1, 0))
        self.assertEqual(self.audits(), [])  # nothing was attempted


if __name__ == "__main__":
    unittest.main()
