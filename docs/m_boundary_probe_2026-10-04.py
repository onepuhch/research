"""Synthetic role-boundary probes for the L acceptance review; no network or state writes.

Run from any directory with Python 3.11+:
    python docs/m_boundary_probe_2026-10-04.py

Exit 1 means a claim's acceptance differs from the intended behavior. These are
review probes, not reported Python test results: the reviewing environment had
no accessible Python interpreter. Keep real-source L4 cases as separate tests.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import candidate_context as ctx  # noqa: E402


CASES = [
    {
        "id": "effect_before_target_metric",
        "quote": "A one-time tax benefit of $12 million increased net income in 2026.",
        "metric": "net income", "figures": ["$12 million"], "accept": False,
    },
    {
        "id": "amount_and_percentage_in_one_figure",
        "quote": ("Net interest income was $62.9 million in 2026, an increase of "
                  "$9.2 million, or 17.2%."),
        "metric": "net interest income", "figures": ["$9.2 million, or 17.2%"], "accept": False,
    },
    {
        "id": "effect_itself_as_metric",
        "quote": "A one-time tax benefit of $12 million increased net income in 2026.",
        "metric": "tax benefit", "figures": ["$12 million"], "accept": True,
    },
    {
        "id": "true_level_beside_effect",
        "quote": "A tax benefit of $12 million increased net income to $50 million in 2026.",
        "metric": "net income", "figures": ["$50 million"], "accept": True,
    },
]


def main():
    mismatches = 0
    for case in CASES:
        item = {
            "kind": "fact", "subject": "issuer", "metric": case["metric"],
            "figures": case["figures"], "period": "2026", "currency": "USD", "gaap": "unknown",
            "note_ko": "원문에 기재된 내용입니다.", "quote": case["quote"],
            "document_id": "DOC-SYNTHETIC", "block_id": "p1",
            "drivers": ["unknown"], "direction": "unknown",
        }
        result = ctx.validate_draft(
            {"claims": [item], "link": "unconfirmed"},
            [{"document_id": "DOC-SYNTHETIC", "block_id": "p1", "text": case["quote"]}],
            {"ticker": "SYNTH", "name": "Synthetic Company"},
        )
        accepted = bool(result["claims"])
        mismatches += accepted != case["accept"]
        print(json.dumps({
            "id": case["id"], "synthetic": True, "parser": ctx.PARSER_VERSION,
            "expected_accept": case["accept"], "actual_accept": accepted,
            "claims": result["claims"], "rejected": result["rejected"],
        }, ensure_ascii=False))
    return int(mismatches > 0)


if __name__ == "__main__":
    raise SystemExit(main())
