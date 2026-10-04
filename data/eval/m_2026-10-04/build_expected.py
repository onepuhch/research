"""Writes expected.json: a person's reading of the reviewed items, written apart from any validator.

Scope: the 56 items v7 accepted in the 9/29-10/4 runs (source-checked in docs/v7_ops_evaluation_2026-10-04.md
section 3) and the 9 items L2 newly accepted (source-checked in docs/l_handoff_2026-10-04.md section 4),
65 in all. Default reading after the source check: keep the item, every figure is a level, and the
item's own metric/period/subject/kind are right. The exceptions below are the judgments.

    python data/eval/m_2026-10-04/build_expected.py
"""
import gzip
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "scripts"))
import draft_eval  # noqa: E402

LEVEL, CHANGE, EFFECT = ["level"], ["delta"], ["effect_on_metric"]
# (ticker, section, position): what each figure is in the source.
JUDGMENTS = {
    ("AMCX", "claims", 2): {"roles": [LEVEL, CHANGE], "why": "'decreased 9%' is the change of net revenue"},
    ("AEHR", "claims", 1): {"roles": [LEVEL], "why": "'18% to 22% of total revenue' is a ratio level"},
    ("MPC", "claims", 3): {"roles": [["level", "delta"]], "why": "12.5% is the value of a growth metric"},
    ("PBF", "limitations", 0): {"roles": [EFFECT, EFFECT],
                                "why": "special items increased net income by $159.8M ($1.32/share): an effect"},
    ("CLBK", "claims", 1): {"accept": False, "why": "$9.2M is the increase of net interest income ($62.9M level, p20)"},
    ("PUBM", "claims", 0): {"roles": [LEVEL, CHANGE], "why": "'up 11%' is a change"},
    ("FSLY", "claims", 0): {"roles": [LEVEL, CHANGE], "why": "'grew 23%' is a change"},
    ("TEAM", "claims", 0): {"roles": [LEVEL, CHANGE], "why": "'up 28%' is a change"},
    ("TEAM", "claims", 3): {"roles": [["level", "delta"]], "why": "28.5% is the value of a growth metric"},
    ("TEAM", "claims", 4): {"roles": [["level", "delta"]], "why": "(4.0%) is the value of a growth metric"},
    ("TXO", "claims", 4): {"roles": [["described_delta", "level"]],
                           "why": "the figure itself says 'decreased ... by', so no reading mistakes it for a level"},
    ("PSX", "claims", 4): {"subject": "other", "why": "CPChem is a 50/50 joint venture, not a subsidiary"},
}
REVIEWED = {  # (ticker, section, position) of the 65 reviewed items
    "AMCX": [("claims", 2)], "AEHR": [("claims", 0), ("claims", 1)], "DK": [("limitations", 2)],
    "NBR": [("claims", 1), ("claims", 2), ("claims", 3), ("claims", 4), ("limitations", 0), ("limitations", 1)],
    "PBF": [("claims", 0), ("claims", 3), ("limitations", 0)],
    "AXTI": [("claims", 0), ("claims", 1), ("claims", 2), ("claims", 3), ("claims", 4)],
    "MPC": [("claims", 3), ("claims", 4)], "CORT": [("claims", 1), ("claims", 3), ("claims", 4)],
    "RPAY": [("claims", 4)], "PARR": [("limitations", 2)], "CODI": [("claims", 3)], "AGL": [("limitations", 0)],
    "URGN": [("claims", 0), ("claims", 3)],
    "CLBK": [("claims", 0), ("claims", 1), ("claims", 2), ("claims", 3), ("claims", 4), ("limitations", 0),
             ("limitations", 1)],
    "PUBM": [("claims", 0), ("claims", 3), ("limitations", 1), ("limitations", 2)],
    "FSLY": [("claims", 0), ("limitations", 1), ("limitations", 2)],
    "DAN": [("claims", 0), ("claims", 1), ("claims", 2), ("limitations", 0), ("limitations", 1)],
    "TEAM": [("claims", 0), ("claims", 2), ("claims", 3), ("claims", 4)], "SPT": [("limitations", 0), ("limitations", 1)],
    "SUNC": [("claims", 0), ("claims", 1), ("claims", 3)], "PGY": [("claims", 0), ("claims", 4)],
    "TXO": [("claims", 4)], "PSX": [("claims", 4)],
    "CLF": [("claims", 0), ("claims", 1), ("claims", 2), ("claims", 3)],
}


def main():
    fixture = HERE.parent / "l4_2026-10-04"
    with gzip.open(fixture / "audits.json.gz", "rt", encoding="utf-8") as handle:
        records = json.load(handle)
    items = []
    for record in records:
        answer = record.get("answer")
        if not isinstance(answer, dict):
            continue
        for section, position in REVIEWED.get(record["ticker"], []):
            item = answer[section][position]
            judged = JUDGMENTS.get((record["ticker"], section, position), {})
            figures = item.get("figures") or []
            items.append({
                "key": draft_eval.item_key(record, section, position, item), "ticker": record["ticker"],
                "section": section, "position": position, "figures": figures,
                "accept": judged.get("accept", True),
                "roles": judged.get("roles", [LEVEL for _ in figures]),
                "metric": item.get("metric") or None, "period": item.get("period") or "unknown",
                "subject": judged.get("subject", item.get("subject") or "issuer"),
                "kind": item.get("kind") or "fact", "why": judged.get("why", "source-checked: as written")})
    assert len(items) == 65, len(items)
    out = {"schema_version": 1, "reviewed_by": "Claude, 2026-10-04, against the stored source blocks",
           "scope": "56 v7-accepted + 9 L2-accepted items of the 9/29-10/4 runs; a regression baseline only",
           "items": items}
    (HERE / "expected.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(items), "items")


if __name__ == "__main__":
    main()
