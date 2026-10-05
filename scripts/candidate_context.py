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
import hashlib
import json
import re
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
DEFAULTS = {"companies_per_day": 10, "folded_companies_per_day": 2, "folded_drafts_per_day": 1,
            "filings_per_company": 5, "documents_per_company": 4,
            "update_days": 45, "update_filings_per_company": 2, "update_documents_per_company": 2,
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
    derived = snapshot.get("derived", {})
    rows = {r["ticker"]: r for r in derived.get("rows", []) if r.get("candidate")}
    order = [t for t, _ in candidates.display_order(derived)]
    # Companies folded by the industry limit stay research targets after the cards (P1-B).
    folded = [t for g in derived.get("industry_groups") or [] for t in g.get("folded", []) if t not in order]
    out = []
    for position, ticker in enumerate(order + folded, 1):
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
                    "eps_target_period": row.get("eps_target_period"), "issuer": issuer, "problem": problem,
                    "folded": ticker in folded})
    return out


def eligible(entry: dict | None, target: dict, now: datetime) -> bool:
    if not entry or entry.get("status") in ("queued", "deferred_budget"):
        return True
    if entry.get("status") == "success" and entry.get("eps_key") != target["eps_key"]:
        return True  # the estimate or its fiscal year changed
    due = entry.get("next_eligible_at")
    return due is None or datetime.fromisoformat(due) <= now


def select(all_targets: list[dict], state: dict, now: datetime, limit: int, folded_limit: int = 0) -> list[dict]:
    """Up to limit companies: card companies first, with up to folded_limit of the places for companies
    folded by the industry limit; a share one side cannot use goes to the other."""
    pool = [t for t in all_targets if eligible(state["candidates"].get(t["candidate_id"]), t, now)]
    # First seen by day: candidates seen the same day keep the A1/B1/A2... display order.
    pool.sort(key=lambda t: (state["candidates"].get(t["candidate_id"], {}).get("status") == "success",
                             t["first_seen_at"][:10], t["rank"], t["candidate_id"]))
    cards = [t for t in pool if not t.get("folded")]
    folded = [t for t in pool if t.get("folded")]
    take_folded = min(len(folded), max(0, folded_limit), limit)
    take_cards = min(len(cards), limit - take_folded)
    take_folded = min(len(folded), limit - take_cards)  # unused card places go to folded companies
    return cards[:take_cards] + folded[:take_folded]


# ------------------------------------------------------------------ research

def choose_filings(listed: list[dict], cfg: dict) -> list[dict]:
    """Recent business updates first (at most update_filings_per_company), then the results releases and
    reports as before (filings_per_company), so an update never pushes the last results release out."""
    return ([f for f in listed if f.get("update")][:cfg.get("update_filings_per_company", 0)]
            + [f for f in listed if not f.get("update")][:cfg["filings_per_company"]])


def own_statements(record: dict, issuer_name: str | None) -> bool:
    """No block of the document sits under another company's statement heading (P0)."""
    return all(cf.same_entity(e, issuer_name) is not False for e in cf.block_scopes(record.get("blocks") or []).values())


def research(target: dict, client: cf.SecClient, state: dict, now: datetime, cfg: dict) -> dict:
    """One company's recent filings: returns {status, document_ids, notes}; raises Budget/Blocked.

    Three passes over one download budget (documents_per_company, cached bodies are free):
    1. recent business-update 8-Ks, at most update_documents_per_company downloads;
    2. results releases and periodic reports with what is left (so at least the rest is theirs);
    3. update attachments skipped in pass 1, only if budget remains.
    An update is linked only when business_update_judgment finds an event sentence with its number;
    it never counts as the filer's results release, nor does another company's statement."""
    issuer = dict(target["issuer"])
    observed = now.isoformat(timespec="seconds")
    try:
        body, _, _ = client.get(cf.submissions_url(issuer["cik"]))
    except HTTPError as error:
        return {"status": "unavailable" if error.code == 404 else "failed", "document_ids": [],
                "notes": [f"submissions HTTP {error.code}"]}
    submissions = json.loads(body.decode("utf-8"))
    issuer["name"] = submissions.get("name") or issuer.get("name")
    # Names the SEC links to this CIK: a statement heading under a former name is still the filer's.
    issuer["aliases"] = [x["name"] for x in submissions.get("formerNames") or [] if x.get("name")]
    filings = choose_filings(cf.recent_filings(submissions, now.date(), cfg["lookback_days"], cfg.get("update_days")),
                             cfg)
    cap, update_cap = cfg["documents_per_company"], cfg.get("update_documents_per_company", 2)
    updates_found, results_found, examined, notes, checks = [], [], [], [], []
    spent = {"bodies": 0, "update": 0, "failures": 0}

    def documents(filing):
        try:
            page, final, _ = client.get(cf.filing_index_url(issuer["cik"], filing["accessionNumber"]))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            # One unreachable filing does not discard what other filings gave (quality=partial).
            spent["failures"] += 1
            notes.append(f"{filing['accessionNumber']} index {getattr(error, 'code', type(error).__name__)}")
            return None
        base = final.rsplit("/", 1)[0] + "/"
        return cf.pick_documents(cf.filing_documents(page.decode("utf-8", "replace"), base), filing["form"],
                                 include_main=bool(filing.get("update")))

    def cached(filing, doc):
        key = f"{filing['accessionNumber']}|{doc['url']}"
        return cf.load_document(state["documents_by_source"][key]) if key in state["documents_by_source"] else None

    def read(filing, doc):
        record = cached(filing, doc)
        if record is not None:
            return record
        try:
            raw, final_url, truncated = client.get(doc["url"])
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            spent["failures"] += 1
            notes.append(f"{doc['name']} {getattr(error, 'code', type(error).__name__)}")
            return None
        spent["bodies"] += 1
        if filing.get("update"):
            spent["update"] += 1
        record = cf.build_record(issuer, filing, doc, raw, final_url, truncated, observed)
        cf.store_document(record)
        state["documents_by_source"][f"{filing['accessionNumber']}|{doc['url']}"] = record["document_id"]
        return record

    def judge_update(record):
        # Judged from the stored blocks with the current rule; the stored record is never rewritten.
        # Search eligibility (worth reading) and alert eligibility (a verified dated event or an explicit
        # outlook change; novelty against a baseline is decided later) are kept apart (Q1-A).
        events = cf.business_events(record.get("blocks") or [], issuer["name"])
        ok = bool(events)
        reason = (f"{cf.UPDATE_CHECK_VERSION}:{events[0]['event']}:{events[0]['block_id']}" if ok
                  else f"{cf.UPDATE_CHECK_VERSION}:no_event_sentence")
        if not any(x["document_id"] == record["document_id"] for x in checks):
            checks.append({"document_id": record["document_id"], "eligible": ok, "search_eligible": ok,
                           "alert_eligible": any(e["alert_eligible"] for e in events), "reason": reason,
                           "alert_reasons": sorted({e["alert_reason"] for e in events if e["alert_reason"]})})
        return ok

    leftover = []
    for filing in (f for f in filings if f.get("update")):
        picks = documents(filing)
        for i, doc in enumerate(picks or []):
            if cached(filing, doc) is None and (spent["update"] >= update_cap or spent["bodies"] >= cap):
                leftover.append((filing, picks[i:]))
                break
            record = read(filing, doc)
            if record is None:
                continue
            examined.append(record["document_id"])
            if judge_update(record):
                updates_found.append(record["document_id"])
                break
    for filing in (f for f in filings if not f.get("update")):
        if spent["bodies"] >= cap:
            notes.append("document budget reached before every results filing was read")
            break
        if results_found and filing["rank"] == 2 and any(
                (cf.load_document(d) or {}).get("relevance", {}).get("core_earnings") for d in results_found):
            break  # the filer's own results release was found: the large periodic report is not needed
        for doc in documents(filing) or []:
            if spent["bodies"] >= cap and cached(filing, doc) is None:
                break
            record = read(filing, doc)
            if record is None:
                continue
            examined.append(record["document_id"])
            if record["relevance"]["earnings"] and own_statements(record, issuer["name"]):
                results_found.append(record["document_id"])
                break  # one results document per filing
    for filing, picks in leftover:
        for doc in picks:
            if spent["bodies"] >= cap and cached(filing, doc) is None:
                break
            record = read(filing, doc)
            if record is None:
                continue
            examined.append(record["document_id"])
            if judge_update(record):
                updates_found.append(record["document_id"])
                break
    found = updates_found + results_found
    for doc_id in examined:  # results releases too: an outlook change in them can be an A event (Q1-A)
        record = cf.load_document(doc_id)
        if record is not None:
            judge_update(record)
    failures = spent["failures"]
    if found:
        return {"status": "success", "quality": "partial" if failures else "complete", "document_ids": found,
                "examined": examined, "notes": notes, "failures": failures, "update_checks": checks}
    if not filings:
        notes.append(f"no 8-K/6-K results or periodic report in {cfg['lookback_days']} days")
    return {"status": "failed" if failures else "no_relevant_document", "document_ids": [], "examined": examined,
            "notes": notes, "failures": failures, "update_checks": checks}


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


def refresh_issuers(client):
    """Only the official identity list; never run prices, EPS or alerts."""
    import screen_revisions as screen
    def transport(url, headers):
        body, _, truncated = client.get(url)
        if truncated:
            raise ValueError("issuer list truncated")
        return 200, body, {}
    rows = screen.load_universe(transport, client.user_agent)
    screen.store_issuers(rows, dict(screen.UNIVERSE_SOURCE))
    return len(rows)


def run_sources(now: datetime | None = None, client: cf.SecClient | None = None,
                deadline: float | None = None) -> dict:
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
    user_agent = os.environ.get("SEC_USER_AGENT") or "investment-research-system/2.0 research-bot"
    client = client or cf.SecClient(user_agent=user_agent,
        attempts_left=max(0, cfg["http_attempts_per_day"] - usage["http_attempts"]),
        deadline=deadline or time.monotonic() + cfg["time_budget_s"], timeout_s=cfg["timeout_s"],
        max_bytes=cfg["max_document_bytes"])
    def reserve_request():
        if usage["http_attempts"] >= cfg["http_attempts_per_day"]:
            raise cf.Budget("daily_http_attempts")
        usage["http_attempts"] += 1
        c.atomic_json(state_path(), state)
    client.on_attempt = reserve_request
    issuers = load_issuers()
    if not issuers.get("issuers") and any(not r.get("cik") for r in snapshot.get("derived", {}).get("rows", []) if r.get("candidate")):
        try:
            refresh_issuers(client)
            issuers = load_issuers()
        except (OSError, ValueError, cf.Budget, cf.Blocked) as error:
            report["issuer_refresh"] = type(error).__name__
    first_seen = {cid: item["first_seen_at"] for cid, item in candidates.known_candidates().items()}
    all_targets = targets(snapshot, c.read_json(c.ROOT / "config" / "entities.json", {}), issuers, first_seen)
    report["targets"] = len(all_targets)
    report["current"] = {t["candidate_id"]: t["eps_target_period"] for t in all_targets}
    for t in all_targets:
        entry = state["candidates"].get(t["candidate_id"])
        if t["problem"]:
            entry = state["candidates"].setdefault(t["candidate_id"], {})
            entry.update(status=t["problem"], identity_problem=True, ticker=t["ticker"])
        elif entry and entry.pop("identity_problem", False):
            entry.update(status="queued", next_eligible_at=None)
    ready = [t for t in all_targets if not t["problem"]]
    report["folded"] = sorted(t["candidate_id"] for t in all_targets if t.get("folded"))
    chosen = select(ready, state, now, max(0, cfg["companies_per_day"] - usage["companies"]),
                    max(0, cfg["folded_companies_per_day"] - usage.get("folded_companies", 0)))
    for target in chosen:
        entry = state["candidates"].setdefault(target["candidate_id"], {})
        usage["companies"] += 1
        if target.get("folded"):
            usage["folded_companies"] = usage.get("folded_companies", 0) + 1
        c.atomic_json(state_path(), state)
        try:
            result = research(target, client, state, now, cfg)
        except cf.Budget as error:
            # Not a failure: nothing more is sent today; the next run continues from here.
            entry.update(status="deferred_budget", note=str(error), ticker=target["ticker"], next_eligible_at=None)
            break
        except cf.Blocked as error:
            entry.update(status="failed", note=str(error), ticker=target["ticker"],
                         next_eligible_at=(now + timedelta(hours=cfg["retry_failed_hours"])).isoformat(timespec="seconds"))
            report["blocked"] = True
            break
        except (URLError, TimeoutError, OSError, ValueError) as error:
            result = {"status": "failed", "document_ids": [], "notes": [type(error).__name__]}
        wait = {"success": timedelta(days=cfg["revisit_days"]), "failed": timedelta(hours=cfg["retry_failed_hours"])}
        entry.update(status=result["status"], ticker=target["ticker"], issuer=target["issuer"],
                     attempted_at=now.isoformat(timespec="seconds"), eps_key=target["eps_key"],
                     eps_target_period=target["eps_target_period"], document_ids=result["document_ids"],
                     quality=result.get("quality", "unknown"), failures=result.get("failures", 0),
                     examined=result.get("examined", []), notes=result["notes"],
                     update_checks=result.get("update_checks", []),
                     next_eligible_at=(now + wait.get(result["status"], timedelta(days=cfg["no_document_days"])))
                     .isoformat(timespec="seconds"))
        report["researched"] += 1
        report["statuses"][result["status"]] = report["statuses"].get(result["status"], 0) + 1
        if result.get("quality") == "partial":
            report["partial_sources"] = report.get("partial_sources", 0) + 1
        c.atomic_json(state_path(), state)
    for t in ready:
        state["candidates"].setdefault(t["candidate_id"], {"status": "queued", "ticker": t["ticker"]})
    c.atomic_json(state_path(), state)
    report["http_attempts"] = usage["http_attempts"]
    report["coverage"] = coverage(state, [t["candidate_id"] for t in all_targets])
    return report


# ------------------------------------------------------------------ G2 drafts

PROMPT_VERSION = "context-ko-v4"
PARSER_VERSION = "context-check-v11"
KINDS = ("fact", "guidance", "interpretation")
SUBJECTS = ("issuer", "subsidiary", "segment", "customer", "other")
DRIVERS = ("volume", "price", "mix", "margin_cost", "capacity", "backlog", "buyback_sharecount", "tax", "fx",
           "acquisition_disposal", "one_off", "accounting", "unknown")
DIRECTIONS = ("positive", "negative", "mixed", "unknown")
# Automatic drafts never assert a direct link to the estimate revision; a person confirms that elsewhere.
LINKS = ("temporal_context", "unconfirmed")
FORWARD = ("expect", "outlook", "guidance", "forecast", "anticipate", "project", "target")
# Whole words: 'increasing its guidance' is a raise (URGN, DAN), and 'execute' holds no 'cut'.
RAISE = re.compile(r"\b(?:rais(?:e|es|ed|ing)|increas(?:e|es|ed|ing)|higher|above|up from|improv\w*)\b")
LOWER = re.compile(r"\b(?:lower(?:s|ed|ing)?|reduc(?:e|es|ed|ing)|cut(?:s|ting)?|decreas(?:e|es|ed|ing)|below|"
                   r"down from|declin\w*)\b")
KO_UP = ("상향", "인상", "올렸", "높였", "늘렸")
KO_DOWN = ("하향", "인하", "낮췄", "줄였")
KO_CAUSAL = ("상향 원인", "때문에 추정치", "추정치가 올랐", "상향을 이끌", "상향의 원인", "추정치 상향", "컨센서스")
FORBIDDEN = ("매수", "목표가", "저평가", "상승 확률")
# Amounts, units and currencies in the Korean note are refused: figures come only from the source.
UNIT_WORDS = ("달러", "유로", "파운드", "엔화", "원화", "억", "조 ", "백만", "천만", "퍼센트", "%", "million", "billion",
              "thousand", "usd", "eur", "gbp", "$", "€", "£", "센트")
METRIC_KO = {"revenue": "매출", "revenues": "매출", "net sales": "매출", "sales": "매출", "net income": "순이익",
             "net earnings": "순이익", "net loss": "순손실", "earnings per share": "주당순이익", "eps": "주당순이익",
             "diluted eps": "희석 주당순이익", "operating income": "영업이익", "gross margin": "매출총이익률",
             "operating margin": "영업이익률", "ebitda": "EBITDA", "adjusted ebitda": "조정 EBITDA",
             "free cash flow": "잉여현금흐름", "backlog": "수주잔고", "orders": "수주", "bookings": "수주",
             "distribution": "분배금", "distributions": "분배금", "dividend": "배당", "margin": "마진",
             "capital expenditures": "설비투자", "share repurchases": "자사주 매입", "throughput": "처리량",
             "production": "생산량", "volume": "물량", "volumes": "물량", "cost": "비용", "costs": "비용"}
FIGURE = re.compile(r"\(?[$€£]?\s?\d[\d,]*(?:\.\d+)?\)?\s?(?:%|percent|million|billion|thousand|cents?|per share|per diluted share|x)?"
                    r"(?:\s(?:million|billion))?", re.I)
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
QUARTER = re.compile(r"\b(?:first|second|third|fourth)\s+quarter\b|\bq[1-4]\b", re.I)
MAX_PROMPT_CHARS = 12000
BLOCK_SIGNALS = {
    "results": ("revenue", "net sales", "net income", "earnings per share", "operating income", "gross margin",
                "ebitda", "per diluted share"),
    "guidance": ("guidance", "outlook", "expect", "forecast", "anticipate"),
    "update": ("agreement", "contract", "award", "backlog", "orders", "acquisition", "capacity", "price increase"),
    "cause": ("driven by", "due to", "primarily", "reflect", "as a result", "because"),
    "one_off": ("one-time", "non-recurring", "impairment", "restructuring", "gain on", "tax benefit", "divest",
                "special item"),
    "against": ("decline", "decrease", "lower", "headwind", "weak", "offset", "reduced"),
}
BOILERPLATE = ("forward-looking statements", "safe harbor", "risk factors", "undue reliance", "cautionary")


def history_dir() -> Path:
    return c.DATA_DIR / "candidate_context_history"


PUNCTUATION = str.maketrans({"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-",
                             "\u2014": "-", "\u00a0": " "})


def squash(text: str) -> str:
    """Whitespace, case and typographic quotes/dashes do not make a quote different."""
    return " ".join(str(text).translate(PUNCTUATION).split()).casefold()


def block_score(text: str) -> int:
    low = text.lower()
    if any(word in low for word in BOILERPLATE):
        return -1
    return sum(any(word in low for word in words) for words in BLOCK_SIGNALS.values())


def relevant_blocks(documents: list[dict], limit: int = MAX_PROMPT_CHARS) -> tuple[list[dict], str]:
    """Blocks about results, guidance, causes, one-offs and counter-evidence first (any industry);
    shown to the model in document order. Coverage is partial when a relevant block was left out."""
    scored, complete = [], True
    for d_index, doc in enumerate(documents):
        if doc.get("coverage") == "partial":
            complete = False
        scopes = cf.block_scopes(doc["blocks"])
        for b_index, block in enumerate(doc["blocks"]):
            text = cf.block_text(block)
            score = block_score(text)
            if score > 0:
                scored.append((score, d_index, b_index, {"document_id": doc["document_id"], "block_id": block["id"],
                                                         "text": text, "scope": scopes.get(block["id"])}))
    chosen, used = [], 0
    for score, d_index, b_index, block in sorted(scored, key=lambda x: (-x[0], x[1], x[2])):
        if used + len(block["text"]) > limit:
            complete = False
            continue
        chosen.append((d_index, b_index, block))
        used += len(block["text"])
    return [b for _, _, b in sorted(chosen, key=lambda x: (x[0], x[1]))], "complete" if complete else "partial"


def draft_prompt(target: dict, documents: list[dict], blocks: list[dict]) -> str:
    heads = [{"document_id": d["document_id"], "form": d["form"], "type": d["document_type"], "title": d["title"],
              "filed_at": d["filed_at"], "report_date": d.get("report_date")} for d in documents]
    return (
        "너는 미국 상장사 공식 공시 원문에서 사실만 뽑는 도우미다. 아래 블록만 근거로 JSON 하나를 출력하라.\n"
        f"회사: {target['ticker']} ({target.get('issuer_name') or '발행사'}). 애널리스트의 내년 EPS 예상치가 최근 올라 "
        f"검토 대상이 됐다(대상 회계연도 말 {target.get('eps_target_period')}). 이 발표가 그 상향을 일으켰다고 쓰지 마라.\n"
        "규칙:\n"
        "1. quote는 해당 block 문장을 글자 그대로 복사한다(한 문장 또는 표 한 행).\n"
        "2. figures는 quote에 있는 수치 문구를 글자 그대로 복사한다(예: \"$5 million\", \"(1.3)\", \"40%\"). 단위 환산·계산 금지.\n"
        "3. note_ko는 한국어 설명이며 숫자·통화·단위(달러, million, % 등)를 쓰지 않는다. 한글로 풀어 쓴 금액(예: 구백만 달러)도 금지. "
        "숫자는 figures로만 전달되며 카드 문장은 figures로 조립된다. 좋은 예: note_ko \"전년 같은 분기보다 늘었다\".\n"
        "3-1. figures 하나에는 한 기간의 값만 넣고, 비교 문장에서는 현재 기간 값을 쓴다. 범위는 원문대로 한 문구로(\"$130 million to $135 million\").\n"
        "4. metric은 quote에 있는 영어 지표명(예: revenue, net income, distributions), period는 quote/표 머리글의 기간 표기 그대로(모르면 unknown).\n"
        "5. subject: 회사 전체 수치면 issuer, 자회사면 subsidiary(subject_name에 이름), 사업부면 segment, 고객이면 customer.\n"
        "6. kind: 실적 fact, 회사 전망 guidance, 원문 인용이 있는 해석 interpretation(figures 없이).\n"
        "7. gaap 값은 GAAP, non-GAAP, unknown 중 하나다. 원문 지표명 앞에 GAAP가 있으면 GAAP, non-GAAP 또는 adjusted가 "
        "있으면 non-GAAP(adjusted라고 적힌 지표도 출력은 non-GAAP), 표기가 없으면 unknown.\n"
        "8. 일회성 이익·세금·자사주 매입으로 생긴 주당 수치 변화를 영업 성장으로 쓰지 마라. 반대 근거는 limitations에.\n"
        "9. link는 unconfirmed 또는 temporal_context만. 매수·목표가·주가 전망 금지. next_check는 확인할 질문 문장(숫자 없이).\n"
        f"drivers: {', '.join(DRIVERS)}. direction: {', '.join(DIRECTIONS)}.\n"
        '출력: {"claims":[{"kind":"","subject":"","subject_name":"","metric":"","figures":[""],"period":"",'
        '"gaap":"unknown","note_ko":"","quote":"","document_id":"","block_id":"","drivers":[""],"direction":""}],'
        '"limitations":[{"subject":"","metric":"","figures":[],"period":"","note_ko":"","quote":"","document_id":"",'
        '"block_id":""}],"next_check":[""],"link":"unconfirmed"}\n최대 claims 5개, limitations 3개, next_check 2개.\n\n'
        f"문서: {json.dumps(heads, ensure_ascii=False)}\n\n블록:\n"
        + "\n".join(f"[{b['document_id']}#{b['block_id']}] {b['text']}" for b in blocks))


def number_spans(text: str) -> list[tuple[int, int]]:
    """Spans of the number phrases in squashed text. A leading '(' counts only as a negative sign."""
    spans = []
    for m in FIGURE.finditer(text):
        if not re.search(r"\d", m.group(0)):
            continue
        start, end = m.span()
        if text[start] == "(" and not re.match(r"\([$€£]?\s?\d[\d,]*(?:\.\d+)?\)", text[start:]):
            start += 1  # '($0.25 per share)': grammar, not a negative
        while start < end and text[start] == " ":
            start += 1  # the pattern may begin at the space before a number
        while end > start and text[end - 1] == " ":
            end -= 1
        spans.append((start, end))
    return spans


def figure_problem(figure: str, quote_raw: str) -> str | None:
    """A figure is a verbatim, contiguous part of the quote that never cuts a number phrase
    (currency, parentheses, million/billion) and holds at most one period."""
    q, f = squash(quote_raw), squash(figure)
    if not re.search(r"\d", f) or len(f) > 80:
        return "figure_not_verbatim"
    start = q.find(f)
    if start < 0:
        return "figure_not_verbatim"
    end = start + len(f)
    if (start > 0 and q[start - 1].isalnum()) or (end < len(q) and q[end].isalnum()):
        return "figure_cut_from_source"
    for s, e in number_spans(q):
        if e > start and s < end and not (start <= s and e <= end):
            return "figure_cut_from_source"
    if len(set(YEAR.findall(f))) + len({squash(x) for x in QUARTER.findall(f)}) > 1 or re.search(r"[.;]\s", f):
        return "figure_spans_statements"
    return None


# ---- what a number is (context-check-v9): a level, a change, or an effect on another figure
# Small words allowed between a change/effect phrase and its number ('by a net, after-tax benefit of').
ROLE_FILL = r"(?:(?:approximately|about|around|nearly|roughly|almost|over|more than|less than|an?|the|net|" \
            r"after-tax|pre-tax|total|additional|further|another)[ ,]+)*"
CHANGE_NOUN = r"(?:increase|decrease|improvement|decline|reduction|rise|drop|growth|expansion|contraction)s?"
CHANGE_VERB = r"(?:increas|decreas|rais|lower|reduc|cut|improv|grew|grow|rose|rise|rising|fell|fall|declin|expand|" \
              r"contract|boost|lift|drop|gain|climb|revis)\w*"
DELTA_BEFORE = [
    re.compile(rf"\b{CHANGE_NOUN} of {ROLE_FILL}\(?$"),                     # 'an increase of $9.2 million'
    re.compile(rf"\b{CHANGE_VERB}\b[^.;:]{{0,90}}?\bby {ROLE_FILL}\(?$"),   # 'increasing its outlook by approximately $225 million'
    re.compile(rf"\b(?:up|down|{CHANGE_VERB}) {ROLE_FILL}\(?$"),            # 'up $29 million', 'grew 23%', 'decline approximately (4.0%)'
]
DELTA_AFTER = re.compile(rf"^ ?(?:{CHANGE_NOUN}\b|(?:higher|lower|more|less) than\b|year-over-year\b|yoy\b|y/y\b|"
                         rf"(?:quarter-over-quarter|sequential(?:ly)?)\b)")
EFFECT_BEFORE = re.compile(rf"\b(?:(?:benefit|charge|impact|effect)s? (?:of|from) |(?:impacted|affected|hurt|helped|"
                           rf"benefited|benefitted|reduced|offset) by ){ROLE_FILL}\(?$")
# 'a $12 million gain lifted net income', '$5 million of charges that reduced operating income'
EFFECT_AFTER = re.compile(r"^ (?:of )?(?:[\w-]+ ){0,3}(?:gain|charge|benefit|loss|impairment|expense|item|cost)s?,? "
                          r"(?:that |which )?(?:increas|decreas|lift|boost|reduc|lower|rais|hurt|impact|affect|offset|"
                          r"weigh|add)\w*\b")
LIST_JOIN = re.compile(r"(?:,| and| or|, and|, or)\s+(?:an? )?$")
TO_LEVEL = re.compile(rf"\bto {ROLE_FILL}$")  # 'increased 25 basis points to 2.44%': the target value is a level
RATE = re.compile(r"%|\bpercent(?:age points?)?\b|\bbasis points?\b|\bbps\b|\bpoints?\b")
UP_WORD = re.compile(r"\b(?:increas\w*|rais\w*|grew|grow\w*|rose|ris(?:e|es|ing)|improv\w*|expand\w*|boost\w*|"
                     r"lift\w*|gain\w*|climb\w*|higher|up)\b")
DOWN_WORD = re.compile(r"\b(?:decreas\w*|lower\w*|reduc\w*|cut\w*|fell|fall\w*|declin\w*|contract\w*|drop\w*|down)\b")
# Verbs that say an amount moved another figure: 'which increased net income by ...', 'net loss was impacted by'.
EFFECT_VERB = re.compile(r"\b(?:increas|decreas|reduc|lower|rais|lift|boost|impact|affect|benefit|hurt|offset)\w*\b")
NOT_A_MODIFIER = re.compile(rf"^(?:{CHANGE_VERB}|\w+ed|was|were|is|are|to|by|of|in|for|from|and|or)$")


def word_direction(text: str) -> str | None:
    """'up'/'down' only when the matched grammar itself says so; never guessed from the sentence."""
    up, down = UP_WORD.search(text), DOWN_WORD.search(text)
    return "up" if up and not down else "down" if down and not up else None


def unit_kind(q: str, start: int, end: int) -> str:
    """amount / pct / bp / pp: 25 basis points is a different unit from 25%, never converted."""
    span = q[start:end]
    if re.match(r"^\(?[\d.,]+\)? ?(?:basis points?|bps)\b", q[start:]):
        return "bp"
    if re.match(r"^\(?[\d.,]+\)? ?percentage points?\b", q[start:]):
        return "pp"  # the number phrase stops at 'percent', so the words after it decide
    return "pct" if "%" in span or "percent" in span else "amount"


def figure_role(q: str, start: int, end: int, previous: dict | None) -> dict:
    """{'role': level|delta|effect, 'direction': up|down|None} for the number phrase q[start:end].
    Only grammar touching the number counts: an 'increase' elsewhere in the sentence does not make
    every number a change, and 'increased to X' / 'from X to Y' keep X and Y as levels."""
    before, after = q[max(0, start - 120):start], q[end:end + 40].lstrip(")")
    found = DELTA_AFTER.search(after)
    if found:  # '$1.8 million increase in provision', also after 'offset by' or 'attributable to a'
        direction = word_direction(found.group(0))
        if direction is None:  # 'grew 23% year-over-year': the word right before the number says which way
            touching = next((p.search(before) for p in DELTA_BEFORE if p.search(before)), None)
            direction = word_direction(touching.group(0).split()[0]) if touching else None
        return {"role": "delta", "direction": direction}
    if TO_LEVEL.search(before) and not DELTA_BEFORE[1].search(before):
        return {"role": "level", "direction": None}
    if EFFECT_BEFORE.search(before) or EFFECT_AFTER.search(after):
        return {"role": "effect", "direction": None}
    for pattern in DELTA_BEFORE:
        found = pattern.search(before)
        if found:  # the change word is the first word of the match
            return {"role": "delta", "direction": word_direction(found.group(0).split()[0])}
    if previous and previous["role"] in ("delta", "effect") and LIST_JOIN.search(before):
        return {**previous, "joined": True}  # 'an increase of $9.2 million, or 17.2%,'
    return {"role": "level", "direction": None}


def quote_roles(q: str) -> list[dict]:
    """Every number phrase of the squashed quote with its role, direction and unit, in order."""
    roles, previous = [], None
    for s, e in number_spans(q):
        role = {**figure_role(q, s, e, previous), "start": s, "end": e, "unit": unit_kind(q, s, e)}
        roles.append(role)
        previous = role
    return roles


def bound_to_metric(q: str, at: int, end: int, m: str) -> bool:
    """The amount measures the metric itself: 'tax benefit of $12 million' or '$138.9 million goodwill
    impairment loss' (up to two modifiers between, never a verb). '$12 million increased net income'
    does not make $12 million net income."""
    if not m:
        return False
    if re.search(r"(?<![a-z])" + re.escape(m) + rf"s? (?:of|from) {ROLE_FILL}\(?$", q[max(0, at - 120):at]):
        return True
    words = re.findall(r"[\w$'-]+", q[end:end + 80])
    target = re.findall(r"[\w$'-]+", m)
    for skip in range(3):
        if words[skip:skip + len(target)] == target and not any(NOT_A_MODIFIER.match(w) for w in words[:skip]):
            return True
    return False


def effect_target(q: str, at: int, m: str) -> dict | None:
    """For a limitation: the effect's target is the claimed metric, named with an effect verb in the
    same clause before the amount ('which increased net income by a net, after-tax benefit of')."""
    start = max([0] + [x.end() for x in re.finditer(r"[.;]\s", q[:at])])
    clause = q[start:at]
    if not m or not re.search(r"(?<![a-z])" + re.escape(m) + r"(?![a-z])", clause):
        return None
    verb = EFFECT_VERB.search(clause)
    if not verb:
        return None
    phrase = clause[clause.rfind(" by ") + 1:] if " by " in clause else clause[-60:]
    return {"direction": word_direction(verb.group(0)), "after_tax": "after-tax" in phrase,
            "net": bool(re.search(r"\bnet\b", phrase.replace(m, "")))}


def role_problem(metric: str, figures: list[str], quote_raw: str, what: str = "claim") -> tuple[str | None, list[dict]]:
    """(problem, role per figure). A change or effect amount offered as the metric's value is refused:
    '$9.2 million increase in net interest income' is not net interest income (CLBK, 10/2 run), and
    'a one-time tax benefit of $12 million increased net income' does not make $12 million net income.
    A pure rate change ('decreased 9%', 'up 25 basis points') stays, labelled as a change, and so does a
    figure that carries its own change wording ('decreased oil revenues by $28.5 million'). A figure
    mixing an amount with a rate, or two roles, is refused whole: nothing is cut into new facts.
    A limitation may show an effect on its metric (PBF special items) only when the clause names the
    metric with an effect verb; the card then says 'effect on', never the metric's value."""
    q, m = squash(quote_raw), squash(metric)
    spans = quote_roles(q)
    details = []
    for figure in figures:
        f = squash(figure)
        seen = []  # the reading at every place the figure appears: two different readings is ambiguous
        for at in (i for i in range(len(q)) if q.startswith(f, i)):
            inside = [x for x in spans if at <= x["start"] < at + len(f)]
            if not inside:
                continue
            roles, units = {x["role"] for x in inside}, {x["unit"] for x in inside}
            if len(roles) > 1:
                return "figure_role_mixed", []
            role = roles.pop()
            if role != "level" and "amount" in units and len(units) > 1:
                return "figure_mixes_amount_and_rate", []  # '$9.2 million, or 17.2%'
            first = inside[0]
            reading = {"role": role, "unit": first["unit"], "direction": first["direction"]}
            if role == "delta" and re.search(rf"\b{CHANGE_VERB}\b|\b{CHANGE_NOUN}\b|\b(?:up|down)\b", f):
                reading["role"] = "described_delta"  # the figure itself says it is a change
            if role == "effect" and bound_to_metric(q, at, at + len(f), m):
                reading = {"role": "level", "unit": first["unit"], "direction": None}
            if reading["role"] == "effect" and m:
                target = effect_target(q, at, m) if what == "limitation" else None
                if target is None:
                    return "effect_presented_as_level", []
                if "per share" in f or "per diluted share" in f:
                    # Only as the per-share form of the effect amount just before it: 'X, or $1.32 per share'.
                    prior = [x for x in spans if x["end"] <= at]
                    if not (first.get("joined") and prior and prior[-1]["role"] == "effect"
                            and any(squash(g) in q[prior[-1]["start"]:prior[-1]["end"] + 12] for g in figures if g != figure)):
                        return "effect_presented_as_level", []
                    target = {**target, "per_share": True}
                reading = {"role": "effect_on_metric", "unit": first["unit"], **target}
            seen.append(reading)
        if any(x != seen[0] for x in seen[1:]):
            return "figure_role_ambiguous", []
        reading = seen[0] if seen else {"role": "level", "unit": "amount", "direction": None}
        if reading["role"] == "delta" and m and reading["unit"] == "amount":
            return "delta_presented_as_level", []
        details.append(reading)
    if any(x["role"] == "effect_on_metric" for x in details) and any(x["role"] != "effect_on_metric" for x in details):
        return "figure_role_mixed", []  # an effect shown next to another metric's or period's number
    return None, details


def labelled(figure: str, reading: dict) -> str:
    """The figure as the card shows it: a change or an effect is never shown bare next to a level."""
    role, direction = reading["role"], reading.get("direction")
    if role == "level":
        return figure
    if role == "effect":
        return f"{figure}(영향 금액)"
    change = {"up": "증가", "down": "감소"}.get(direction, "")
    if role == "effect_on_metric":
        if reading.get("per_share"):
            return f"{figure}(주당 {change + ' ' if change else ''}효과)"
        basis = ("세후 " if reading.get("after_tax") else "") + ("순" if reading.get("net") else "")
        return f"{figure}({basis}{change} 효과)" if basis or change else f"{figure}(효과)"
    kind = {"pct": "변화율", "bp": "변화폭", "pp": "변화폭"}.get(reading.get("unit"), "변화량")
    return f"{figure}({kind}·{change})" if change else f"{figure}({kind})"


PREDICATE = r"(?:is|was|were|are|totaled|totalled|totals|reached|stood at|amounted to|of)\b"
# ', including <words>, is ...': commas inside only in a date, periods only in a decimal number.
ASIDE = re.compile(r", including (?:[^,.;]|(?<=\d)\.(?=\d)|, (?=(?:19|20)\d{2}\b))+?, (?=" + PREDICATE + ")")


def asides(q: str) -> list[tuple[int, int]]:
    """Closed 'including ...' asides followed by the sentence's own predicate ('effective backlog,
    including bookings since may 29, 2026, is $100.6 million'). Anything unclear is not an aside,
    so the conservative nearest-metric rule still applies."""
    return [found.span() for found in ASIDE.finditer(q)]


def metric_problem(metric: str, figures: list[str], quote_raw: str) -> str | None:
    """Each figure's nearest metric mention is the claimed one, within the same statement."""
    q, m = squash(quote_raw), squash(metric)
    if not m or m not in q:
        return "metric_not_in_quote"
    names = {squash(x) for x in METRIC_KO} | {m}
    all_mentions = [(x.start(), x.end(), name) for name in names
                    for x in re.finditer(r"(?<![a-z])" + re.escape(name) + r"(?![a-z])", q)]
    claimed = [(s, e) for s, e, name in all_mentions if name == m]
    aside_spans = asides(q)
    for figure in figures:
        at = q.find(squash(figure))
        if at < 0 or not all_mentions:
            continue
        # A figure outside an aside is not claimed by a metric named inside it, and a figure inside
        # one belongs only to a metric named inside the same aside.
        inside = next((span for span in aside_spans if span[0] <= at < span[1]), None)
        mentions = [x for x in all_mentions
                    if (inside and inside[0] <= x[0] < inside[1])
                    or (not inside and not any(a <= x[0] < b for a, b in aside_spans))]
        if RATE.search(squash(figure)):
            # '45.0 percent of revenue': revenue is the ratio's denominator, not the figure's metric (AXTI).
            end_at = at + len(squash(figure))
            mentions = [x for x in mentions if not re.fullmatch(r" of (?:total |net )?", q[end_at:x[0]])] or mentions
        if not mentions:
            return "figure_belongs_to_another_metric"
        # Nearest mention by distance; at a tie the longer name wins ('adjusted ebitda' over 'ebitda').
        s, e, name = min(mentions, key=lambda x: (min(abs(x[0] - at), abs(x[1] - at)), -len(x[2])))
        # A shorter name counts as the claimed metric only inside a mention of it: 'revenue' within
        # 'total company revenue', never a separate 'net income' next to 'net income attributable to ...'.
        if name != m and not any(cs <= s and e <= ce for cs, ce in claimed) and not repeated_name(q, m, name, s, claimed):
            return "figure_belongs_to_another_metric"
        # 'operating income' inside 'adjusted operating income' is another metric unless claimed so.
        qualifier = re.search(r"(adjusted|non-gaap|organic|core|segment|pro forma)\s+$", q[max(0, s - 14):s])
        if qualifier and qualifier.group(1) not in m:
            return "figure_belongs_to_another_metric"
        between = q[min(e, at):max(s, at)]
        if re.search(r"[.;]\s", between):
            return "figure_belongs_to_another_metric"
    return None


def repeated_name(q: str, m: str, name: str, s: int, claimed: list[tuple[int, int]]) -> bool:
    """'GAAP net income ... for the second quarter of 2026 was a net income of $11.1 million' (AXTI):
    the second 'net income' repeats the claimed metric. Only the claimed name's own ending, written as
    'was/is a <name> of', after a mention of the claimed metric in the same statement, with no other
    metric, basis, attribution or scope word between."""
    if not (m.endswith(" " + name) and re.search(r"\b(?:was|were|is|are) an? $", q[max(0, s - 8):s])
            and q[s + len(name):s + len(name) + 4] == " of "):
        return False
    earlier = [ce for cs, ce in claimed if ce <= s]
    if not earlier:
        return False
    between = q[max(earlier):s]
    return not re.search(r"[.;]\s", between) and not any(
        re.search(r"(?<![a-z])" + re.escape(x) + r"(?![a-z])", between) for x in set(METRIC_KO) - {name}) \
        and not re.search(r"\b(?:adjusted|non-gaap|gaap|attributable|segment|consolidated|excluding|including)\b",
                          between)


def figure_phrases(text: str) -> set[str]:
    return {squash(m.group(0).strip()) for m in FIGURE.finditer(str(text)) if re.search(r"\d", m.group(0))}


def nearest(pattern: re.Pattern, text: str, position: int) -> str | None:
    hits = [(abs(m.start() - position), squash(m.group(0))) for m in pattern.finditer(text)]
    return min(hits)[1] if hits else None


MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"
# A period is a year, quarter, half, fiscal/full year, 'N months ended', or a month with a day or year.
PERIOD_FORM = re.compile(
    rf"\b(?:19|20)\d{{2}}\b|\bq[1-4]\b|\b(?:first|second|third|fourth)\s+quarter\b|\b(?:first|second)\s+half\b"
    rf"|\bfiscal\b|\bfull[- ]year\b|\b(?:three|six|nine|twelve)\s+months\s+ended\b"
    rf"|\b(?:{MONTHS})\s+\d{{1,2}}\b|\b(?:{MONTHS})\s+(?:19|20)\d{{2}}\b", re.I)


COMPARISON = re.compile(r"\b(?:compared (?:to|with)|versus|vs\.?)\s")


def period_problem(item: dict, quote: str, block: str) -> str | None:
    """The claimed period must be in the source, and every figure's nearest year/quarter in the
    quote must be that period's, so a number cannot move to another period."""
    period = squash(item.get("period") or "unknown")
    years, quarters = set(YEAR.findall(quote)), {squash(q) for q in QUARTER.findall(quote)}
    if period == "unknown":
        return "ambiguous_period" if item.get("figures") and (len(years) > 1 or len(quarters) > 1) else None
    if not PERIOD_FORM.search(period):
        return "period_not_a_period"  # e.g. 'may' the verb is not the month May
    if period not in squash(quote) and period not in squash(block):
        return "period_not_in_source"
    q = squash(quote)
    aside_spans = asides(q)
    if aside_spans and period in q and all(any(a <= x.start() < b for a, b in aside_spans)
                                           for x in re.finditer(re.escape(period), q)):
        # 'backlog, including bookings since May 29, 2026, is ...': the aside's date is not the figure's period.
        if any(not any(a <= q.find(squash(f)) < b for a, b in aside_spans) for f in item.get("figures") or []):
            return "figure_from_another_period"
    # 'net income to $15.6 million ..., compared with $3.3 million in the second quarter of 2025' (IPI):
    # the only stated period sits on one side of the comparison, so a figure on the other side is not its.
    mark = COMPARISON.search(q)
    if mark and period in q:
        sides = {x.start() < mark.start() for x in re.finditer(re.escape(period), q)}
        if len(sides) == 1:
            before = sides.pop()
            for figure in item.get("figures") or []:
                at = q.find(squash(figure))
                if at >= 0 and (at < mark.start()) != before:
                    return "figure_from_another_period"
    flat = quote.translate(PUNCTUATION)
    for figure in item.get("figures") or []:
        at = squash(flat).find(squash(figure))
        text = squash(flat)
        near_year, near_quarter = nearest(YEAR, text, at), nearest(QUARTER, text, at)
        if near_year and YEAR.search(period) and near_year not in period:
            return "figure_from_another_period"
        if near_quarter and QUARTER.search(period) and near_quarter not in period:
            return "figure_from_another_period"
    return None


def issuer_named(quote: str, issuer: dict) -> bool:
    low = squash(quote)
    names = {squash(issuer.get("ticker") or "")} | {w for w in squash(issuer.get("name") or "").split()[:1] if len(w) > 2}
    return any(n and n in low for n in names) or any(
        w in f" {low} " for w in (" the company", " we ", " our ", " consolidated", " total company", " company's"))


# Figures listed before 'from <business>, which was sold ...' are that business's, however many there are.
DIVESTED = re.compile(r"\bfrom (?:the |our |its )?[^,.;]{2,80}?,? which (?:was|were|had been|has been|have been|is|are|"
                      r"will be) (?:sold|divested|disposed of|spun[- ]off|deconsolidated|exited|classified as held for sale)\b")
# A business named as discontinued/divested: figures before it in the statement, or right after it.
EXITED = re.compile(r"\b(?:from|of|in|for|at|by) (?:the |our |its )?(?:discontinued operations?|(?:divested|exited|sold|"
                    r"deconsolidated) (?:business(?:es)?|operations?|units?|segments?|subsidiar(?:y|ies)))\b")
SCOPE_BREAK = re.compile(r"[.;]\s|\b(?:including|excluding|of which|compared (?:to|with)|versus|while|whereas)\b")
CLAUSE_BREAK = re.compile(r"[.;]\s|,\s(?:and|but|while|whereas)\s|\b(?:including|excluding|of which|while|whereas)\b")
# '<Named> segment/division/subsidiary', in the original case.
NAMED_UNIT = re.compile(r"\b(?:[A-Z][\w.&'-]*\s+){1,4}(?:segment|division|business unit|subsidiary|joint venture)s?\b")
NAME_WORD = re.compile(r"((?:[A-Z][\w.&'-]*\s+){1,3})$")
GENERIC_WORDS = {
    "total", "consolidated", "net", "adjusted", "operating", "gaap", "non-gaap", "company", "company's", "quarterly",
    "annual", "first", "second", "third", "fourth", "first-quarter", "second-quarter", "third-quarter",
    "fourth-quarter", "q1", "q2", "q3", "q4", "full", "full-year", "year", "fiscal", "record", "our", "the", "its",
    "diluted", "basic", "gross", "organic", "core", "free", "cash", "reported", "comparable", "pro", "forma", "new",
    "current", "prior", "prior-year", "trailing", "global", "international", "domestic", "u.s.", "us", "north",
    "america", "american", "worldwide", "we", "this", "that", "these", "total-company", "quarter", "half", "ytd",
    "effective", "average", "daily", "recurring", "annualized", "product", "services", "service", "subscription",
    "income", "revenue", "revenues", "sales", "ebitda", "eps", "earnings", "margin", "and", "for", "in", "of"}
GENERIC_WORDS |= set(MONTHS.split("|")) | {"each", "all", "every", "other", "both", "reportable", "business", "its"}


def name_words(words: list[str]) -> set[str]:
    return {re.sub(r"'s?$", "", w.lower()) for w in words}


def sentence_initial(flat: str, at: int) -> bool:
    """A word at the start of a sentence or bullet is capitalized by grammar, not because it is a name:
    'Increased net income to $15.6 million' (IPI, 9/28 run) names no business."""
    before = flat[:at].rstrip()
    return not before or before[-1] in ".;:!?•◦"


def scope_problem(metric: str, figures: list[str], quote_raw: str, issuer: dict) -> str | None:
    """An issuer claim must not carry a figure the source ties to a named or divested business:
    'revenue of $63 million, EBITDA of $37 million, and operating income of $26 million from Quail
    Tools, which was sold in August 2025' is none of the company's own totals. Causes and regions
    ('from higher demand', 'from $400 million', 'from international operations') are not a scope,
    and a company total next to a business's part ('$750 million, including $63 million from ...')
    keeps its own figure. The subject is never rewritten: the claim is refused."""
    flat = " ".join(str(quote_raw).translate(PUNCTUATION).split())
    q = flat.lower()
    m = squash(metric)
    positions = [q.find(squash(f)) for f in figures]
    positions = [p for p in positions if p >= 0]
    if not positions:
        return None
    spans = []
    for pattern in (DIVESTED, EXITED):
        for found in pattern.finditer(q):
            if pattern is EXITED and found.group(0).split(" ", 1)[1] in m:
                continue  # 'income from discontinued operations' names its own scope
            start = max([0] + [b.end() for b in SCOPE_BREAK.finditer(q, 0, found.start())])
            spans.append((start, found.start()))
            if pattern is EXITED:
                after = CLAUSE_BREAK.search(q, found.end())
                comma = q.find(", ", found.end())
                ends = [x for x in (after.start() if after else -1, comma) if x >= 0]
                spans.append((found.end(), min(ends) if ends else len(q)))
    if any(a <= p < b for a, b in spans for p in positions):
        return "subject_scope_conflict"
    own = {w for w in squash(issuer.get("name") or "").split() if len(w) > 2} | {squash(issuer.get("ticker") or "")}
    bounds = [0] + [b.end() for b in CLAUSE_BREAK.finditer(q)] + [len(q)]
    for p in positions:
        start = max(b for b in bounds if b <= p)
        end = min([b for b in bounds if b > p] or [len(q)])
        for unit in NAMED_UNIT.finditer(flat, start, end):
            tokens = unit.group(0).split()[:-1]
            words = name_words(tokens[1:] if sentence_initial(flat, unit.start()) else tokens)
            if words - GENERIC_WORDS - own:
                return "subject_scope_conflict"
        # '<Named business> revenue of $63 million': a proper name right before the metric nearest the figure.
        mentions = [x for x in re.finditer(r"(?<![a-z])" + re.escape(m) + r"(?![a-z])", q)] if m else []
        if mentions:
            near = min(mentions, key=lambda x: min(abs(x.start() - p), abs(x.end() - p)))
            if start <= near.start() < end:
                origin = max(start, near.start() - 60)
                name = NAME_WORD.search(flat[origin:near.start()])
                tokens = name.group(1).split() if name else []
                if tokens and sentence_initial(flat, origin + name.start(1)):
                    tokens = tokens[1:]  # 'Quail Tools revenue ...' still keeps 'Tools'
                words = name_words(tokens)
                if words - GENERIC_WORDS - own:
                    return "subject_scope_conflict"
    return None


def gaap_basis(metric: str, quote: str, figures: list[str] | None = None) -> str:
    """The basis the source states for this metric, not for the whole sentence: in 'Operating income
    of $16 million; Adjusted Operating Income of $46 million' operating income is not non-GAAP.
    A metric named adjusted/non-GAAP is non-GAAP; otherwise only 'GAAP'/'non-GAAP' written right
    before the mention of the metric nearest the first figure counts. Without a metric nothing is inferred."""
    m = squash(metric)
    if not m:
        return "unknown"
    if re.search(r"(?<![a-z])(adjusted|non-gaap)(?![a-z])", m):
        return "non-GAAP"
    if re.search(r"(?<![a-z-])gaap(?![a-z])", m):
        return "GAAP"
    mentions = list(re.finditer(r"(?<![a-z])" + re.escape(m) + r"(?![a-z])", quote))
    at = quote.find(squash(figures[0])) if figures else -1
    if at >= 0 and mentions:
        mentions = [min(mentions, key=lambda x: min(abs(x.start() - at), abs(x.end() - at)))]
    for found in mentions:
        before = quote[max(0, found.start() - 12):found.start()]
        if re.search(r"(non-gaap|adjusted)\s+$", before):
            return "non-GAAP"
        if re.search(r"(?<![a-z-])gaap\s+$", before):
            return "GAAP"
    return "unknown"


TEXT_FIELDS = ("document_id", "block_id", "quote", "kind", "subject", "subject_name", "metric", "period", "gaap",
               "note_ko", "direction", "currency", "unit")
LIST_FIELDS = ("figures", "drivers")
# Formatting at the start of a quote only: '◦' and '•' are the same bullet. Nothing inside a quote is dropped.
LEADING_BULLET = re.compile(r"^[•◦]\s*")


def field_type_problem(item: dict) -> str | None:
    """Model fields are used as strings and lists of strings; anything else refuses this item only
    (a list block_id would otherwise break the lookup). Nothing is converted into a new fact."""
    if any(item.get(k) is not None and not isinstance(item[k], str) for k in TEXT_FIELDS):
        return "invalid_field_type"
    if any(item.get(k) is not None and not (isinstance(item[k], list) and all(isinstance(x, str) for x in item[k]))
           for k in LIST_FIELDS):
        return "invalid_field_type"
    return None


def has_forward_wording(quote: str) -> bool:
    """Check normalized wording; the modal 'will' must not match 'goodwill'."""
    return any(word in quote for word in FORWARD) or bool(re.search(r"\bwill\b", quote))


def check_item(item: dict, blocks: dict, issuer: dict, what: str, scopes: dict | None = None) -> tuple[str | None, dict]:
    """(problem, checked item). Structural checks only: passing means 'automatic, unreviewed'."""
    if not isinstance(item, dict):
        return "not_an_object", {}
    problem = field_type_problem(item)
    if problem:
        return problem, {}
    key = (item.get("document_id"), item.get("block_id"))
    if key not in blocks:
        return "unknown_block", {}
    quote_raw = str(item.get("quote", ""))
    quote, block = squash(quote_raw), blocks[key]
    bare = LEADING_BULLET.sub("", quote)  # compared without its bullet; the quote itself is kept as given
    if len(bare) < 8 or bare not in squash(block):
        return "quote_not_in_block", {}
    heading = (scopes or {}).get(key)
    if heading:  # the block sits under a financial-statement heading (P0)
        same = cf.same_entity(heading, issuer.get("name"), issuer.get("aliases"))
        if same is None:
            return "subject_unverified", {}
        if not same:
            return "subject_other_entity", {}  # another company's statements, e.g. an acquired business
    kind = item.get("kind") or "fact"
    if kind not in KINDS:
        return "bad_kind", {}
    figures = [str(f) for f in item.get("figures") or []]
    if kind == "interpretation" and figures:
        return "figures_in_interpretation", {}
    for figure in figures:
        problem = figure_problem(figure, quote_raw)
        if problem:
            return problem, {}
    problem, roles = role_problem(str(item.get("metric") or ""), figures, quote_raw, what)
    if problem:
        return problem, {}
    note = str(item.get("note_ko") or "").strip()
    if not note or len(note) > 160:
        return "bad_note", {}
    if re.search(r"\d", note) or any(word in note.lower() for word in UNIT_WORDS):
        return "number_or_unit_in_note", {}
    if any(word in note for word in FORBIDDEN):
        return "forbidden_wording", {}
    if any(word in note for word in KO_CAUSAL):
        return "causal_claim_about_estimates", {}
    metric = str(item.get("metric") or "").strip()
    if (what == "claim" and kind != "interpretation" and not metric) or (metric and squash(metric) not in quote):
        return "metric_not_in_quote", {}
    if figures and any(token in quote_raw for token in (" | ", " ; ")):
        return "ambiguous_table_figures", {}  # a table row without its header row cannot place its numbers
    if figures and metric:
        problem = metric_problem(metric, figures, quote_raw)
        if problem:
            return problem, {}
    problem = period_problem(item, quote_raw, block)
    if problem:
        return problem, {}
    gaap = item.get("gaap") or "unknown"
    expected = gaap_basis(metric, quote, figures)
    notes = {}
    if squash(gaap) == "adjusted" and expected == "non-GAAP":
        # Prompts up to context-ko-v3 invited 'adjusted'; it counts only where this metric's own
        # basis in the source is non-GAAP, and the model's value is kept beside the result.
        notes["gaap_original"], gaap = gaap, "non-GAAP"
    if gaap != "unknown" and gaap != expected:
        return "gaap_not_as_stated", {}  # an asserted label must be the source's; unknown is filled from it
    currencies = {"$": "USD", "€": "EUR", "£": "GBP"}
    derived = sorted({v for k, v in currencies.items() if any(k in f for f in figures)})
    if item.get("currency") and item["currency"] not in derived:
        return "currency_not_in_figures", {}
    if item.get("unit") and not any(str(item["unit"]).lower() in f.lower() for f in figures):
        return "unit_not_in_figures", {}
    if kind == "fact" and has_forward_wording(quote):
        return "guidance_written_as_fact", {}
    if kind == "guidance" and not has_forward_wording(quote):
        return "guidance_without_forward_wording", {}
    if any(w in note for w in KO_UP) and (not RAISE.search(quote) or LOWER.search(quote)):
        return "raise_not_in_quote", {}
    if any(w in note for w in KO_DOWN) and not LOWER.search(quote):
        return "cut_not_in_quote", {}
    subject = item.get("subject") or "issuer"
    if subject not in SUBJECTS:
        return "bad_subject", {}
    subject_name = str(item.get("subject_name") or "")
    if subject == "issuer" and re.search(r"\b(subsidiary|mplx|customer)\b", quote):
        return "unverified_issuer_subject", {}
    if subject != "issuer" and (not subject_name or squash(subject_name) not in quote):
        return "subject_not_in_quote", {}
    if subject == "issuer" and figures:
        problem = scope_problem(metric, figures, quote_raw, issuer)
        if problem:
            return problem, {}
    core = subject == "issuer" and issuer_named(quote_raw, issuer)
    drivers = list(dict.fromkeys(x for x in item.get("drivers") or [] if x in DRIVERS)) or ["unknown"]
    if what == "claim" and set(item.get("drivers") or []) - set(DRIVERS):
        # A tag outside the list is a label, not a fact: dropped (never guessed into another tag),
        # with the model's tags kept beside the result (AXTI 'customer_demand', 9/30 run).
        notes["drivers_original"] = list(item["drivers"])
    if what == "claim" and item.get("direction", "unknown") not in DIRECTIONS:
        return "bad_tag", {}
    label = METRIC_KO.get(metric.lower(), metric) if metric else ""
    if any(r["role"] == "effect_on_metric" for r in roles):
        label = f"{label}에 미친 영향"  # never the metric's value (PBF special items)
    period = item.get("period") if item.get("period") and item["period"] != "unknown" else ""
    head = "".join([f"[{subject_name}] " if subject != "issuer" else "",
                    f"{label}({metric})" if label and label != metric else label,
                    f" · {period}" if period else ""])
    body = " / ".join(labelled(f, r) for f, r in zip(figures, roles))
    text_ko = f"{head}: {body} — {note}" if head and body else (f"{head} — {note}" if head else note)
    return None, {"text_ko": text_ko, "note_ko": note, "kind": kind, "quote": quote_raw, "document_id": key[0],
                  "block_id": key[1], "metric": metric or None, "figures": figures, "period": item.get("period") or "unknown",
                  "currency": derived[0] if len(derived) == 1 else None, "gaap": expected, "subject": subject,
                  "subject_name": subject_name or None, "core": core,
                  "figure_roles": [r["role"] for r in roles], "figure_readings": roles,
                  "drivers": drivers, "direction": item.get("direction", "unknown"),
                  **({"normalized": notes} if notes else {})}


def excerpt(item) -> dict:
    """What was refused, kept short for review; never used on the card."""
    if not isinstance(item, dict):
        return {}
    return {"note_ko": str(item.get("note_ko") or item.get("text_ko") or "")[:200],
            "figures": [str(f)[:40] for f in (item.get("figures") or [])[:5]] if isinstance(item.get("figures"), list) else [],
            "quote": str(item.get("quote", ""))[:200], "where": f"{item.get('document_id')}#{item.get('block_id')}"}


def validate_draft(answer: dict, blocks: list[dict], issuer: dict | None = None) -> dict:
    index = {(b["document_id"], b["block_id"]): b["text"] for b in blocks}
    scopes = {(b["document_id"], b["block_id"]): b["scope"] for b in blocks if b.get("scope")}
    issuer = issuer or {}
    claims, limitations, rejected = [], [], []
    answer = answer if isinstance(answer, dict) else {}
    for what, items, out, cap in (("claim", answer.get("claims"), claims, 5),
                                  ("limitation", answer.get("limitations"), limitations, 3)):
        for item in (items or [])[:cap] if isinstance(items, list) else []:
            problem, checked = check_item(item, index, issuer, what, scopes)
            if problem:
                rejected.append({"what": what, "reason": problem, **excerpt(item)})
            else:
                out.append(checked)
    link = answer.get("link")
    link_note = None
    if link not in LINKS:
        link_note = "automatic drafts do not assert a direct link" if link == "explicit_link" else "link value missing"
        link = "unconfirmed"
    raw_checks = [x.get("text_ko") if isinstance(x, dict) else x for x in (answer.get("next_check") or [])[:2]] \
        if isinstance(answer.get("next_check"), list) else []
    checks = [x.strip()[:120] for x in raw_checks if isinstance(x, str) and x.strip() and not re.search(r"\d", x)
              and not any(w in x for w in FORBIDDEN) and ("확인" in x or x.strip().endswith("?"))]
    core = [x for x in claims if x["core"] and x["kind"] in ("fact", "guidance")]
    status = ("draft_ready" if core else "insufficient_earnings_context") if claims else "no_supported_claims"
    return {"claims": claims, "limitations": limitations, "next_check": checks, "link": link,
            "link_note": link_note, "rejected": rejected, "context_status": status}


# Stored drafts of these validator versions are re-checked with the current one when read (L1 4.2).
REVALIDATED_VERSIONS = ("context-check-v7", "context-check-v8", "context-check-v9", "context-check-v10")


class RevalidationUnavailable(ValueError):
    """A stored draft cannot be re-checked (document, block or issuer missing or different)."""


def revalidate_record(record: dict, documents: dict[str, dict], issuer: dict | None) -> dict:
    """A stored older-validator draft as the current validator accepts it: only the items it
    accepted then are checked again, on the same source blocks the model saw, for the same issuer.
    Nothing is rescued from what it refused (only excerpts of those are stored), the record itself
    is not changed, and its generation time stays its own. Raises RevalidationUnavailable instead
    of passing anything through unchecked."""
    if record.get("parser_version") not in REVALIDATED_VERSIONS:
        raise RevalidationUnavailable(f"validator {record.get('parser_version')} is not re-checked")
    if not issuer or not issuer.get("cik") or issuer.get("cik") != record.get("issuer_cik"):
        raise RevalidationUnavailable("issuer missing or different from the draft's")
    blocks = []
    for ref in record.get("source_blocks") or []:
        document_id, _, block_id = str(ref).partition("#")
        doc = documents.get(document_id)
        if doc is None or (doc.get("issuer") or {}).get("cik") != record.get("issuer_cik"):
            raise RevalidationUnavailable(f"document {document_id} missing or of another issuer")
        block = next((b for b in doc.get("blocks") or [] if b.get("id") == block_id), None)
        if block is None:
            raise RevalidationUnavailable(f"block {ref} missing")
        blocks.append({"document_id": document_id, "block_id": block_id, "text": cf.block_text(block),
                       "scope": cf.block_scopes(doc.get("blocks") or []).get(block_id)})
    if not blocks:
        raise RevalidationUnavailable("no source blocks recorded")
    checked = validate_draft({"claims": record.get("claims") or [], "limitations": record.get("limitations") or [],
                              "next_check": record.get("next_check") or [], "link": record.get("link")},
                             blocks, issuer)
    return {**record, **{k: checked[k] for k in ("claims", "limitations", "next_check", "link", "context_status")},
            "source_parser_version": record["parser_version"], "display_validator_version": PARSER_VERSION,
            "validation_scope": "accepted_only",
            "revalidation_dropped": [{"what": r["what"], "reason": r["reason"], "quote": r["quote"]}
                                     for r in checked["rejected"]]}


def input_sha(target: dict, document_ids: list[str]) -> str:
    return hashlib.sha256(json.dumps([target["candidate_id"], sorted(document_ids), target.get("eps_target_period"),
                                      PROMPT_VERSION, PARSER_VERSION]).encode()).hexdigest()


def store_context(record: dict) -> bool:
    path = history_dir() / f"{record['context_id']}.json"
    if path.exists():
        return False
    c.atomic_json(path, c.validate_record("candidate_context", record))
    return True


def draft_queue(state: dict, current: dict[str, str], now: datetime) -> list[tuple[str, dict]]:
    """Current candidates only, with documents for the same target fiscal year and no draft for this input."""
    queue = []
    for cid, entry in state["candidates"].items():
        if entry.get("status") != "success" or not entry.get("document_ids") or cid not in current:
            continue
        if entry.get("eps_target_period") != current[cid]:
            continue
        if entry.get("context_input_sha") == input_sha({"candidate_id": cid, **entry}, entry["document_ids"]):
            continue
        if entry.get("draft_next_at") and datetime.fromisoformat(entry["draft_next_at"]) > now:
            continue
        queue.append((cid, entry))
    return sorted(queue, key=lambda pair: pair[1].get("attempted_at", ""))


AUDIT_SCHEMA = 1
AUDIT_MAX_BYTES = 512 * 1024


def audit_dir(day: str) -> Path:
    """Pre-validation copies of each draft attempt: a 30-day run artifact, never read by the pipeline."""
    return c.ROOT / "reports" / "generated" / "context_audit" / day


def code_sha() -> str | None:
    """The commit actually checked out (not the event's head_sha), read without running git."""
    try:
        git = c.ROOT / ".git"
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
        if not head.startswith("ref: "):
            return head
        ref = head[5:]
        if (git / ref).exists():
            return (git / ref).read_text(encoding="utf-8").strip()
        for line in (git / "packed-refs").read_text(encoding="utf-8").splitlines():
            if line.endswith(" " + ref):
                return line.split()[0]
    except OSError:
        pass
    return None


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_audit(record: dict, day: str) -> bool:
    """Atomic, one file per attempt, at most AUDIT_MAX_BYTES. A copy too large keeps its hash and
    size, drops the biggest fields and says truncated=true (not usable for a full comparison)."""
    try:
        body = json.dumps(record, ensure_ascii=False, indent=1)
        size = len(body.encode("utf-8"))
        if size > AUDIT_MAX_BYTES:
            record = {**record, "truncated": True, "original_bytes": size, "original_sha256": sha256_text(body)}
            for key in ("blocks", "prompt", "raw_response", "answer", "validation"):
                if key in record:
                    dropped = json.dumps(record[key], ensure_ascii=False)
                    record[key] = {"dropped": True, "sha256": sha256_text(dropped),
                                   "bytes": len(dropped.encode("utf-8"))}
                body = json.dumps(record, ensure_ascii=False, indent=1)
                if len(body.encode("utf-8")) <= AUDIT_MAX_BYTES:
                    break
        path = audit_dir(day) / f"{record['attempt_id']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        c.atomic_json(path, json.loads(body))
        return True
    except (OSError, ValueError, TypeError):
        return False


def draft_order(queue: list[tuple[str, dict]], folded: set[str], remaining: int, folded_slots: int) -> list:
    """Card companies first, but folded_slots of today's remaining model requests stay for folded
    companies when any wait; requests they cannot use go back to the cards (P1-B)."""
    cards = [q for q in queue if q[0] not in folded]
    others = [q for q in queue if q[0] in folded]
    keep = min(len(others), max(0, folded_slots))
    head = max(0, remaining - keep)
    return cards[:head] + others[:keep] + cards[head:] + others[keep:]


def run_drafts(now: datetime | None = None, call=None, deadline: float | None = None,
               current: dict[str, str] | None = None, clock=time.monotonic, folded: list[str] | None = None) -> dict:
    """One company per model request and one attempt per company in a run; a failed company
    waits 24 hours so the others get their turn. Budget, provider block and time are checked
    before every request (and inside the shared model call)."""
    import extract
    now = now or datetime.now(timezone.utc)
    state = load_state()
    api_key = c.load_dotenv_value("GEMINI_API_KEY")
    report = {"requests": 0, "drafted": 0, "insufficient_earnings_context": 0, "no_supported_claims": 0,
              "deferred": 0, "failed": 0}
    deadline = deadline or (clock() + settings()["time_budget_s"])
    raw_seen: dict = {}  # filled by the real provider call only; an injected call leaves it empty
    if call is None:
        if not api_key:
            report["skipped"] = "model_key_missing"
            return report

        def call(prompt):
            return extract.call_gemini_prompt(prompt, api_key, "candidate_context", timeout=60, thinking_budget=0,
                                              deadline=deadline, max_attempts=1, clock=clock, raw=raw_seen)
    day = c.today()
    run_id = "-".join(x for x in (os.environ.get("GITHUB_RUN_ID"), os.environ.get("GITHUB_RUN_ATTEMPT")) if x) or "local"
    sha_of_code = code_sha()
    if current is None:
        current = {cid: e.get("eps_target_period") for cid, e in state["candidates"].items()}
    queue = draft_order(draft_queue(state, current, now), set(folded or []),
                        c.model_calls_remaining("candidate_context"), settings()["folded_drafts_per_day"])
    for cid, entry in queue:
        blocked = c.model_provider_blocked()
        if blocked or c.model_calls_remaining("candidate_context") <= 0 or deadline - clock() < 5:
            report["deferred"] += 1
            entry["draft_status"] = "deferred_budget" if not blocked else "provider_rate_limited"
            continue
        documents = [d for d in (cf.load_document(x) for x in entry["document_ids"]) if d]
        target = {"candidate_id": cid, "ticker": entry.get("ticker"), "eps_target_period": entry.get("eps_target_period"),
                  "issuer_name": (entry.get("issuer") or {}).get("name")}
        blocks, coverage_state = relevant_blocks(documents)
        sha = input_sha({"candidate_id": cid, **entry}, entry["document_ids"])
        before_calls = c.model_calls_today()
        before_component = component_calls(day)
        prompt = draft_prompt(target, documents, blocks)
        started = datetime.now(timezone.utc)
        raw_seen.clear()
        audit = {"schema_version": AUDIT_SCHEMA, "attempt_id": f"{started:%Y%m%dT%H%M%S%fZ}-{cid}",
                 "candidate_id": cid, "ticker": entry.get("ticker"), "issuer": entry.get("issuer"),
                 "eps_target_period": entry.get("eps_target_period"), "run_id": run_id, "code_sha": sha_of_code,
                 "provider": "gemini", "model": extract.GEMINI_MODEL, "prompt_version": PROMPT_VERSION,
                 "parser_version": PARSER_VERSION, "input_sha": sha,
                 "started_at": started.isoformat(timespec="seconds"),
                 "documents": [{"document_id": d["document_id"], "raw_sha256": d.get("raw_sha256"),
                                "coverage": d.get("coverage")} for d in documents],
                 "blocks": blocks, "source_coverage": coverage_state, "prompt": prompt,
                 "prompt_sha256": sha256_text(prompt)}

        audit_failed = []

        def finish(outcome, **fields):
            """Rewrites this attempt's one file; a failed write is counted once per attempt."""
            audit.update(outcome=outcome, finished_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         budget={"candidate_context_before": before_component,
                                 "candidate_context_after": component_calls(day),
                                 "requests_sent": c.model_calls_today() - before_calls},
                         raw_response={"available": "text" in raw_seen,
                                       **{k: raw_seen.get(k) for k in ("text", "finish_reason", "usage")}},
                         **fields)
            if not write_audit(audit, day) and not audit_failed:
                audit_failed.append(True)
                report["audit_write_failed"] = report.get("audit_write_failed", 0) + 1

        try:
            answer = call(prompt)  # one company per request
        except c.ModelBudgetExhausted as reason:
            report["requests"] += c.model_calls_today() - before_calls
            entry["draft_status"] = "provider_rate_limited" if "rate" in str(reason) else "deferred_budget"
            report["deferred"] += 1
            finish("deferred", error={"type": "ModelBudgetExhausted", "reason": str(reason)[:60]})
            continue
        except (OSError, ValueError, KeyError, IndexError, TimeoutError) as error:
            report["requests"] += c.model_calls_today() - before_calls
            entry.update(draft_status="failed", draft_error=type(error).__name__,
                         draft_next_at=(now + timedelta(hours=settings()["retry_failed_hours"])).isoformat(timespec="seconds"))
            report["failed"] += 1
            c.atomic_json(state_path(), state)
            # Type and HTTP status only: an exception's text can carry a URL.
            finish("failed", error={"type": type(error).__name__, "http_status": getattr(error, "code", None)})
            continue
        report["requests"] += c.model_calls_today() - before_calls
        answer_copy = json.loads(json.dumps(answer, ensure_ascii=False, default=str))
        finish("answered_unvalidated", answer=answer_copy)  # kept even if the validator breaks
        try:
            checked = validate_draft(answer, blocks, {**(entry.get("issuer") or {}), "ticker": entry.get("ticker")})
        except Exception as error:
            # An internal validator bug is recorded and then surfaces; it never becomes '0 drafts'.
            finish("validation_error", answer=answer_copy, validation_error={"type": type(error).__name__})
            raise
        record = {"context_id": "CTX-" + sha[:16].upper(), "candidate_id": cid, "ticker": entry.get("ticker"),
                  "issuer_cik": (entry.get("issuer") or {}).get("cik"), "document_ids": entry["document_ids"],
                  "eps_target_period": entry.get("eps_target_period"),
                  "source_blocks": [f"{b['document_id']}#{b['block_id']}" for b in blocks], "input_sha": sha,
                  "model": extract.GEMINI_MODEL, "prompt_version": PROMPT_VERSION, "parser_version": PARSER_VERSION,
                  "generated_at": now.isoformat(timespec="seconds"),
                  "source_coverage": coverage_state, "review": "자동 정리·미검토", **checked}
        stored = store_context(record)
        # 'Audit written' and 'CTX stored' are separate facts.
        finish("answered", answer=answer_copy, validation=checked, context_id=record["context_id"], ctx_stored=stored)
        status = checked["context_status"]
        entry.update(draft_status=status, context_id=record["context_id"], context_input_sha=sha)
        entry.pop("draft_next_at", None)
        report["drafted" if status == "draft_ready" else status] += 1
        c.atomic_json(state_path(), state)
    c.atomic_json(state_path(), state)
    return report


def component_calls(day: str) -> int:
    return c.read_json(c.DATA_DIR / "model_budget.json", {}).get("days", {}).get(day, {}).get("candidate_context", 0)


def coverage(state: dict, ids: list[str]) -> dict:
    counts: dict[str, int] = {}
    for cid in ids:
        status = state["candidates"].get(cid, {}).get("status", "queued")
        counts[status] = counts.get(status, 0) + 1
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh-issuers", action="store_true")
    args = parser.parse_args(argv)
    if args.refresh_issuers:
        # Share the normal daily HTTP accounting without invoking the screener.
        state = load_state()
        usage = state["days"].setdefault(c.today(), {"companies": 0, "http_attempts": 0})
        def reserve():
            usage["http_attempts"] += 1
            c.atomic_json(state_path(), state)
        client = cf.SecClient(user_agent=os.environ.get("SEC_USER_AGENT") or "investment-research-system/2.0",
            attempts_left=max(0, settings()["http_attempts_per_day"] - usage["http_attempts"]),
            deadline=time.monotonic() + settings()["time_budget_s"], on_attempt=reserve)
        print(f"[issuers] {refresh_issuers(client)} verified entries")
        return 0
    try:
        # One time budget for sources and drafts together; state is saved after each company.
        deadline = time.monotonic() + settings()["time_budget_s"]
        report = run_sources(deadline=deadline)
        report["drafts"] = ({"held": True} if report["held"] else
                            run_drafts(deadline=deadline, current=report.get("current", {}),
                                       folded=report.get("folded", [])))
    except (OSError, ValueError, KeyError) as error:
        c.record_run("candidate_context", "failed", error_type=type(error).__name__)
        print(f"[context] failed: {type(error).__name__}")
        return 1
    # Some documents unreachable, SEC blocked, or drafts failing: the step ran but its data is partial.
    troubled = (report["statuses"].get("failed") or report.get("blocked") or report.get("partial_sources")
                or report["drafts"].get("failed"))
    status = "held" if report["held"] else ("degraded" if troubled else "success")
    c.record_run("candidate_context", status, **{k: v for k, v in report.items() if k != "day"})
    print(f"[context] {json.dumps(report, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
