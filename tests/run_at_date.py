"""Run the whole suite at a chosen instant (test-only; production code is unchanged).

    python tests/run_at_date.py 2027-02-15T03:00:00+00:00

Before running, it checks that the clock readers actually return that instant
(common.today in KST, common.utc_now, candidates.now_utc, date.today in scripts),
so a date scenario can never pass by silently using the real clock.
"""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import virtual_clock  # noqa: E402


def self_check(target: datetime) -> None:
    import candidates
    import common
    import extract
    expected_day = virtual_clock.kst(target).date().isoformat()
    readings = {
        "common.today": common.today(),
        "common.utc_now": common.utc_now()[:16],
        "candidates.now_utc": candidates.now_utc().isoformat()[:16],
        "extract.date.today": extract.date.today().isoformat(),
    }
    wanted = {"common.today": expected_day, "common.utc_now": target.isoformat()[:16],
              "candidates.now_utc": target.isoformat()[:16],
              "extract.date.today": target.astimezone().date().isoformat()}
    wrong = {k: (readings[k], wanted[k]) for k in wanted if readings[k] != wanted[k]}
    if wrong:
        raise SystemExit(f"virtual clock not in effect: {wrong}")
    print(f"[clock] {target.isoformat()} -> KST day {expected_day}; readers agree", flush=True)


def main(argv: list[str]) -> int:
    target = datetime.fromisoformat(argv[0])
    if target.tzinfo is None:
        raise SystemExit("give the instant with a UTC offset, e.g. 2027-02-15T03:00:00+00:00")
    loader = unittest.defaultTestLoader
    suite = loader.discover(str(Path(__file__).resolve().parent))  # loads test and script modules first
    virtual_clock.install(target)
    self_check(target)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
