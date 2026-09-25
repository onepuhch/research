"""Official company documents linked to screener candidates (G1), and drafts from them (G2).

Targets come from the latest valid screener snapshot in the shared A/B display
order, not from the cards (cards read this step's output; no cycle). A stale or
partial screen means no new outside research; stored results stay readable.

Issuer: the SEC CIK from the snapshot row, else the cached official SEC list by
exact ticker + exchange. Names are never matched. The CIK is an extra mapping: it
does not replace entity_id or CAN IDs. A CIK different from the registry's is an
identity_conflict and is held.

Order: never-researched candidates by first seen (oldest first), then display
order, then ID; at most companies_per_day a KST day, so a long queue rotates.
Revisit: 7 days after research or when the estimate period/value changed;
technical failure after 24 hours; 'no relevant document' after 7 days.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402
import company_filings as cf  # noqa: E402

STATUSES = ("queued", "success", "no_relevant_document", "unavailable", "failed", "deferred_budget", "identity_conflict")
DEFAULTS = {"companies_per_day": 10, "filings_per_company": 5, "documents_per_company": 3,
            "http_attempts_per_day": 100, "time_budget_s": 180, "timeout_s": 15, "max_document_bytes": 2_000_000,
            "lookback_days": 120, "revisit_days": 7, "retry_failed_hours": 24, "no_document_days": 7}


def settings() -> dict:
    return {**DEFAULTS, **c.policy().get("candidate_context", {})}


def state_path() -> Path:
    return c.DATA_DIR / "candidate_context_state.json"


def load_state() -> dict:
    state = c.read_json(state_path(), {"candidates": {}, "days": {}, "documents_by_source": {}})
    for key in ("candidates", "days", "documents_by_source"):
        state.setdefault(key, {})
    return state


def load_issuers() -> dict:
    import screen_revisions
    path = screen_revisions.issuers_path()
    if not path.exists():
        return {}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


# ------------------------------------------------------------------ targets

def issuer_for(row: dict, registry: dict, issuers: dict) -> tuple[dict | None, str | None]:
    """(issuer, problem). Problem is 'unavailable' or 'identity_conflict'."""
    ticker, exchange = row["ticker"], row.get("exchange")
    source = None
    if row.get("cik"):
        cik, source = row["cik"], "screen snapshot (SEC company_tickers_exchange)"
    else:
        cached = (issuers.get("issuers") or {}).get(ticker)
        if not cached or not exchange or cached.get("exchange") != exchange:
            return None, "unavailable"
        cik, source = cached["cik"], "cached SEC company_tickers_exchange"
    cik = cf.cik10(cik)
    known = [a for a in (registry.get(ticker) or {}).get("aliases", []) if a.startswith("CIK:")]
    if known and f"CIK:{cik}" not in known:
        return None, "identity_conflict"
    return {"cik": cik, "ticker": ticker, "exchange": exchange, "name": row.get("name"),
            "mapping_source": source, "mapping_sha256": (issuers.get("source") or {}).get("sha256"),
            "mapping_observed_at": (issuers.get("source") or {}).get("observed_at")}, None


def targets(snapshot: dict, registry: dict, issuers: dict, first_seen: dict) -> list[dict]:
    import candidates
    rows = {r["ticker"]: r for r in snapshot.get("derived", {}).get("rows", []) if r.get("candidate")}
    out = []
    for position, (ticker, _) in enumerate(candidates.display_order(snapshot.get("derived", {})), 1):
        row = rows.get(ticker)
        if row is None:
            continue
        identity = candidates.identify(row, registry)
        if not identity["entity_id"]:
            continue
        cid = candidates.candidate_id(identity["entity_id"])
        issuer, problem = issuer_for(row, registry, issuers)
        out.append({"candidate_id": cid, "ticker": ticker, "entity_id": identity["entity_id"], "rank": position,
                    "first_seen_at": first_seen.get(cid) or snapshot["run"]["finished_at"],
                    "eps_key": f"{row.get('eps_target_period')}|{row.get('eps_now')}",
                    "eps_target_period": row.get("eps_target_period"), "issuer": issuer, "problem": problem})
    return out


def eligible(entry: dict | None, target: dict, now: datetime) -> bool:
    if not entry or entry.get("status") in ("queued", "deferred_budget"):
        return True
    if entry.get("status") == "success" and entry.get("eps_key") != target["eps_key"]:
        return True  # the estimate or its fiscal year changed
    due = entry.get("next_eligible_at")
    return due is None or datetime.fromisoformat(due) <= now


def select(all_targets: list[dict], state: dict, now: datetime, limit: int) -> list[dict]:
    pool = [t for t in all_targets if eligible(state["candidates"].get(t["candidate_id"]), t, now)]
    pool.sort(key=lambda t: (state["candidates"].get(t["candidate_id"], {}).get("status") == "success",
                             t["first_seen_at"], t["rank"], t["candidate_id"]))
    return pool[:limit]


# ------------------------------------------------------------------ research

def research(target: dict, client: cf.SecClient, state: dict, now: datetime, cfg: dict) -> dict:
    """One company's recent filings: returns {status, document_ids, notes}; raises Budget/Blocked."""
    issuer = dict(target["issuer"])
    observed = now.isoformat(timespec="seconds")
    try:
        body, _, _ = client.get(cf.submissions_url(issuer["cik"]))
    except HTTPError as error:
        return {"status": "unavailable" if error.code == 404 else "failed", "document_ids": [],
                "notes": [f"submissions HTTP {error.code}"]}
    submissions = json.loads(body.decode("utf-8"))
    issuer["name"] = submissions.get("name") or issuer.get("name")
    filings = cf.recent_filings(submissions, now.date(), cfg["lookback_days"])[:cfg["filings_per_company"]]
    found, examined, notes, bodies = [], [], [], 0
    for filing in filings:
        if bodies >= cfg["documents_per_company"]:
            break
        index_url = cf.filing_index_url(issuer["cik"], filing["accessionNumber"])
        try:
            page, final, _ = client.get(index_url)
        except HTTPError as error:
            notes.append(f"{filing['accessionNumber']} index HTTP {error.code}")
            continue
        base = final.rsplit("/", 1)[0] + "/"
        for doc in cf.pick_documents(cf.filing_documents(page.decode("utf-8", "replace"), base), filing["form"]):
            if bodies >= cfg["documents_per_company"]:
                break
            key = f"{filing['accessionNumber']}|{doc['url']}"
            cached = state["documents_by_source"].get(key)
            record = cf.load_document(cached) if cached else None
            if record is None:
                try:
                    raw, final_url, truncated = client.get(doc["url"])
                except HTTPError as error:
                    notes.append(f"{doc['name']} HTTP {error.code}")
                    continue
                bodies += 1
                record = cf.build_record(issuer, filing, doc, raw, final_url, truncated, observed)
                cf.store_document(record)
                state["documents_by_source"][key] = record["document_id"]
            examined.append(record["document_id"])
            if record["relevance"]["earnings"]:
                found.append(record["document_id"])
                break  # one results document per filing
    if found:
        return {"status": "success", "document_ids": found, "examined": examined, "notes": notes}
    if not filings:
        notes.append(f"no 8-K/6-K results or periodic report in {cfg['lookback_days']} days")
    return {"status": "no_relevant_document", "document_ids": [], "examined": examined, "notes": notes}


def screen_ready(now: datetime) -> tuple[dict | None, list[str]]:
    """The latest valid snapshot, and why new outside research must wait (stale or partial)."""
    import candidates
    import screen_revisions
    choice = candidates.choose_snapshot(list(screen_revisions.SCREEN_DIR.glob("*.json.gz")), now,
                                        candidates.settings()["stale_hours"])
    if not choice["valid"]:
        return None, ["no_valid_screen"]
    snapshot = choice["valid"]["snapshot"]
    reasons = list(choice["stale"])
    reasons += candidates.screen_attempt_stale(c.read_json(c.DATA_DIR / "daily_runs.json", {}),
                                               snapshot["run"].get("run_id"))
    if snapshot["run"].get("status") != "success":
        reasons.append("partial_screen")
    return snapshot, list(dict.fromkeys(reasons))


def run_sources(now: datetime | None = None, client: cf.SecClient | None = None) -> dict:
    import candidates
    now = now or datetime.now(timezone.utc)
    cfg = settings()
    day = now.astimezone(candidates.KST).date().isoformat()
    state = load_state()
    usage = state["days"].setdefault(day, {"companies": 0, "http_attempts": 0})
    snapshot, hold = screen_ready(now)
    report = {"day": day, "held": hold, "researched": 0, "statuses": {}}
    if snapshot is None or hold:
        c.atomic_json(state_path(), state)
        return report
    first_seen = {cid: item["first_seen_at"] for cid, item in candidates.known_candidates().items()}
    all_targets = targets(snapshot, c.read_json(c.ROOT / "config" / "entities.json", {}), load_issuers(), first_seen)
    report["targets"] = len(all_targets)
    for t in all_targets:  # identity problems are recorded without any request
        if t["problem"]:
            entry = state["candidates"].setdefault(t["candidate_id"], {})
            if entry.get("status") != t["problem"]:
                entry.update(status=t["problem"], ticker=t["ticker"], attempted_at=now.isoformat(timespec="seconds"),
                             next_eligible_at=(now + timedelta(days=cfg["no_document_days"])).isoformat(timespec="seconds"))
    ready = [t for t in all_targets if not t["problem"]]
    slots = max(0, cfg["companies_per_day"] - usage["companies"])
    chosen = select(ready, state, now, slots)
    user_agent = os.environ.get("SEC_USER_AGENT") or "investment-research-system/2.0 research-bot"
    client = client or cf.SecClient(user_agent=user_agent,
                                    attempts_left=max(0, cfg["http_attempts_per_day"] - usage["http_attempts"]),
                                    deadline=time.monotonic() + cfg["time_budget_s"], timeout_s=cfg["timeout_s"],
                                    max_bytes=cfg["max_document_bytes"])
    for target in chosen:
        entry = state["candidates"].setdefault(target["candidate_id"], {})
        before = client.attempts
        try:
            result = research(target, client, state, now, cfg)
        except cf.Budget as error:
            # Not a failure: nothing more is sent today; the next run continues from here.
            entry.update(status="deferred_budget", note=str(error), ticker=target["ticker"], next_eligible_at=None)
            usage["http_attempts"] += client.attempts - before
            break
        except cf.Blocked as error:
            entry.update(status="failed", note=str(error), ticker=target["ticker"],
                         next_eligible_at=(now + timedelta(hours=cfg["retry_failed_hours"])).isoformat(timespec="seconds"))
            usage["http_attempts"] += client.attempts - before
            report["blocked"] = True
            break
        except (URLError, TimeoutError, OSError, ValueError) as error:
            result = {"status": "failed", "document_ids": [], "notes": [type(error).__name__]}
        usage["http_attempts"] += client.attempts - before
        usage["companies"] += 1
        wait = {"success": timedelta(days=cfg["revisit_days"]), "failed": timedelta(hours=cfg["retry_failed_hours"])}
        entry.update(status=result["status"], ticker=target["ticker"], issuer=target["issuer"],
                     attempted_at=now.isoformat(timespec="seconds"), eps_key=target["eps_key"],
                     eps_target_period=target["eps_target_period"], document_ids=result["document_ids"],
                     examined=result.get("examined", []), notes=result["notes"],
                     next_eligible_at=(now + wait.get(result["status"], timedelta(days=cfg["no_document_days"])))
                     .isoformat(timespec="seconds"))
        report["researched"] += 1
        report["statuses"][result["status"]] = report["statuses"].get(result["status"], 0) + 1
        c.atomic_json(state_path(), state)
    for t in ready:
        state["candidates"].setdefault(t["candidate_id"], {"status": "queued", "ticker": t["ticker"]})
    c.atomic_json(state_path(), state)
    report["http_attempts"] = usage["http_attempts"]
    report["coverage"] = coverage(state, [t["candidate_id"] for t in all_targets])
    return report


def coverage(state: dict, ids: list[str]) -> dict:
    counts: dict[str, int] = {}
    for cid in ids:
        status = state["candidates"].get(cid, {}).get("status", "queued")
        counts[status] = counts.get(status, 0) + 1
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args(argv)
    try:
        report = run_sources()
    except (OSError, ValueError, KeyError) as error:
        c.record_run("candidate_context", "failed", error_type=type(error).__name__)
        print(f"[context] failed: {type(error).__name__}")
        return 1
    status = "held" if report["held"] else ("degraded" if report["statuses"].get("failed") else "success")
    c.record_run("candidate_context", status, **{k: v for k, v in report.items() if k != "day"})
    print(f"[context] {json.dumps(report, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
