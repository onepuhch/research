import copy
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import common as c
import research_journal as journal


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.destination = Path(self.temp.name)
        self.case = c.read_json(c.ROOT / "data/research/cases/ai_interconnect.json", {})
        self.at = "2026-09-14T13:00:00+00:00"

    def freeze(self, rows=None, at=None):
        return journal.capture(self.case, rows or [], at or self.at, self.destination)

    def actual(self, **changes):
        row = {"entity_id": "NASDAQ:ALAB", "지표명": "Revenue", "period_end": "2026-09-30",
               "metric_kind": "actual", "회계기준": "GAAP", "단위": "million", "통화": "USD",
               "출처": "ALAB IR", "출처URL": "https://example.com/results", "data_quality": "live",
               "as_of": "2026-11-01T12:00:00+00:00", "현재값": "539"}
        return {**row, **changes}

    def test_reruns_preserve_baseline_and_new_revision_is_separate(self):
        first = self.freeze()
        again = self.freeze([self.actual()], "2026-12-01T00:00:00+00:00")
        self.assertEqual(first, again)
        self.case = copy.deepcopy(self.case)
        self.case["decision_tests"][0]["threshold"] = 500
        second = self.freeze()
        self.assertNotEqual(first["revision"], second["revision"])
        self.assertEqual(len(list(self.destination.glob("*.json"))), 2)

    def test_first_result_and_later_correction_do_not_rewrite_verdict(self):
        snapshot = self.freeze()
        rows = [self.actual(), self.actual(as_of="2026-11-02", 현재값="550")]
        result = journal.evaluate(snapshot, rows, "2026-11-03T00:00:00Z")[0]
        self.assertEqual(result["status"], "반증 발동")
        self.assertEqual(result["first"]["현재값"], "539")
        self.assertEqual(result["latest"]["현재값"], "550")
        early = journal.evaluate(snapshot, rows, "2026-10-01T00:00:00Z")[0]
        self.assertEqual(early["status"], "평가 대기")

    def test_wrong_definitions_and_guidance_do_not_count(self):
        snapshot = self.freeze()
        rows = [self.actual(**change) for change in [
            {"metric_kind": "guidance"}, {"회계기준": "non-GAAP"}, {"entity_id": "NASDAQ:CRDO"},
            {"통화": "EUR"}, {"출처": "other"}, {"period_end": "2025-09-30"},
            {"data_quality": "example"}, {"as_of": "2026-09-20"}]]
        self.assertEqual(journal.evaluate(snapshot, rows, "2026-12-01T00:00:00Z")[0]["status"], "평가 대기")

    def test_retrospective_registration_and_tampering_are_rejected(self):
        snapshot = self.freeze(at="2026-10-02T00:00:00Z")
        result = journal.evaluate(snapshot, [self.actual()], "2026-12-01T00:00:00Z")[0]
        self.assertEqual(result["status"], "사후 등록·성과 제외")
        snapshot["case"]["decision_tests"][0]["threshold"] = 1
        with self.assertRaises(ValueError):
            journal.evaluate(snapshot, [], "2026-12-01T00:00:00Z")

    def test_future_observations_excluded_and_no_trigger_is_not_success(self):
        snapshot = self.freeze([self.actual()])
        self.assertEqual(snapshot["observations"], [])
        result = journal.evaluate(snapshot, [self.actual(현재값="550")], "2026-12-01T00:00:00Z")[0]
        self.assertEqual(result["status"], "반증 미발동·적중 판정 아님")


if __name__ == "__main__":
    unittest.main()
