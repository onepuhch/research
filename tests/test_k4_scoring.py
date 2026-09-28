"""K4 required scoring tests on a small hand-made experiment (no model, no server, no network).

The NBR case uses the real p8 sentence: a divested unit's revenue accepted as the issuer's by the
v4 validator at run time, judged critical by hand review."""
import hashlib
import json
import pathlib
import re
import socket
import sys
import tempfile
import unittest
import urllib.request
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import candidate_context as ctx  # noqa: E402
import local_context_benchmark as lb  # noqa: E402

ISSUER = {"ticker": "NBR", "name": "Nabors Industries Ltd."}
P8 = ("The quarter ended June 30, 2025 includes revenue of $63 million, EBITDA of $37 million, and operating "
      "income of $26 million from Quail Tools, which was sold in August 2025.")
P25 = ("We now expect full-year adjusted EBITDA of $920 to $930 million and full-year adjusted free cash flow "
       "of $20 to $30 million.")
BLOCKS = [{"document_id": "DOC-N", "block_id": "p8", "text": P8},
          {"document_id": "DOC-N", "block_id": "p25", "text": P25}]
LABELS = {"companies": {"NBR": {
    "facts": [{"id": "nbr_guide_ebitda", "metric_terms": ["adjusted ebitda"], "figures": ["$920 to $930 million"],
               "period": "full-year", "subject": "issuer", "gaap": "non-GAAP", "kind": "guidance", "block": "p25",
               "important": True}],
    "critical": [{"id": "nbr_guide_not_income", "metric_terms": ["net income", "revenue"],
                  "figures": ["$920 to $930 million"]}],
    "counter": []}}}
MANUAL_NBR = {"verdict": "wrong", "severity": "critical", "reason": "divested_unit_as_issuer",
              "evidence": "p8: revenue from Quail Tools, which was sold in August 2025",
              "reviewed_at": "2026-09-28T22:10:00+09:00"}


def claim(**fields):
    base = {"kind": "fact", "subject": "issuer", "subject_name": None, "metric": "revenue", "figures": ["$63 million"],
            "period": "quarter ended June 30, 2025", "gaap": "unknown", "note_ko": "사업부 매출이다.", "quote": P8,
            "document_id": "DOC-N", "block_id": "p8", "drivers": ["acquisition_disposal"], "direction": "unknown",
            "currency": "USD"}
    return {**base, **fields}


GUIDE = dict(kind="guidance", metric="adjusted EBITDA", figures=["$920 to $930 million"], period="full-year",
             gaap="non-GAAP", quote=P25, block_id="p25", drivers=["unknown"])


def result(claims, status="insufficient_earnings_context", **fields):
    answer = {"claims": claims, "limitations": [], "next_check": [], "link": "unconfirmed"}
    return {"parser_version": "context-check-v4", "failure": None, "elapsed_s": 10.0,
            "raw_content": json.dumps(answer), "answer": answer,
            "validation": {"claims": claims, "rejected": [], "limitations": [], "context_status": status}, **fields}


def row_cells(markdown: str, first: str) -> list[str]:
    """Cells of one table row; an escaped pipe inside a cell does not split it."""
    line = next(x for x in markdown.splitlines() if x.startswith(f"| {first} |"))
    return [x.strip().replace("\\|", "|") for x in re.split(r"(?<!\\)\|", line)[1:-1]]


class K4ScoringTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.exp = pathlib.Path(tmp.name) / "experiment"
        self.labels = pathlib.Path(tmp.name) / "labels.json"
        self.labels.write_text(json.dumps(LABELS))

    def build(self, runs: dict, manual: dict | None = None, cases=None):
        """runs: {case_id: result or None (not run)}; every case is an eval case of NBR."""
        cases = cases or {cid: {"group": cid[-1], "status": "ready"} for cid in runs}
        (self.exp / "cases").mkdir(parents=True)
        (self.exp / "runs" / "final").mkdir(parents=True)
        entries = []
        for cid, meta in cases.items():
            case = {"case_id": cid, "group": meta["group"], "split": "eval", "ticker": "NBR", "status": meta["status"],
                    "blocks": BLOCKS, "issuer": ISSUER}
            (self.exp / "cases" / f"{cid}.json").write_text(json.dumps(case), encoding="utf-8")
            entries.append({"case_id": cid, "group": meta["group"], "split": "eval", "status": meta["status"]})
            if runs.get(cid) is not None:
                (self.exp / "runs" / "final" / f"{cid}.json").write_text(json.dumps(runs[cid]), encoding="utf-8")
        (self.exp / "experiment.json").write_text(json.dumps({"cases": entries, "stability_cases": []}))
        if manual is not None:
            (self.exp / "manual_review.json").write_text(json.dumps(manual), encoding="utf-8")

    def report(self, name="report", **kw):
        out = lb.report(self.exp, self.labels, self.exp / name, **kw)
        return out, (self.exp / f"{name}.md").read_text(encoding="utf-8")

    def test_manual_critical_nbr_is_one_in_json_and_markdown(self):
        self.build({"NBR-B": result([claim()])}, {"NBR-B": {"p8|revenue|$63 million": MANUAL_NBR}})
        out, md = self.report()
        self.assertEqual(out["summary"]["eval"]["critical_accepted"], 1)
        self.assertEqual(json.loads((self.exp / "report.json").read_text(encoding="utf-8"))
                         ["summary"]["eval"]["critical_accepted"], 1)
        self.assertEqual(row_cells(md, "eval")[11], "1")  # '중대 오류 수용(주장)'
        self.assertEqual(row_cells(md, "NBR-B")[8], "p8|revenue|$63 million manual:divested_unit_as_issuer")
        self.assertEqual((out["summary"]["eval"]["correct"], out["summary"]["eval"]["wrong_accepted"]), (0, 1))

    def test_bare_wrong_string_is_not_critical(self):
        """The J3 form 'wrong' keeps severity unset: a wrong claim, not a critical one."""
        self.build({"NBR-B": result([claim()])}, {"NBR-B": {"p8|revenue|$63 million": "wrong"}})
        out, md = self.report()
        self.assertEqual((out["summary"]["eval"]["critical_accepted"], out["summary"]["eval"]["wrong_accepted"]), (0, 1))
        self.assertEqual(row_cells(md, "eval")[11], "0")

    def test_manual_and_rule_on_one_claim_count_once(self):
        both = claim(metric="revenue", figures=["$920 to $930 million"], quote=P25, block_id="p25")
        key = "p25|revenue|$920 to $930 million"
        self.build({"NBR-B": result([both])}, {"NBR-B": {key: {**MANUAL_NBR, "reason": "guidance_as_revenue"}}})
        out, md = self.report()
        s = out["summary"]["eval"]
        self.assertEqual((s["critical_accepted"], s["critical_emitted"], s["critical_rejected"]), (1, 1, 0))
        row = out["rows"][0]
        self.assertEqual(row["critical_accepted"], [{"key": key, "rules": ["nbr_guide_not_income",
                                                                          "manual:guidance_as_revenue"]}])
        self.assertEqual(row_cells(md, "eval")[11], "1")

    def test_wrong_period_subject_or_extra_figure_is_neither_correct_nor_recalled(self):
        self.build({"NBR-B": None})
        case = json.loads((self.exp / "cases" / "NBR-B.json").read_text(encoding="utf-8"))
        right = lb.score_case(case, result([claim(**GUIDE)], "draft_ready"), LABELS, {})
        self.assertEqual((right["correct"], right["recall_model"], right["recall_accepted"]), (1, 1, 1))
        for name, bad in (("period", claim(**{**GUIDE, "period": "second quarter"})),
                          ("subject", claim(**{**GUIDE, "subject": "segment", "subject_name": "Drilling"})),
                          ("extra figure", claim(**{**GUIDE, "figures": ["$920 to $930 million", "$20 to $30 million"]})),
                          ("unknown period", claim(**{**GUIDE, "period": "unknown"}))):
            with self.subTest(name):
                scored = lb.score_case(case, result([bad], "draft_ready"), LABELS, {})
                self.assertEqual((scored["correct"], scored["recall_model"], scored["recall_accepted"]), (0, 0, 0))
                self.assertEqual(scored["mention_model"], 1)  # the loose mention rate is shown apart

    def test_not_run_and_failed_eval_cases_stay_in_the_denominator(self):
        failed = {"parser_version": "context-check-v4", "failure": "timeout", "elapsed_s": 120.0}
        self.build({"NBR-A": None, "NBR-B": result([claim(**GUIDE)], "draft_ready"), "NBR-C": failed,
                    "NBR-D": None},
                   cases={"NBR-A": {"group": "A", "status": "ready"}, "NBR-B": {"group": "B", "status": "ready"},
                          "NBR-C": {"group": "B", "status": "ready"},
                          "NBR-D": {"group": "A", "status": "dataset_missing"}})
        out, md = self.report()
        s = out["summary"]["eval"]
        self.assertEqual((s["cases"], s["ran"], s["not_run"], s["json_ok"], s["json_rate"]), (4, 2, 2, 1, 25.0))
        self.assertEqual((s["core_draft"], s["core_draft_possible"], s["core_draft_rate"]), (1, 4, 25.0))
        self.assertEqual(s["failures"], {"timeout": 1, "dataset_missing": 1, "not_run": 1})
        rows = {r["case_id"]: r for r in out["rows"]}
        self.assertEqual({(rows[c]["split"], rows[c]["group"]) for c in ("NBR-A", "NBR-D")}, {("eval", "A")})
        self.assertEqual(out["summary"]["eval_A"]["cases"], 2)
        self.assertEqual(row_cells(md, "eval")[1:4], ["4", "2", "2"])

    def tree(self, *parts):
        root = self.exp
        return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for part in parts for p in sorted((root / part).rglob("*") if (root / part).is_dir() else [root / part])
                if p.is_file()}

    def test_revalidation_keeps_old_answers_results_and_reports(self):
        self.build({"NBR-B": result([claim()])}, {"NBR-B": {"p8|revenue|$63 million": MANUAL_NBR}})
        old_out, _ = self.report("report")
        before = self.tree("runs", "cases", "report.json", "report.md", "manual_review.json")
        root = lb.revalidate(self.exp)
        self.assertEqual(root, self.exp / "revalidated" / ctx.PARSER_VERSION)
        new = json.loads((root / "final" / "NBR-B.json").read_text(encoding="utf-8"))
        self.assertEqual(new["validation_at_run"], result([claim()])["validation"])
        self.assertEqual(new["revalidation"]["kind"], "기존 표본에 대한 회귀 재검증")
        self.assertEqual((new["revalidation"]["validator"], new["revalidation"]["validator_at_run"],
                          new["revalidation"]["scoring_version"]),
                         (ctx.PARSER_VERSION, "context-check-v4", lb.SCORING_VERSION))
        self.assertEqual([x["reason"] for x in new["validation"]["rejected"]], ["subject_scope_conflict"])
        again, _ = self.report("report_v6", runs_root=root)
        self.assertEqual((again["summary"]["eval"]["critical_accepted"], again["summary"]["eval"]["critical_rejected"]),
                         (0, 1))
        self.assertEqual(again["validators"], [ctx.PARSER_VERSION])
        self.assertEqual(old_out["validators"], ["context-check-v4"])
        self.assertEqual(self.tree("runs", "cases", "report.json", "report.md", "manual_review.json"), before)
        written = (root / "final" / "NBR-B.json").read_bytes()
        lb.revalidate(self.exp)  # a second pass keeps what is written
        self.assertEqual((root / "final" / "NBR-B.json").read_bytes(), written)
        self.assertEqual(json.loads((root / "revalidation.json").read_text(encoding="utf-8"))["kept"], 1)

    def test_revalidate_and_report_make_no_network_or_model_call(self):
        self.build({"NBR-B": result([claim()])}, {"NBR-B": {"p8|revenue|$63 million": MANUAL_NBR}})
        with mock.patch.object(socket, "socket", side_effect=AssertionError("network")), \
                mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")), \
                mock.patch.object(urllib.request, "urlopen", side_effect=AssertionError("network")), \
                mock.patch.object(lb, "Loopback", side_effect=AssertionError("model server")):
            root = lb.revalidate(self.exp)
            self.report("report_v6", runs_root=root)
        self.assertTrue((root / "final" / "NBR-B.json").exists())


if __name__ == "__main__":
    unittest.main()
