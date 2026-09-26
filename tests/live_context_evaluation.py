"""I3-2/J1: count what one regular daily run did with candidate drafts, read-only and offline.

    python tests/live_context_evaluation.py 2026-09-27 [--audit <downloaded artifact>/context_audit/2026-09-27]

Reads the persisted research state (after `git pull`), the model budget of that KST day, the CTX
records generated that day and, when given, the run's pre-validation audit copies. No request,
no write. Counts only: comparing drafts with their sources stays a human step.
"""
import argparse
import json
import pathlib
import sys
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import candidate_context as ctx  # noqa: E402
import common as c  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("day")
    parser.add_argument("--audit", type=pathlib.Path)
    args = parser.parse_args(argv)
    budget = c.read_json(c.DATA_DIR / "model_budget.json", {}).get("days", {}).get(args.day, {})
    state = ctx.load_state()
    usage = state.get("days", {}).get(args.day, {})
    records = []
    for path in sorted(ctx.history_dir().glob("CTX-*.json")):
        record = c.read_json(path, {})
        if (record.get("generated_at") or "").startswith(args.day) or (
                record.get("generated_at", "") >= args.day and record.get("parser_version") == ctx.PARSER_VERSION):
            records.append(record)
    records = [r for r in records if r.get("parser_version") == ctx.PARSER_VERSION]
    print(f"# {args.day} candidate_context")
    print(f"model budget (KST day): {budget}")
    print(f"SEC usage: {usage}")
    print("draft status by company:", dict(Counter(e.get("draft_status") or "-" for e in state["candidates"].values())))
    print(f"{ctx.PARSER_VERSION} records: {len(records)}")
    for r in records:
        core = [x for x in r.get("claims") or [] if x.get("core") and x.get("kind") in ("fact", "guidance")]
        print(f"- {r['context_id']} {r.get('ticker')} {r['context_status']} accepted={len(r.get('claims') or [])} "
              f"core={len(core)} rejected={dict(Counter(x['reason'] for x in r.get('rejected') or []))}")
        for x in r.get("claims") or []:
            print(f"    [{x['kind']}{' core' if x.get('core') else ''}] {x.get('text_ko')}")
    if args.audit:
        audits = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(args.audit.glob("*.json"))]
        print(f"audit copies: {len(audits)} outcomes={dict(Counter(a.get('outcome') for a in audits))} "
              f"requests_sent={sum((a.get('budget') or {}).get('requests_sent', 0) for a in audits)} "
              f"raw_available={sum((a.get('raw_response') or {}).get('available', False) for a in audits)} "
              f"truncated={sum(bool(a.get('truncated')) for a in audits)} code={sorted({a.get('code_sha') for a in audits})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
