"""N1: where candidates of the 9/29-10/4 KST daily runs go, from stored data only (read-only).

    python data/eval/n_2026-10-04/export_inputs.py          # writes funnel.json and input_hashes.json here

Counts each stage on its own denominator; runs, attempts, CTX records and companies are never mixed.
No network, no model, no write outside this folder. Job-log figures (EDGAR prefilter) are copied from
the GitHub Actions logs into LOG_FIGURES below, with the run they came from.
"""
import csv
import gzip
import hashlib
import json
import pathlib
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DATA = ROOT / "data" / "processed"
sys.path.insert(0, str(ROOT / "scripts"))
import candidates  # noqa: E402  (display_order only; nothing is generated)

KST = timezone(timedelta(hours=9))
RUNS = {  # KST day -> (daily run, screen snapshot) of the regular daily run that day
    "2026-09-29": ("36528079469-1", "20260929T055354Z_36528079469-1.json.gz"),
    "2026-09-30": ("36674489444-1", "20260930T054134Z_36674489444-1.json.gz"),
    "2026-10-01": ("36822997450-1", "20261001T060811Z_36822997450-1.json.gz"),
    "2026-10-02": ("36880974655-1", "20261001T150156Z_36880974655-1.json.gz"),  # 00:01 KST 10/2 (PC timer)
    "2026-10-03": ("37099766046-1", "20261003T052857Z_37099766046-1.json.gz"),
    "2026-10-04": ("37181539693-1", "20261004T060125Z_37181539693-1.json.gz"),
}
# '[prefilter] Gemini candidates: n/m' and '[collected] EDGAR: n' of each run's job log (read 2026-10-04).
LOG_FIGURES = {
    "2026-09-29": {"collected_edgar": 27, "collected_rss": 0, "model_candidates": 8},
    "2026-09-30": {"collected_edgar": 24, "collected_rss": 0, "model_candidates": 2},
    "2026-10-01": {"collected_edgar": 25, "collected_rss": 0, "model_candidates": 6},
    "2026-10-02": {"collected_edgar": 25, "collected_rss": 0, "model_candidates": 0},
    "2026-10-03": {"collected_edgar": 23, "collected_rss": 0, "model_candidates": 10},
    "2026-10-04": {"collected_edgar": 23, "collected_rss": 0, "model_candidates": 0},
}
INPUTS = []


def read(path: pathlib.Path):
    INPUTS.append(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    if path.suffix == ".csv":
        return list(csv.DictReader(open(path, encoding="utf-8-sig")))
    return json.loads(path.read_text(encoding="utf-8"))


def kst(stamp: str | None) -> str | None:
    if not stamp:
        return None
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(KST).date().isoformat()


def main():
    days = list(RUNS)
    index = read(DATA / "candidates" / "index.json")
    ledger = read(DATA / "candidate_alerts.json")
    signals = read(DATA / "signal_log.csv")
    sources = read(DATA / "source_state.json")
    notify_state = read(DATA / "notify_state.json")
    with gzip.open(ROOT / "data" / "eval" / "l4_2026-10-04" / "audits.json.gz", "rt", encoding="utf-8") as h:
        audits = json.load(h)
    INPUTS.append(ROOT / "data" / "eval" / "l4_2026-10-04" / "audits.json.gz")
    history = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((DATA / "run_history").glob("*.json"))]
    observations = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((DATA / "candidate_observations").glob("OB-*.json"))]
    contexts = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((DATA / "candidate_context_history").glob("CTX-*.json"))]
    bootstrap = {k.split("|")[0] for k in (ledger.get("bootstrap") or {}).get("keys", [])}

    eps, cards_by_day, pass_by_day, rows_by_ticker = {}, {}, {}, {}
    for day, (run, snap) in RUNS.items():
        s = read(DATA / "revision_screen" / snap)
        derived = s["derived"]
        passed = [r for r in derived["rows"] if r.get("candidate")]
        targets = [t for t, _ in candidates.display_order(derived)]
        cards_by_day[day], pass_by_day[day] = targets, [r["ticker"] for r in passed]
        for r in derived["rows"]:
            rows_by_ticker.setdefault(r["ticker"], {})[day] = r
        ctx_runs = [h for h in history if h.get("component") == "candidate_context" and kst(h.get("checked_at")) == day
                    and str(h.get("run_id", "")) == run.split("-")[0]]
        ctx_run = ctx_runs[0] if ctx_runs else {}
        day_audits = [a for a in audits if a["run_id"] == run]
        alert_runs = [h for h in history if h.get("component") == "candidate_alerts" and kst(h.get("checked_at")) == day
                      and str(h.get("run_id", "")) == run.split("-")[0]]
        eps[day] = {
            "run_id": run, "snapshot": f"data/processed/revision_screen/{snap}",
            "universe": s["run"].get("universe_size"),
            "quotes": s["stages"]["quotes"], "earnings": s["stages"]["earnings"],
            "comparable_rows": len(derived["rows"]), "exclusions": s.get("exclusions"),
            "condition_pass": len(passed), "card_targets": len(targets),
            "pass_outside_cards": len(passed) - len(targets),
            "pass_by_list": {"yield_only": sum(1 for r in passed if r["by_yield"] and not r["by_growth"]),
                             "growth_only": sum(1 for r in passed if r["by_growth"] and not r["by_yield"]),
                             "both": sum(1 for r in passed if r["by_yield"] and r["by_growth"])},
            "source_research": {k: ctx_run.get(k) for k in ("targets", "researched", "statuses")},
            "drafts": {"requests": sum(a.get("budget", {}).get("requests_sent", 0) for a in day_audits),
                       "attempts": len(day_audits),
                       "outcomes": dict(Counter(a["outcome"] for a in day_audits)),
                       "http_errors": dict(Counter(str((a.get("error") or {}).get("http_status")) for a in day_audits
                                                   if a["outcome"] == "failed")),
                       "statuses_v7": dict(Counter((a.get("validation") or {}).get("context_status") for a in day_audits
                                                   if a["outcome"] == "answered"))},
            "alerts": [{k: h.get(k) for k in ("slots", "selected", "sent", "bootstrap")} for h in alert_runs],
        }

    # Per company (identified by the screen's ticker and the index entity; no name matching).
    entity_of = {}
    for o in observations:
        entity_of.setdefault(o["identity"]["ticker"], o["entity_id"])
    sent = defaultdict(list)
    for e in ledger["events"].values():
        if e.get("status") == "sent":
            sent[e["entity_id"]].append({"day": e["day"], "channel": e["channel"], "event": e["event"]})
    card_tickers = sorted({t for day in days for t in cards_by_day[day]})
    companies = []
    for t in card_tickers:
        shown = [d for d in days if t in cards_by_day[d]]
        entity = entity_of.get(t)
        cid = next((o["candidate_id"] for o in observations if o["identity"]["ticker"] == t), None)
        all_seen = sorted(o["observed_at"] for o in observations if o["identity"]["ticker"] == t)
        ctxs = sorted((c for c in contexts if c.get("candidate_id") == cid), key=lambda c: c["generated_at"])
        in_window = [c for c in ctxs if kst(c["generated_at"]) in days]
        doc_ids = sorted({d for c in ctxs for d in c.get("document_ids") or []})
        filed, stored = [], []
        for d in doc_ids:
            path = DATA / "company_documents" / f"{d}.json.gz"
            if path.exists():
                with gzip.open(path, "rt", encoding="utf-8") as h:
                    doc = json.load(h)
                filed.append(doc.get("filed_at"))
                stored.append(kst(doc.get("observed_at")))
        row = rows_by_ticker[t][shown[-1]]
        alerts = sent.get(entity, [])
        if alerts:
            why = "sent"
        elif entity in bootstrap:
            why = "bootstrap_9_25_marked_seen"
        else:
            day_obs = [o for o in observations if o["identity"]["ticker"] == t and kst(o["observed_at"]) in shown]
            missing = sorted({m["field"] for o in day_obs for m in o.get("missing") or []})
            why = f"data_missing:{','.join(missing)}" if missing else "not_selected(slots/order)"
        companies.append({
            "ticker": t, "entity_id": entity, "candidate_id": cid, "industry": row.get("industry"),
            "sector": row.get("sector"), "card_days": len(shown), "first_card_day_in_window": shown[0],
            "first_observed_ever": kst(all_seen[0]) if all_seen else None,
            "ctx_total": len(ctxs), "ctx_in_window": len(in_window),
            "latest_ctx_status": ctxs[-1]["context_status"] if ctxs else None,
            "filing_dates": sorted(set(filter(None, filed))) or None,
            "first_document_stored": min(filter(None, stored), default=None),
            "alerts_sent": alerts or None, "alert_status": why,
            "eps_target_period": row.get("eps_target_period"), "pct_90": row.get("pct_90"),
            "yield_change_90_pp": row.get("yield_change_90_pp")})

    unique = {
        "condition_pass_companies": len({t for d in days for t in pass_by_day[d]}),
        "card_companies": len(card_tickers),
        "card_companies_with_any_ctx": sum(1 for c in companies if c["ctx_total"]),
        "card_companies_ctx_in_window": sum(1 for c in companies if c["ctx_in_window"]),
        "card_companies_latest_draft_ready": sum(1 for c in companies if c["latest_ctx_status"] == "draft_ready"),
        "card_companies_alerted_ever": sum(1 for c in companies if c["alerts_sent"]),
        "alert_status": dict(Counter(c["alert_status"].split(":")[0] for c in companies)),
        "card_days_histogram": dict(Counter(c["card_days"] for c in companies)),
        "sector": dict(Counter(c["sector"] for c in companies).most_common()),
        "industry_top": dict(Counter(c["industry"] for c in companies).most_common(8)),
    }

    window_sources = {k: v for k, v in sources.items() if kst(v.get("updated_at")) in days}
    window_signals = [s for s in signals if s["날짜"] in days]
    news = {
        "by_day_logs": LOG_FIGURES,
        "judged_items_by_status": dict(Counter(v["status"] for v in window_sources.values())),
        "rejection_reasons": dict(Counter("evidence_grounding_failed" if v.get("reason") == "evidence_grounding_failed"
                                          else "model_judged_not_a_signal" if v["status"] == "rejected" else v["status"]
                                          for v in window_sources.values() if v["status"] != "accepted")),
        "accepted_signals": [{k: s[k] for k in ("signal_id", "날짜", "종목/티커", "신호유형", "upside_score", "티어",
                                                "event_state", "entity_id", "published_at")} for s in window_signals],
        "news_alerts_sent": [{"signal_id": e.get("signal_id"), "day": e["day"], "entity_id": e["entity_id"]}
                             for e in ledger["events"].values() if e["channel"] == "news" and e["day"] in days
                             and e["status"] == "sent"],
        "notify_sent": {k: v for k, v in notify_state.get("sent", {}).items() if v.get("date") in days},
        "unmeasurable": ["EDGAR full-text search hits beyond search_limit and the query's phrase list (no log of what "
                         "the search did not return)", "items dropped as already seen before the window (only kept "
                         "items carry a ledger entry)", "RSS: 2 semiconductor feeds returned 0 items on all six days"],
    }
    out = {"base_commit": "b358704", "window_kst": [days[0], days[-1]], "eps_path_by_day": eps,
           "eps_path_unique": unique, "companies": companies, "business_change_path": news,
           "definitions": {
               "comparable_rows": "rows with a same-period, same-currency EPS estimate and its 30/90-day history",
               "condition_pass": "row.candidate (A: yield change >= 1.0pp or B: 90-day growth >= 25% with steady revisions)",
               "card_targets": "union of the A and B top-20 lists (display_order)",
               "drafts": "candidate_context attempts of that daily run (L4 audits); requests = model requests sent",
               "alert_status": "sent / bootstrap_9_25_marked_seen (never a new-discovery alert by design) / "
                               "data_missing (screen_items skips) / not_selected"}}
    (HERE / "funnel.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    hashes = {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
              for p in sorted(set(INPUTS))}
    (HERE / "input_hashes.json").write_text(json.dumps(hashes, indent=1), encoding="utf-8")
    print(json.dumps(unique, ensure_ascii=False))


if __name__ == "__main__":
    main()
