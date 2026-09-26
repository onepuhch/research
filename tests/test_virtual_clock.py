"""The date scenarios must really run at the chosen instant, and the model budget must split at KST midnight."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))
import common as c  # noqa: E402
import virtual_clock  # noqa: E402

PROBE = """
import json, sys
sys.path.insert(0, {tests!r})
import virtual_clock
from datetime import datetime
virtual_clock.install(datetime.fromisoformat({target!r}))
import candidates, common, daily_run_state, extract
print(json.dumps({{"today": common.today(), "utc_now": common.utc_now()[:16],
                   "now_utc": candidates.now_utc().isoformat()[:16],
                   "kst_day": daily_run_state.kst_day(daily_run_state.datetime.now(daily_run_state.timezone.utc)),
                   "date_today": extract.date.today().isoformat()}}))
"""


class RunnerTest(unittest.TestCase):
    def probe(self, target):
        out = subprocess.run([sys.executable, "-c", PROBE.format(tests=str(HERE), target=target)],
                             capture_output=True, text=True, check=True, cwd=HERE.parent)
        return json.loads(out.stdout.strip().splitlines()[-1])

    def test_every_clock_reader_uses_the_chosen_instant(self):
        seen = self.probe("2027-02-15T03:00:00+00:00")
        self.assertEqual((seen["today"], seen["kst_day"]), ("2027-02-15", "2027-02-15"))
        self.assertEqual((seen["utc_now"], seen["now_utc"]), ("2027-02-15T03:00", "2027-02-15T03:00"))

    def test_kst_new_year_boundary(self):
        self.assertEqual(self.probe("2026-12-31T14:59:50+00:00")["today"], "2026-12-31")
        self.assertEqual(self.probe("2026-12-31T15:00:10+00:00")["today"], "2027-01-01")


class BudgetMidnightTest(unittest.TestCase):
    """The 9/26 outage: two runs must count on the KST day they actually happen."""

    def test_calls_before_and_after_kst_midnight_are_separate_days(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(c, "DATA_DIR", pathlib.Path(tmp)):
            before, _ = virtual_clock.make_classes(datetime(2026, 9, 25, 14, 59, 30, tzinfo=timezone.utc))
            after, _ = virtual_clock.make_classes(datetime(2026, 9, 25, 15, 0, 30, tzinfo=timezone.utc))
            with mock.patch.object(c, "datetime", before):
                c.reserve_model_call("candidate_context")
                self.assertEqual(c.today(), "2026-09-25")
            with mock.patch.object(c, "datetime", after):
                c.reserve_model_call("candidate_context")
                self.assertEqual(c.today(), "2026-09-26")
            days = c.read_json(pathlib.Path(tmp) / "model_budget.json", {})["days"]
            self.assertEqual(days, {"2026-09-25": {"candidate_context": 1}, "2026-09-26": {"candidate_context": 1}})


if __name__ == "__main__":
    unittest.main()
