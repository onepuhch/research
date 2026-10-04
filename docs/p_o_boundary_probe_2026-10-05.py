"""Read-only O3 boundary probes; synthetic inputs, no model/network/state writes.

Run before and after P1: python docs/p_o_boundary_probe_2026-10-05.py
Exit 1 means at least one boundary still differs from the expected behavior.
The download-budget path needs the separate fake-client research test in the P spec.
"""
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import company_filings as cf  # noqa: E402


def main():
    cases = [
        ("dividend_with_two_update_words", False,
         "The board increases the quarterly dividend to $0.25 per share and expects payment in October."),
        ("credit_capacity_is_not_operating_capacity", False,
         "The company entered into a credit agreement with borrowing capacity of $500 million."),
        ("real_customer_contract_and_guidance", True,
         "AAA Inc. raises fiscal 2027 revenue guidance to $150 million after signing a multi-year "
         "supply agreement with a new customer. The agreement adds $40 million of backlog."),
    ]
    mismatches = 0
    for name, expected, source in cases:
        blocks = cf.normalize_html(f"<html><body><p>{source}</p></body></html>".encode())
        actual, reason = cf.looks_like_business_update(blocks)
        print(json.dumps({"id": name, "synthetic": True, "expected": expected,
                          "actual": actual, "reason": reason}, ensure_ascii=False))
        mismatches += actual != expected
    # The current picker omits an 8-K's main document even when it has no EX-99.
    main_doc = {"description": "Current report with material supply agreement", "type": "8-K",
                "name": "report.htm", "url": "https://www.sec.gov/Archives/synthetic/report.htm"}
    actual = main_doc in cf.pick_documents([main_doc], "8-K")
    print(json.dumps({"id": "main_8k_without_exhibit_can_be_examined", "synthetic": True,
                      "expected": True, "actual": actual}, ensure_ascii=False))
    mismatches += not actual
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
