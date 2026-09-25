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
                                    deadline=deadline or time.monotonic() + cfg["time_budget_s"],
                                    timeout_s=cfg["timeout_s"],
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


# ------------------------------------------------------------------ G2 drafts

PROMPT_VERSION = "context-ko-v1"
PARSER_VERSION = "context-check-v1"
KINDS = ("fact", "guidance", "interpretation")
DRIVERS = ("volume", "price", "mix", "margin_cost", "capacity", "backlog", "buyback_sharecount", "tax", "fx",
           "acquisition_disposal", "one_off", "accounting", "unknown")
DIRECTIONS = ("positive", "negative", "mixed", "unknown")
LINKS = ("temporal_context", "explicit_link", "unconfirmed")
FINANCIAL_TERMS = ("revenue", "sales", "net income", "earnings per share", "eps", "margin", "operating income",
                   "guidance", "outlook", "expect", "backlog", "orders", "restructuring", "impairment", "one-time",
                   "non-recurring", "tax", "repurchase", "buyback", "shares outstanding", "acquisition", "divest",
                   "demand", "pricing", "price", "volume", "capacity", "gain", "charge", "gaap")
FORWARD = ("expect", "outlook", "guidance", "forecast", "anticipate", "project", "will ", "target")
RAISE = ("raise", "raised", "increase", "increased", "higher", "above", "up from", "improv")
LOWER = ("lower", "lowered", "reduce", "reduced", "cut", "decrease", "decreased", "below", "down from", "declin")
KO_UP = ("상향", "인상", "올렸", "높였", "늘렸")
KO_DOWN = ("하향", "인하", "낮췄", "줄였")
KO_CAUSAL = ("상향 원인", "때문에 추정치", "추정치가 올랐", "상향을 이끌", "상향의 원인")
FORBIDDEN = ("매수", "목표가", "저평가", "상승 확률")
MAX_PROMPT_CHARS = 12000


def history_dir() -> Path:
    return c.DATA_DIR / "candidate_context_history"


def squash(text: str) -> str:
    return " ".join(str(text).split()).casefold()


def relevant_blocks(documents: list[dict], limit: int = MAX_PROMPT_CHARS) -> tuple[list[dict], str]:
    """Blocks that mention financial terms (any industry), in document order; coverage says if cut."""
    chosen, used, complete = [], 0, True
    for doc in documents:
        if doc.get("coverage") == "partial":
            complete = False
        for block in doc["blocks"]:
            text = cf.block_text(block)
            if not any(term in text.lower() for term in FINANCIAL_TERMS):
                continue
            if used + len(text) > limit:
                complete = False
                continue
            chosen.append({"document_id": doc["document_id"], "block_id": block["id"], "text": text})
            used += len(text)
    return chosen, "complete" if complete else "partial"


def draft_prompt(target: dict, documents: list[dict], blocks: list[dict]) -> str:
    heads = [{"document_id": d["document_id"], "form": d["form"], "type": d["document_type"], "title": d["title"],
              "filed_at": d["filed_at"], "report_date": d.get("report_date")} for d in documents]
    return (
        "너는 미국 상장사 공식 공시 원문에서 사실만 정리하는 도우미다. 아래 문단/표만 근거로 JSON 하나를 출력하라.\n"
        f"회사: {target['ticker']}. 애널리스트의 내년 EPS 예상치가 최근 올라 검토 대상이 됐다(대상 회계연도 말 "
        f"{target.get('eps_target_period')}). 이 발표가 그 상향을 일으켰다고 단정하지 마라.\n"
        "규칙: (1) 각 claim의 quote는 해당 block의 문장을 글자 그대로 짧게 인용한다. (2) text_ko 안의 숫자는 quote에 있는 숫자만 쓴다. "
        "(3) 실적은 kind=fact, 회사 전망은 kind=guidance, 네 해석은 kind=interpretation. (4) 이전 전망과의 비교는 원문이 직접 말할 때만 쓴다. "
        "(5) 일회성 이익·세금·자사주 매입에 의한 주당 수치 변화는 영업 성장으로 쓰지 마라. (6) 반대 근거(하향 전망, 수요 둔화, 일회성 요인)도 limitations에 넣어라. "
        "(7) 매수·목표가·주가 전망을 쓰지 마라. (8) 추정치 상향과의 연결은 원문이 명시하지 않으면 link=unconfirmed 또는 temporal_context.\n"
        f"drivers 값: {', '.join(DRIVERS)}. direction 값: {', '.join(DIRECTIONS)}.\n"
        '출력 형식: {"claims":[{"text_ko":"","kind":"fact|guidance|interpretation","quote":"","document_id":"","block_id":"",'
        '"period":"","currency":"","unit":"","gaap":"GAAP|non-GAAP|unknown","drivers":[""],"direction":""}],'
        '"limitations":[{"text_ko":"","quote":"","document_id":"","block_id":""}],"next_check":[""],'
        '"link":"temporal_context|explicit_link|unconfirmed"}\n최대 claims 5개, limitations 3개, next_check 2개.\n\n'
        f"문서: {json.dumps(heads, ensure_ascii=False)}\n\n블록:\n"
        + "\n".join(f"[{b['document_id']}#{b['block_id']}] {b['text']}" for b in blocks))


def numbers(text: str) -> set[str]:
    return {n.replace(",", "").rstrip(".") for n in re.findall(r"\d[\d,]*\.?\d*", str(text))}


def check_quote(item: dict, blocks: dict) -> str | None:
    key = (item.get("document_id"), item.get("block_id"))
    if key not in blocks:
        return "unknown_block"
    quote = squash(item.get("quote", ""))
    if len(quote) < 8 or quote not in squash(blocks[key]):
        return "quote_not_in_block"
    if not numbers(item.get("text_ko", "")) <= numbers(item.get("quote", "")):
        return "number_not_in_quote"
    text = item.get("text_ko", "")
    if not text.strip() or any(word in text for word in FORBIDDEN):
        return "forbidden_or_empty"
    return None


def check_claim(item: dict, blocks: dict) -> str | None:
    """Structural checks only; passing is 'automatically organized, not reviewed'."""
    problem = check_quote(item, blocks)
    if problem:
        return problem
    text, quote = item.get("text_ko", ""), item.get("quote", "").lower()
    if item.get("kind") not in KINDS:
        return "bad_kind"
    if item.get("direction", "unknown") not in DIRECTIONS:
        return "bad_direction"
    if not set(item.get("drivers") or ["unknown"]) <= set(DRIVERS):
        return "bad_driver"
    if item["kind"] == "fact" and any(word in quote for word in FORWARD):
        return "guidance_written_as_fact"
    if item["kind"] == "guidance" and not any(word in quote for word in FORWARD):
        return "guidance_without_forward_wording"
    if any(word in text for word in KO_CAUSAL):
        return "causal_claim_about_estimates"  # checked first: it also contains 'raise' words
    if any(word in text for word in KO_UP) and (not any(w in quote for w in RAISE) or any(w in quote for w in LOWER)):
        return "raise_not_in_quote"
    if any(word in text for word in KO_DOWN) and not any(w in quote for w in LOWER):
        return "cut_not_in_quote"
    return None


def validate_draft(answer: dict, blocks: list[dict]) -> dict:
    index = {(b["document_id"], b["block_id"]): b["text"] for b in blocks}
    claims, limitations, rejected = [], [], []
    for item in (answer.get("claims") or [])[:5] if isinstance(answer, dict) else []:
        problem = check_claim(item, index) if isinstance(item, dict) else "not_an_object"
        if problem:
            rejected.append({"what": "claim", "reason": problem})
            continue
        claims.append({k: item.get(k) for k in ("text_ko", "kind", "quote", "document_id", "block_id", "period",
                                                  "currency", "unit", "gaap", "drivers", "direction")})
    for item in (answer.get("limitations") or [])[:3] if isinstance(answer, dict) else []:
        problem = check_quote(item, index) if isinstance(item, dict) else "not_an_object"
        if problem:
            rejected.append({"what": "limitation", "reason": problem})
            continue
        limitations.append({k: item.get(k) for k in ("text_ko", "quote", "document_id", "block_id")})
    link = answer.get("link") if isinstance(answer, dict) else None
    link_note = None
    if link not in LINKS:
        link, link_note = "unconfirmed", "link value missing"
    elif link == "explicit_link" and not any(w in squash(b["text"]) for b in blocks
                                             for w in ("analyst", "consensus", "estimate revision")):
        link, link_note = "unconfirmed", "explicit link not stated in the source"
    checks = [str(x)[:120] for x in (answer.get("next_check") or [])[:2] if str(x).strip()
              and not any(w in str(x) for w in FORBIDDEN)] if isinstance(answer, dict) else []
    return {"claims": claims, "limitations": limitations, "next_check": checks, "link": link,
            "link_note": link_note, "rejected": rejected}


def input_sha(target: dict, document_ids: list[str]) -> str:
    return hashlib.sha256(json.dumps([target["candidate_id"], sorted(document_ids), target.get("eps_target_period"),
                                      PROMPT_VERSION, PARSER_VERSION]).encode()).hexdigest()


def store_context(record: dict) -> bool:
    path = history_dir() / f"{record['context_id']}.json"
    if path.exists():
        return False
    c.atomic_json(path, c.validate_record("candidate_context", record))
    return True


def run_drafts(now: datetime | None = None, call=None, deadline: float | None = None) -> dict:
    """At most one company per model request; budget and time are checked before each request."""
    import extract
    now = now or datetime.now(timezone.utc)
    state = load_state()
    api_key = c.load_dotenv_value("GEMINI_API_KEY")
    report = {"drafted": 0, "no_supported_claims": 0, "deferred_budget": 0, "failed": 0}
    if call is None:
        if not api_key:
            report["skipped"] = "model_key_missing"
            return report
        call = lambda prompt: extract.call_gemini_prompt(prompt, api_key, "candidate_context")  # noqa: E731
    deadline = deadline or (time.monotonic() + settings()["time_budget_s"])
    waiting = sorted(((cid, e) for cid, e in state["candidates"].items()
                      if e.get("status") == "success" and e.get("document_ids")
                      and e.get("context_input_sha") != input_sha({"candidate_id": cid, **e}, e["document_ids"])),
                     key=lambda pair: pair[1].get("attempted_at", ""))
    for cid, entry in waiting:
        if c.model_calls_remaining("candidate_context") <= 0:
            report["deferred_budget"] += 1
            entry["draft_status"] = "deferred_budget"
            continue
        if time.monotonic() >= deadline:
            entry["draft_status"] = "deferred_budget"
            report["deferred_budget"] += 1
            continue
        documents = [d for d in (cf.load_document(x) for x in entry["document_ids"]) if d]
        target = {"candidate_id": cid, "ticker": entry.get("ticker"), "eps_target_period": entry.get("eps_target_period")}
        blocks, coverage_state = relevant_blocks(documents)
        sha = input_sha({"candidate_id": cid, **entry}, entry["document_ids"])
        try:
            answer = call(draft_prompt(target, documents, blocks))
        except c.ModelBudgetExhausted:
            entry["draft_status"] = "deferred_budget"
            report["deferred_budget"] += 1
            continue
        except (OSError, ValueError, KeyError, IndexError, TimeoutError) as error:
            entry.update(draft_status="failed", draft_error=type(error).__name__)
            report["failed"] += 1
            continue
        checked = validate_draft(answer, blocks)
        status = "draft_ready" if checked["claims"] else "no_supported_claims"
        record = {"context_id": "CTX-" + sha[:16].upper(), "candidate_id": cid, "ticker": entry.get("ticker"),
                  "issuer_cik": (entry.get("issuer") or {}).get("cik"), "document_ids": entry["document_ids"],
                  "source_blocks": [f"{b['document_id']}#{b['block_id']}" for b in blocks], "input_sha": sha,
                  "model": extract.GEMINI_MODEL, "prompt_version": PROMPT_VERSION, "parser_version": PARSER_VERSION,
                  "generated_at": now.isoformat(timespec="seconds"), "context_status": status,
                  "source_coverage": coverage_state, "review": "자동 정리·미검토", **checked}
        store_context(record)
        entry.update(draft_status=status, context_id=record["context_id"], context_input_sha=sha)
        report["drafted" if status == "draft_ready" else "no_supported_claims"] += 1
        c.atomic_json(state_path(), state)
    c.atomic_json(state_path(), state)
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
        # One time budget for sources and drafts together; state is saved after each company.
        deadline = time.monotonic() + settings()["time_budget_s"]
        report = run_sources(deadline=deadline)
        report["drafts"] = run_drafts(deadline=deadline)
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
