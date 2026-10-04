"""P regression tests (docs/p_o_acceptance_and_discovery_followup_2026-10-05.md). Stored inputs and fakes only."""
import json
import pathlib
import re
import sys
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import candidate_context as ctx  # noqa: E402
import common as c  # noqa: E402
import company_filings as cf  # noqa: E402
import extract  # noqa: E402
from test_candidate_context import claim  # noqa: E402


def stored_novt_item():
    state = json.loads((ROOT / "data" / "processed" / "source_state.json").read_text(encoding="utf-8"))
    return next(v for v in state.values() if v.get("signal_id") == "SIG-0900")["item"]


NOVT_QUOTE = ("Contract liabilities related to customer prepayments and accrued customer rebates totaled $3,312,226 "
              "and $1,058,978 as of December 31, 2025 and January 1, 2025, respectively.")


class SubjectNewsPathTest(unittest.TestCase):
    """P0: a quote in another company's own statements is not the filer's signal."""

    def test_stored_novt_input_is_refused(self):
        item = stored_novt_item()
        problem = extract.evidence_subject_problem(NOVT_QUOTE, item["raw_text"], item)
        self.assertTrue(problem.startswith("subject_other_entity"))
        self.assertIn("Runway Buyer, LLC", problem)

    def test_own_statements_and_an_acquisition_fact_are_kept(self):
        own = ("NOVANTA INC (NOVT) (CIK 0001076930) EX-99.1. Novanta Inc. CONSOLIDATED STATEMENTS OF OPERATIONS "
               "Revenue was $250.1 million in the quarter.")
        item = {"title": "NOVANTA INC (NOVT, NOVTU) (CIK 0001076930) EX-99.1 2026-10-02"}
        self.assertIsNone(extract.evidence_subject_problem("Revenue was $250.1 million in the quarter.", own, item))
        deal = ("Novanta Inc. completed the acquisition of Runway Buyer, LLC for $300 million on October 1, 2026. "
                "Runway Buyer, LLC CONSOLIDATED STATEMENT OF CASH FLOWS Net income $ 11,462,563")
        self.assertIsNone(extract.evidence_subject_problem(
            "Novanta Inc. completed the acquisition of Runway Buyer, LLC for $300 million", deal, item))
        self.assertTrue(extract.evidence_subject_problem("Net income $ 11,462,563", deal, item)
                        .startswith("subject_other_entity"))

    def test_an_unreadable_filer_is_unverified(self):
        item = stored_novt_item()
        problem = extract.evidence_subject_problem(NOVT_QUOTE, item["raw_text"], {"title": ""})
        self.assertTrue(problem.startswith("subject_unverified"))


class SubjectDraftPathTest(unittest.TestCase):
    """P0 in the validator (context-check-v10): blocks under another entity's statements."""

    TEXT = "Net income was $11.5 million in 2025."

    def run_with(self, scope, issuer_name="Novanta Inc."):
        blocks = [{"document_id": "DOC-A", "block_id": "p1", "text": self.TEXT, "scope": scope}]
        item = claim(quote=self.TEXT, block_id="p1", document_id="DOC-A", metric="Net income",
                     figures=["$11.5 million"], period="2025", note_ko="순이익이 기재되어 있다")
        return ctx.validate_draft({"claims": [item], "link": "unconfirmed"}, blocks, {"ticker": "NOVT", "name": issuer_name})

    def test_other_entity_unverified_and_own(self):
        self.assertEqual(self.run_with("Runway Buyer, LLC")["rejected"][0]["reason"], "subject_other_entity")
        self.assertEqual(self.run_with("Runway Buyer, LLC", issuer_name=None)["rejected"][0]["reason"], "subject_unverified")
        self.assertEqual(len(self.run_with("Novanta Inc.")["claims"]), 1)
        self.assertEqual(len(self.run_with(None)["claims"]), 1)  # no statement heading: the usual checks only
        self.assertEqual(ctx.PARSER_VERSION, "context-check-v10")
        self.assertIn("context-check-v9", ctx.REVALIDATED_VERSIONS)

    def test_block_scopes_follow_document_order(self):
        blocks = cf.normalize_html(b"<p>Novanta reports results.</p><p>Runway Buyer, LLC CONSOLIDATED STATEMENT OF "
                                   b"CASH FLOWS</p><p>Net income $ 11,462,563</p>")
        scopes = cf.block_scopes(blocks)
        self.assertEqual([scopes.get(b["id"]) for b in blocks], [None, "Runway Buyer, LLC", "Runway Buyer, LLC"])


class SignalQuarantineTest(unittest.TestCase):
    """P0: SIG-0900 is withheld from every reader; the ledger is unchanged; a broken list stops readers."""

    def test_withheld_everywhere_but_kept_in_the_ledger(self):
        self.assertIn("SIG-0900", {r["signal_id"] for r in c.read_rows("signal_log")})
        self.assertNotIn("SIG-0900", {r["signal_id"] for r in c.read_signals()})
        self.assertNotIn("SIG-0900", {r["signal_id"] for r in c.read_signals(live_only=False)})
        import promote
        self.assertIsNone(promote.find_signal("SIG-0900"))  # /track SIG-0900 finds nothing
        readers = {"candidate_alerts.py", "digest.py", "evaluate.py", "gen_report.py", "notify.py", "promote.py",
                   "telegram_cmd.py"}
        for name in readers:
            text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
            with self.subTest(name):
                self.assertFalse(re.search(r'read_(?:live_)?rows\("signal_log"\)', text))
                self.assertIn("read_signals(", text)

    def test_a_broken_list_raises(self):
        with mock.patch.object(c, "ROOT", ROOT / "does-not-exist"):
            with self.assertRaises(ValueError):
                c.read_signals()


if __name__ == "__main__":
    unittest.main()
