"""Test-only virtual clock: every project module reads one moved 'now'.

The clock reads in this project are `datetime.now(...)` (common.today/utc_now,
daily_run_state, candidates.now_utc, candidate_context, collectors, tests) and
`date.today()` (extract, digest, collect_reddit). The runner replaces the
`datetime` and `date` names inside every module loaded from scripts/ and tests/
with subclasses whose now()/today() return the target instant, advancing with
real time, so one scenario never mixes the real and the virtual clock.
Production code has no date override; this file lives only under tests/.
"""
from __future__ import annotations

import importlib
import sys
from datetime import date as _date, datetime as _datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRS = (ROOT / "scripts", ROOT / "tests")


def make_classes(target: _datetime):
    offset = target - _datetime.now(timezone.utc)

    class VirtualDatetime(_datetime):
        @classmethod
        def now(cls, tz=None):
            moved = _datetime.now(timezone.utc) + offset
            return moved.astimezone(tz) if tz else moved.astimezone().replace(tzinfo=None)

        @classmethod
        def utcnow(cls):
            return (_datetime.now(timezone.utc) + offset).replace(tzinfo=None)

        @classmethod
        def today(cls):
            return cls.now()

    class VirtualDate(_date):
        @classmethod
        def today(cls):
            return VirtualDatetime.now().date()

    return VirtualDatetime, VirtualDate


def project_modules():
    for module in list(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if path and any(Path(path).resolve().parent == d for d in DIRS):
            yield module


def install(target: _datetime) -> tuple[type, type]:
    """Load every script module, then point their datetime/date names at the virtual clock."""
    for directory in DIRS:
        if str(directory) not in sys.path:
            sys.path.insert(0, str(directory))
    for path in sorted((ROOT / "scripts").glob("*.py")):
        try:
            importlib.import_module(path.stem)
        except Exception:  # a script that cannot load is reported by its own tests
            pass
    virtual_datetime, virtual_date = make_classes(target)
    for module in project_modules():
        if getattr(module, "datetime", None) is _datetime:
            module.datetime = virtual_datetime
        if getattr(module, "date", None) is _date:
            module.date = virtual_date
    return virtual_datetime, virtual_date


def kst(dt: _datetime) -> _datetime:
    return dt.astimezone(timezone(timedelta(hours=9)))
