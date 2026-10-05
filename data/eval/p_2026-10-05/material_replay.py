"""P2 dry-run: which known candidates would the re-review rule have raised since the bootstrap?

Read-only replay of the stored daily screens after the bootstrap (no sending, no ledger write):
each snapshot becomes a pseudo index (shown cards plus industry-folded companies) and
material_updates.evaluate runs with its state carried from day to day. Nothing is announced, so a
baseline only moves by rebase; announced events in the real ledger are used as they are.
Trigger A uses the current context state only on the last snapshot (earlier days would otherwise
see documents collected later). Pseudo cards are complete by assumption (no price/quality check).

    python data/eval/p_2026-10-05/material_replay.py [output.json]
"""
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import candidate_alerts as a  # noqa: E402
import candidate_context  # noqa: E402
import candidates  # noqa: E402
import material_updates as m  # noqa: E402
import screen_revisions  # noqa: E402

OUT = Path(__file__).resolve().parent / "material_replay.json"


def entities(ledger: dict) -> dict[str, str]:
    keys = list((ledger.get("bootstrap") or {}).get("keys") or []) + list(ledger["events"])
    return {key.split("|")[0].split(":", 1)[1]: key.split("|")[0] for key in keys if ":" in key.split("|")[0]}


def pseudo_index(path: Path, names: dict[str, str]) -> dict:
    raw = path.read_bytes()
    snap = json.loads(gzip.decompress(raw))
    derived = snap["derived"]
    rows = {r["ticker"]: r for r in derived["rows"] if r.get("candidate")}
    shown = [t for t, _ in candidates.display_order(derived)]
    folded = [t for g in derived.get("industry_groups") or [] for t in g.get("folded", []) if t not in shown]
    ref = {"path": f"data/processed/revision_screen/{path.name}", "sha256": __import__("hashlib").sha256(raw).hexdigest(),
           "run_id": snap["run"]["run_id"], "finished_at": snap["run"]["finished_at"]}

    def card(ticker, state):
        r = rows[ticker]
        return {"candidate_id": f"replay-{ticker}", "identity": {"entity_id": names.get(ticker, f"?:{ticker}"), "ticker": ticker},
                "thesis_key": candidates.THESIS_KEY, "name": r.get("name"), "industry": r.get("industry"),
                "eps": {k: r.get(k) for k in candidates.VERSION_EPS_KEYS}, "eps_provider": m.SCREEN_PROVIDER,
                "observation_id": f"replay:{ref['run_id']}:{ticker}", "missing": [], "run_quality": "complete",
                "tracking": {"status": "untracked"}, "display_state": state}
    return {"source_snapshot": ref, "observed_at": ref["finished_at"], "run_status": "success",
            "candidates": [card(t, "card") for t in shown if t in rows],
            "folded_candidates": [card(t, "industry_folded") for t in folded if t in rows]}


def main() -> int:
    ledger = a.load_ledger()
    ledger = {**ledger, "material": m.empty_state()}  # replay from no pending state (Q: the live ledger has one)
    names = entities(ledger)
    boot = ledger["bootstrap"]["source_snapshot"]["finished_at"]
    paths = [p for p in screen_revisions.snapshots() if p.name[:16] > Path(ledger["bootstrap"]["source_snapshot"]["path"]).name[:16]]
    context = candidate_context.load_state()
    timeline, first_eligible, last = [], {}, []
    for i, path in enumerate(paths):
        index = pseudo_index(path, names)
        state_ctx = context if i == len(paths) - 1 else {"candidates": {}}
        items, diagnostics, state = m.evaluate(index, ledger, state_ctx)
        ledger = {**ledger, "material": state}
        day = m.kst_day(index["source_snapshot"]["finished_at"])
        for item in items:
            first_eligible.setdefault(item["entity_id"], {"day": day, "triggers": item["material"]["triggers"],
                                                          "pct": item["material"]["pct"]})
        timeline.append({"snapshot": path.name, "kst_day": day, "eligible": [x["entity_id"] for x in items],
                         "pending": sorted(state["pending"]), "known": sum(d["decision"] != "not_known" for d in diagnostics)})
        last = diagnostics
    known = [d for d in last if d["decision"] != "not_known"]
    result = {"bootstrap_finished_at": boot, "snapshots": [p.name for p in paths], "timeline": timeline,
              "first_eligible": first_eligible, "last_day_known": known,
              "cancelled": ledger["material"]["cancelled"], "rebases": ledger["material"]["rebases"]}
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({"snapshots": len(paths), "known_last_day": len(known), "first_eligible": first_eligible,
                      "cancelled": len(result["cancelled"]), "rebases": len(result["rebases"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
