"""I3-2/J1: count what one regular daily run did with candidate drafts, read-only and offline.

    python tests/live_context_evaluation.py 2026-09-27 --audit <artifact>/context_audit/2026-09-27 \
        [--run-id <GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>]

Reads the persisted research state (after `git pull`), the model budget of that KST day, the CTX
records and, when given, the run's pre-validation audit copies. No request, no write.

- A day is the KST day [00:00, next 00:00), compared as UTC datetimes; a time without a zone or
  unreadable is counted as 'time unknown', never guessed.
- Run results come from that run's audit copies (attempt_id counted once) and the CTX records they
  name. The current candidate state is shown as the current queue, not as a past run's result.
- Whether the run was a normal daily run (event, mode, success, checkout SHA) is GitHub evidence
  and is written in the evaluation document; the audit alone does not show it.
Counts only: comparing drafts with their sources stays a human step.
"""
import argparse
import json
import pathlib
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import candidate_context as ctx  # noqa: E402
import common as c  # noqa: E402

KST = timezone(timedelta(hours=9))


def kst_window(day: str) -> tuple[datetime, datetime]:
    start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=KST)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def parse_time(value) -> datetime | None:
    """Aware datetimes only: a naive or broken time is unknown, not assumed to be UTC or KST."""
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else None


def in_day(value, window) -> str:
    moment = parse_time(value)
    if moment is None:
        return "unknown"
    return "in" if window[0] <= moment < window[1] else "out"


def raw_state(audit: dict) -> str:
    raw = audit.get("raw_response")
    if not isinstance(raw, dict):
        return "missing"
    if raw.get("dropped"):
        return "dropped"  # over the size cap: only a hash is left
    return "available" if raw.get("available") and isinstance(raw.get("text"), str) else "none"


def read_audits(folder: pathlib.Path | None) -> tuple[list[dict], int]:
    if folder is None or not folder.is_dir():
        return [], 0
    audits, unreadable = [], 0
    for path in sorted(folder.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            unreadable += 1
            continue
        if isinstance(record, dict):
            audits.append(record)
        else:
            unreadable += 1
    return audits, unreadable


def attempt_summary(audit: dict, contexts: dict) -> dict:
    validation = audit.get("validation")
    usable = isinstance(validation, dict) and not validation.get("dropped")
    claims = (validation.get("claims") or []) if usable else []
    context_id = audit.get("context_id")
    return {"attempt_id": audit.get("attempt_id"), "ticker": audit.get("ticker"), "outcome": audit.get("outcome"),
            "started_at": audit.get("started_at"), "run_id": audit.get("run_id"),
            "parser_version": audit.get("parser_version"), "code_sha": audit.get("code_sha"),
            "requests_sent": (audit.get("budget") or {}).get("requests_sent", 0) if isinstance(audit.get("budget"), dict) else 0,
            "raw": raw_state(audit), "truncated": bool(audit.get("truncated")),
            "status": validation.get("context_status") if usable else None,
            "accepted": len(claims) if usable else None,
            "core": sum(1 for x in claims if x.get("core") and x.get("kind") in ("fact", "guidance")) if usable else None,
            "rejected": dict(Counter(x.get("reason") for x in validation.get("rejected") or [])) if usable else None,
            "error": audit.get("error") or audit.get("validation_error"),
            "context_id": context_id, "ctx_stored": audit.get("ctx_stored"),
            "ctx_found": context_id in contexts if context_id else None}


def aggregate(attempts: list[dict]) -> dict:
    return {"attempts": len(attempts), "outcomes": dict(Counter(a["outcome"] for a in attempts)),
            "requests_sent": sum(a["requests_sent"] or 0 for a in attempts),
            "raw": dict(Counter(a["raw"] for a in attempts)), "truncated": sum(a["truncated"] for a in attempts),
            "by_parser": dict(Counter(a["parser_version"] or "unknown" for a in attempts)),
            "statuses": dict(Counter(a["status"] or "-" for a in attempts)),
            "accepted": sum(a["accepted"] or 0 for a in attempts), "core": sum(a["core"] or 0 for a in attempts),
            "code_sha": sorted({a["code_sha"] for a in attempts}, key=lambda x: (x is None, str(x)))}


def collect(day: str, audit_dir: pathlib.Path | None = None, run_id: str | None = None) -> dict:
    window = kst_window(day)
    contexts, ctx_days = {}, Counter()
    by_parser_day: Counter = Counter()
    for path in sorted(ctx.history_dir().glob("CTX-*.json")):
        record = c.read_json(path, {})
        if not isinstance(record, dict) or not record.get("context_id"):
            continue
        contexts[record["context_id"]] = record
        where = in_day(record.get("generated_at"), window)
        ctx_days[where] += 1
        if where == "in":
            by_parser_day[record.get("parser_version") or "unknown"] += 1
    audits, unreadable = read_audits(audit_dir)
    seen, unique, duplicates = set(), [], 0
    for audit in audits:
        key = audit.get("attempt_id")
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        unique.append(audit)
    attempts = [attempt_summary(a, contexts) for a in unique]
    day_times = Counter(in_day(a["started_at"], window) for a in attempts)
    of_day = [a for a in attempts if in_day(a["started_at"], window) == "in"]
    of_run = [a for a in attempts if run_id and a["run_id"] == run_id]
    budget_day = c.read_json(c.DATA_DIR / "model_budget.json", {}).get("days", {}).get(day, {})
    state = ctx.load_state()
    return {
        "day": day, "window_utc": [x.isoformat() for x in window], "run_id": run_id,
        "audit_dir": str(audit_dir) if audit_dir else None,
        "audit_evidence": ("missing" if not audits else
                           "incomplete" if unreadable or any(a["truncated"] or a["raw"] in ("dropped", "missing")
                                                             for a in attempts) else "complete"),
        "audit_files": len(audits), "audit_unreadable": unreadable, "audit_duplicates": duplicates,
        "audit_day_times": dict(day_times),
        "run": aggregate(of_run) if run_id else None,
        "run_excluded_other_runs": sum(1 for a in attempts if run_id and a["run_id"] != run_id),
        "run_outside_day": [(a["attempt_id"], a["started_at"]) for a in of_run
                            if in_day(a["started_at"], window) != "in"],
        "day_summary": aggregate(of_day) | {"runs": dict(Counter(a["run_id"] or "unknown" for a in of_day))},
        "attempts": of_run if run_id else of_day,
        "model_budget_day": budget_day,
        "budget_vs_audit": {"model_budget_candidate_context": budget_day.get("candidate_context"),
                            "audit_requests_day": sum(a["requests_sent"] or 0 for a in of_day),
                            "audit_requests_run": sum(a["requests_sent"] or 0 for a in of_run) if run_id else None,
                            "note": "the day's budget can include other runs of the same KST day"},
        "ctx_generated": {"in_day": ctx_days["in"], "out_of_day": ctx_days["out"], "time_unknown": ctx_days["unknown"],
                          "in_day_by_parser": dict(by_parser_day)},
        "current_queue": dict(Counter((e or {}).get("draft_status") or "-" for e in state.get("candidates", {}).values())),
        "sec_usage_day": state.get("days", {}).get(day, {}),
    }


def render(result: dict) -> str:
    lines = [f"# {result['day']} candidate_context (KST {result['window_utc'][0]} ~ {result['window_utc'][1]} UTC)",
             f"audit: {result['audit_evidence']} files={result['audit_files']} unreadable={result['audit_unreadable']} "
             f"duplicates={result['audit_duplicates']} start times={result['audit_day_times']}"]
    if result["run"] is not None:
        lines.append(f"run {result['run_id']}: {result['run']} (other runs excluded: {result['run_excluded_other_runs']})")
        if result["run_outside_day"]:
            lines.append(f"  attempts of this run outside the KST day: {result['run_outside_day']}")
    lines.append(f"KST day (all runs): {result['day_summary']}")
    lines += [f"budget vs audit: {result['budget_vs_audit']}", f"model budget (KST day): {result['model_budget_day']}",
              f"CTX generated: {result['ctx_generated']}",
              f"current queue (not a past run's result): {result['current_queue']}",
              f"SEC usage: {result['sec_usage_day']}", "attempts:"]
    for a in result["attempts"]:
        lines.append(f"- {a['attempt_id']} {a['ticker']} {a['outcome']} {a['parser_version']} status={a['status']} "
                     f"accepted={a['accepted']} core={a['core']} requests={a['requests_sent']} raw={a['raw']} "
                     f"ctx={a['context_id']} stored={a['ctx_stored']} found={a['ctx_found']} error={a['error']} "
                     f"rejected={a['rejected']}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("day")
    parser.add_argument("--audit", type=pathlib.Path)
    parser.add_argument("--run-id", help="GITHUB_RUN_ID-GITHUB_RUN_ATTEMPT, as written in the audit copies")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = collect(args.day, args.audit, args.run_id)
    print(json.dumps(result, ensure_ascii=False, indent=1) if args.json else render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
