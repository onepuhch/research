"""R2 review: retry allowance must persist across calls in the same KST day.

Uses the existing temporary-directory fixture and fake Yahoo responses only.
Exit 0 when the boundary is resolved, 1 while it remains open.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]
from test_q3_prices import PriceQueueTest  # noqa: E402
import common as c  # noqa: E402
import discovery_timing as timing  # noqa: E402


def probe():
    fixture = PriceQueueTest()
    try:
        fixture.setUp()
        fixture.build(25)
        failed = {f"T{i:02d}" for i in range(19)}
        fixture.answers = {ticker: 404 for ticker in failed}
        setup_report = fixture.collect("2026-10-10T03:00:00+00:00")
        fixture.calls.clear()
        first = fixture.collect("2026-10-11T03:00:00+00:00")
        first_calls = list(fixture.calls)
        fixture.calls.clear()
        second = fixture.collect("2026-10-11T04:00:00+00:00")
        second_calls = list(fixture.calls)
        retry_calls = [ticker for ticker in first_calls + second_calls if ticker in failed]
        day_usage = c.read_json(timing.queue_path(), {})["days"]["2026-10-11"]
        limits = timing.price_settings()
        resolved = len(retry_calls) <= limits["retries_per_day"]
        # The fixture must still exercise R2's original starvation case and preserve its fix.
        assert setup_report["failures"] == 19
        assert first["collected"] == 6
        assert sum(ticker in failed for ticker in first_calls) == 5
        assert day_usage["requests"] == len(first_calls) + len(second_calls)
        assert day_usage["requests"] <= limits["requests_per_day"]
        return {
            "case": "same_KST_day_two_price_invocations",
            "input": {"candidates": 25, "first_19_return": 404,
                      "first_day": "2026-10-10", "review_day": "2026-10-11"},
            "limits": {"requests_per_day": limits["requests_per_day"],
                       "retries_per_day": limits["retries_per_day"]},
            "setup_report": setup_report,
            "first_run": first, "second_run": second,
            "first_calls": first_calls, "second_calls": second_calls,
            "retry_ticker_count": len(retry_calls),
            "persisted_day_usage": day_usage,
            "resolved": resolved,
            "open_boundaries": int(not resolved),
            "network": "fake fetch; temporary data only",
        }
    finally:
        fixture.doCleanups()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional evidence JSON path")
    args = parser.parse_args()
    result = probe()
    body = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding="utf-8")
    print(body, end="")
    return result["open_boundaries"]


if __name__ == "__main__":
    raise SystemExit(main())
