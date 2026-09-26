"""R3: every model HTTP request, retries included, is counted before it is sent."""
import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock
from urllib.error import HTTPError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import common as c  # noqa: E402
import extract  # noqa: E402

POLICY = {**c.policy(), "max_model_calls": 20, "model_budget": {"extract": 11, "cards": 3, "candidate_context": 6}}


class ModelBudgetTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data = pathlib.Path(tmp.name)
        self.day = "2026-09-25"
        for patch in (mock.patch.object(c, "DATA_DIR", self.data), mock.patch.object(c, "policy", return_value=POLICY),
                      mock.patch.object(c, "today", side_effect=lambda: self.day),
                      mock.patch.object(extract.time, "sleep"), contextlib.redirect_stdout(io.StringIO())):
            patch.__enter__()
            self.addCleanup(patch.__exit__, None, None, None)

    def used(self, **counts):
        c.atomic_json(self.data / "model_budget.json", {"days": {self.day: counts}, "counting_since": "x"})

    def counts(self):
        return json.loads((self.data / "model_budget.json").read_text(encoding="utf-8"))["days"].get(self.day, {})

    def call(self, component, effects):
        with mock.patch.object(extract, "urlopen", side_effect=effects) as urlopen:
            try:
                extract.call_gemini_prompt("p", "key", component, sleep=lambda _: None)
            except (c.ModelBudgetExhausted, HTTPError) as error:
                return urlopen.call_count, type(error).__name__
        return urlopen.call_count, None

    def test_each_retry_counts_and_the_last_request_is_not_retried_past_the_total(self):
        self.used(extract=5, cards=3, candidate_context=6, other=5)  # 19 of 20
        failure = HTTPError("u", 503, "busy", {}, None)
        self.assertEqual(self.call("extract", [failure, failure]), (1, "ModelBudgetExhausted"))
        self.assertEqual(sum(self.counts().values()), 20)

    def test_component_limit_is_not_borrowed(self):
        self.used(cards=3)
        self.assertEqual(self.call("cards", []), (0, "ModelBudgetExhausted"))
        self.assertEqual(c.model_calls_remaining("candidate_context"), 6)
        self.assertEqual(c.model_calls_remaining("extract"), 11)

    def test_retries_consume_the_component_limit(self):
        failure = HTTPError("u", 503, "busy", {}, None)
        calls, error = self.call("cards", [failure, failure, failure, failure])
        self.assertEqual((calls, error), (2, "HTTPError"))  # cards limit 3: no fourth request
        self.assertEqual(self.counts(), {"cards": 2})

    def test_kst_day_boundary_starts_a_new_budget(self):
        self.used(extract=11)
        self.assertEqual(c.model_calls_remaining("extract"), 0)
        self.day = "2026-09-26"
        self.assertEqual(c.model_calls_remaining("extract"), 11)

    def test_a_stop_after_reserving_keeps_the_count(self):
        with mock.patch.object(extract, "urlopen", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                extract.call_gemini_prompt("p", "key", "candidate_context")
        self.assertEqual(self.counts(), {"candidate_context": 1})

    def test_existing_counts_are_kept_when_limits_are_added(self):
        c.atomic_json(self.data / "model_budget.json", {"days": {self.day: {"extract": 4}}})
        c.reserve_model_call("cards")
        self.assertEqual(self.counts(), {"extract": 4, "cards": 1})
        self.assertEqual(json.loads((self.data / "model_budget.json").read_text(encoding="utf-8"))["counting_since"],
                         "unrecorded")


if __name__ == "__main__":
    unittest.main()
