"""Q acceptance: five cases in three follow-up areas. Synthetic inputs and fake sends/HTTP only.

python -X utf8 docs/r_q_boundary_probe_2026-10-05.py
Exit 1: at least one boundary is open. No production records or external services are changed.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]

import candidate_context
import material_updates as material
from test_p2_material import MaterialFixture
from test_q3_prices import PriceQueueTest


def guidance_case(name, current, prior=None):
    f = MaterialFixture()
    try:
        f.setUp()
        ledger = f.boot(eps=1.0)
        index = f.screen("2026-10-10", eps=1.0)
        if prior:
            f.update_doc("2026-09-20", doc_id="DOC-OLD", text=prior)
        f.update_doc("2026-10-09", text=current)
        items, diagnostics, _ = material.evaluate(index, ledger, candidate_context.load_state())
        documents = [d for item in items for d in item["material"]["documents"]]
        result = {"case": name, "expected": "no_A_alert", "actual": "A_alert" if items else "no_A_alert",
                  "current_sentence": current, "prior_sentence": prior,
                  "accepted_documents": documents, "fixed": not items}
    finally:
        f.doCleanups()
    return result


def failed_composite_lapse():
    f = MaterialFixture()
    try:
        f.setUp()
        f.boot(eps=1.0)
        f.screen("2026-10-10", eps=1.3)
        f.send_alerts()
        f.screen("2026-10-11", eps=1.3)
        f.update_doc("2026-10-10")
        f.outcomes = ["failed"]
        f.send_alerts()
        before = f.material_events()[0]
        f.screen("2026-10-12", eps=1.0)  # B lapsed; A still matches a part of the failed event
        f.send_alerts()
        after = f.material_events()[0]
        stale_sent = after["status"] == "sent" and "B" in after["material"]["triggers"]
        result = {"case": "failed_AB_retries_after_B_lapses", "expected": "no_stale_B_send",
                  "before_status": before["status"], "before_triggers": before["material"]["triggers"],
                  "after_status": after["status"], "after_triggers": after["material"]["triggers"],
                  "latest_eps": 1.0, "payload_eps": after["material"]["current"]["eps_now"],
                  "fake_sent_count": len(f.sent), "fixed": not stale_sent}
    finally:
        f.doCleanups()
    return result


def price_queue_starvation():
    f = PriceQueueTest()
    try:
        f.setUp()
        f.build(25)
        f.answers = {f"T{i:02d}": 404 for i in range(19)}
        first = f.collect("2026-10-10T03:00:00+00:00")
        first_calls = list(f.calls)
        f.calls.clear()
        second = f.collect("2026-10-11T03:00:00+00:00")
        second_calls = list(f.calls)
        result = {"case": "failed_price_heads_starve_later_candidates", "expected": "later_untried_progress",
                  "day_one": first, "day_two": second, "day_one_calls": first_calls,
                  "day_two_calls": second_calls, "fixed": "T19" in first_calls + second_calls}
    finally:
        f.doCleanups()
    return result


def main():
    results = [
        guidance_case("old_guidance_retold_in_new_release",
                      "On September 1, 2026, AAA raised fiscal 2027 revenue guidance from $130 million to $150 million."),
        guidance_case("quarter_used_as_annual_prior",
                      "AAA raises fiscal 2027 revenue guidance to $150 million.",
                      "AAA expects third-quarter 2027 revenue of $130 million."),
        guidance_case("another_entity_used_as_prior",
                      "AAA raises fiscal 2027 revenue guidance to $150 million.",
                      "Other Buyer LLC CONSOLIDATED STATEMENTS OF OPERATIONS. "
                      "Other expects fiscal 2027 revenue of $130 million."),
        failed_composite_lapse(), price_queue_starvation(),
    ]
    print(json.dumps({"review_baseline": "2858c90", "probes": results,
                      "open_boundaries": sum(not x["fixed"] for x in results)}, ensure_ascii=True, indent=2))
    return int(any(not x["fixed"] for x in results))


if __name__ == "__main__":
    raise SystemExit(main())
