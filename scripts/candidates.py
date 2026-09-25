"""Screener candidates as one model for cards, Telegram and the HTML view.

Cards, commands and pages all read what this module builds; none of them
compute their own numbers or order.

Identity
  candidate_id = "CAN-" + first 16 hex of SHA256(entity_id | thesis_key).
  entity_id comes from config/entities.json when the ticker is registered,
  otherwise from the SEC exchange list the screener read ("NASDAQ:AEHR", the
  same form as the registry). A CIK is never guessed. The screener thesis is
  "eps-revision-review:v1": review the business cause and persistence of an
  EPS estimate upgrade. It does not claim a bottleneck.

Versions and observations
  candidate_version is a hash of what the card claims: identity, raw estimate
  numbers, target period and basis, which screen lists it met, data status,
  explanations and their sources. Each version is stored once, immutably, in
  candidate_history/{version}.json.
  Every time a candidate is seen, an immutable observation is stored in
  candidate_observations/{observation_id}.json: the real observation time, the
  source snapshot path and full SHA256, the price window, ranks, quality, the
  price-based yield change and the version it showed. First/last seen and the
  version timeline are rebuilt from observations, never from version files.

States (kept separate)
  data quality          complete / partial run / needs_evidence reasons
  classification        found / needs_evidence / recommended
  tracking              untracked / tracked / closed (from the review ledger)
  recommended needs human evidence for all five explanations, every statement
  linked to a stored source, and an approval of exactly the current version.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

THESIS_KEY = "eps-revision-review:v1"
GENERATOR_VERSION = "cards-v3"
TRANSLATION_PROMPT_VERSION = "company-ko-v1"
CAN_PATTERN = re.compile(r"^CAN-[0-9A-Fa-f]{16}$")
EXPLANATIONS = ("earnings_path", "persistence_evidence", "market_expectation_gap", "falsification", "next_check")
STATEMENT_KINDS = ("fact", "guidance", "consensus", "interpretation")
EXCHANGE_IDS = {"Nasdaq": "NASDAQ", "NYSE": "NYSE"}
DEFAULTS = {"stale_hours": 36, "translation_batch": 10, "translation_max_calls": 3}
EXPLANATION_LABELS = {
    "earnings_path": "이익 경로", "persistence_evidence": "지속 근거",
    "market_expectation_gap": "시장 기대와의 차이(한계 포함)", "falsification": "반증 조건",
    "next_check": "다음 점검",
}
PRICE_NOTES = {
    "chart_mismatch": "차트 식별 정보 불일치", "malformed_series": "시세 배열 이상",
    "no_prices": "확정 종가 없음", "calendar_unsupported": "거래일 달력 범위 밖",
    "stale_end_price": "최근 종가가 오래됨", "window_not_covered": "90일 전 종가 없음(거래 기간 부족)",
    "stale_start_price": "시작 종가가 기준일보다 7일 넘게 이전", "split_in_window": "기간 중 주식분할(PER 비교 생략)",
    "price_not_retrieved": "주가 조회 실패",
    "legacy_version_only": "과거 기록에 주가 비교 없음",
}


# ------------------------------------------------------------------ paths

def cards_dir() -> Path:
    return c.DATA_DIR / "candidates"


def index_path() -> Path:
    return cards_dir() / "index.json"


def history_dir() -> Path:
    return c.DATA_DIR / "candidate_history"


def observations_dir() -> Path:
    return c.DATA_DIR / "candidate_observations"


def evidence_path() -> Path:
    return c.DATA_DIR / "candidate_evidence.json"


def translation_path() -> Path:
    return c.DATA_DIR / "translation_cache.json"


def rejection_path() -> Path:
    return c.DATA_DIR / "translation_rejects.json"


def settings() -> dict:
    return {**DEFAULTS, **c.policy().get("candidate_cards", {})}


# ------------------------------------------------------------------ identity

def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def normalize_id(text: str) -> str | None:
    value = str(text or "").strip()
    return "CAN-" + value[4:].upper() if CAN_PATTERN.fullmatch(value) else None


def candidate_id(entity_id: str, thesis_key: str = THESIS_KEY) -> str:
    return "CAN-" + hashlib.sha256(f"{entity_id}|{thesis_key}".encode("utf-8")).hexdigest()[:16].upper()


def identify(row: dict, registry: dict) -> dict:
    """Entity from the registry, else from the SEC exchange the screener read; never guessed."""
    ticker = row["ticker"]
    if ticker in registry:
        return {"entity_id": registry[ticker]["entity_id"], "ticker": ticker,
                "exchange": registry[ticker].get("exchange"), "source": "config/entities.json", "verified": True}
    exchange = EXCHANGE_IDS.get(row.get("exchange") or "")
    if exchange:
        return {"entity_id": f"{exchange}:{ticker}", "ticker": ticker, "exchange": exchange,
                "source": "SEC company_tickers_exchange", "verified": True}
    return {"entity_id": None, "ticker": ticker, "exchange": None, "source": None, "verified": False}


# ------------------------------------------------------------------ snapshot choice

def read_snapshot(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def choose_snapshot(paths: list[Path], now: datetime, stale_hours: float) -> dict:
    """The latest usable screener run, and why it may be stale.

    A failed latest attempt never replaces the last valid result; it marks it stale.
    """
    import screen_revisions
    ordered = sorted(paths, key=screen_revisions.snapshot_key)
    latest_attempt, valid = None, None
    for path in reversed(ordered):
        snapshot = read_snapshot(path)
        run = snapshot.get("run", {})
        latest_attempt = latest_attempt or {"path": path, "run": run}
        if run.get("status") in ("success", "degraded"):
            valid = {"path": path, "snapshot": snapshot}
            break
    stale = []
    if valid is None:
        return {"valid": None, "latest_attempt": latest_attempt, "stale": ["no_valid_screen"]}
    if latest_attempt["path"] != valid["path"]:
        stale.append(f"latest_attempt_{latest_attempt['run'].get('status')}")
    finished = datetime.fromisoformat(valid["snapshot"]["run"]["finished_at"])
    if now - finished > timedelta(hours=stale_hours):
        stale.append("old_observation")
    return {"valid": valid, "latest_attempt": latest_attempt, "stale": stale}


def screen_attempt_stale(state: dict, valid_run_id: str | None) -> list[str]:
    """A newer screen attempt with no usable result, from the daily run record.

    Covers attempts that never wrote a snapshot (timeout, killed runner, a plan that
    invalidated screen and stopped). A later success whose snapshot is the one in use
    clears it. Only execution status counts: an 'unknown' quality from schema 1 is not a failure.
    """
    days = [day for day, record in sorted(state.get("days", {}).items(), reverse=True)
            if "screen" in record.get("steps", {})]
    if not days:
        return []
    entry = state["days"][days[0]]["steps"]["screen"]
    status = entry.get("execution_status") or entry.get("status")
    attempt = entry.get("planned_by") if status == "pending" else entry.get("run_id")
    if status == "success":
        return [] if attempt == valid_run_id or valid_run_id is None else ["latest_screen_result_missing"]
    if attempt == valid_run_id:
        return []
    return [f"latest_screen_{status or 'unknown'}"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def current_freshness(index: dict, now: datetime | None = None) -> list[str]:
    """Why these cards must not be acted on now (approval, automatic alerts); empty = fresh.

    Re-checked at the moment of acting, from stored files only (no network, translation or
    ledger write): the stored stale reasons, the age of the source data (not of the render),
    a newer usable snapshot than the one the cards use, and the daily record's latest screen
    attempt. Viewing old cards stays allowed; acting on them does not.
    """
    import screen_revisions
    now = now or now_utc()
    hours = settings()["stale_hours"]
    reasons = list(index.get("stale") or [])
    ref = index.get("source_snapshot") or {}
    if not index.get("observed_at"):
        reasons.append("no_valid_screen")
    elif now - datetime.fromisoformat(index["observed_at"]) > timedelta(hours=hours):
        reasons.append("old_observation")
    latest = choose_snapshot(list(screen_revisions.SCREEN_DIR.glob("*.json.gz")), now, hours)["valid"]
    if latest and Path(ref.get("path", "")).name != latest["path"].name:
        reasons.append("newer_snapshot_not_in_cards")
    reasons += screen_attempt_stale(c.read_json(c.DATA_DIR / "daily_runs.json", {}), ref.get("run_id"))
    return list(dict.fromkeys(reasons))


# ------------------------------------------------------------------ ordering

def display_order(derived: dict) -> list[tuple[str, list[dict]]]:
    """A1, B1, A2, B2, ... with each company once. A slot order, not a combined score."""
    lists = {"A": derived.get("top_yield", []), "B": derived.get("top_growth", [])}
    seen: dict[str, list[dict]] = {}
    for i in range(max(len(lists["A"]), len(lists["B"]))):
        for name in ("A", "B"):
            if i < len(lists[name]):
                ticker = lists[name][i]
                seen.setdefault(ticker, []).append({"list": name, "rank": i + 1})
    return list(seen.items())


# ------------------------------------------------------------------ building

def price_block(row: dict) -> dict:
    keys = ("price_status", "price_note", "price_basis", "price_start_target", "price_start_date",
            "price_end_expected", "price_end_date", "close_start", "close_end", "price_pct_90",
            "adj_return_pct_90", "pe_change_pct")
    block = {k: row.get(k) for k in keys}
    if block["price_status"] is None:
        block.update(price_status="failed", price_note="price_not_retrieved")
    return block


def ledger_tracking(entity_id: str | None, ideas: list[dict], thesis: str = THESIS_KEY) -> dict:
    """tracked: this thesis is tracked. entity_tracked: the company is tracked under another
    thesis only (never merged automatically). closed / untracked."""
    if not entity_id:
        return {"status": "untracked", "idea_ids": []}
    rows = [r for r in ideas if r.get("entity_id") == entity_id]
    active = [r for r in rows if r.get("현재 단계") != "제외" and r.get("검토 상태") != "종료"]
    same = [r for r in active if r.get("thesis_key") == thesis]
    if same:
        return {"status": "tracked", "idea_ids": [r["idea_id"] for r in same]}
    if active:
        return {"status": "entity_tracked", "idea_ids": [r["idea_id"] for r in active]}
    if rows:
        return {"status": "closed", "idea_ids": [r["idea_id"] for r in rows]}
    return {"status": "untracked", "idea_ids": []}


def evidence_problems(entry: dict | None) -> list[str]:
    """Why human evidence is not enough for a recommendation (empty = sufficient)."""
    if not entry:
        return ["evidence_missing"]
    problems = [f"source_{s.get('id') or '?'}_incomplete" for s in entry.get("sources", []) if not source_complete(s)]
    sources = {s.get("id") for s in entry.get("sources", []) if source_complete(s)}
    if entry.get("review_status") == "needs_evidence":
        problems.append("marked_needs_evidence")
    for field in EXPLANATIONS:
        statements = entry.get("explanations", {}).get(field) or []
        if not statements:
            problems.append(f"{field}_missing")
        for statement in statements:
            if statement.get("kind") not in STATEMENT_KINDS or not str(statement.get("text", "")).strip():
                problems.append(f"{field}_invalid_statement")
            elif not statement.get("source_ids") or not set(statement["source_ids"]) <= sources:
                problems.append(f"{field}_unsourced")
    return sorted(set(problems))


def source_complete(source: dict) -> bool:
    """A cited source names what it is, who published it, when it was seen and what it supports.
    published_at may be null (unknown) but must be stated."""
    def dated(value):
        try:
            datetime.fromisoformat(str(value)[:10])
            return True
        except ValueError:
            return False
    return (bool(source.get("id")) and safe_url(source.get("url")) and bool(str(source.get("title", "")).strip())
            and bool(str(source.get("provider", "")).strip()) and dated(source.get("observed_at"))
            and "published_at" in source and (source["published_at"] is None or dated(source["published_at"]))
            and bool(str(source.get("quote") or source.get("fields") or "").strip()))


def evidence_hash(entry: dict | None) -> str:
    return digest({k: v for k, v in (entry or {}).items() if k != "approval"})


def safe_url(url: Any) -> bool:
    return isinstance(url, str) and re.match(r"^https?://", url) is not None and "crumb=" not in url


def base_sources(ticker: str, observed_at: str, profile_observed: bool) -> list[dict]:
    symbol = ticker.replace(".", "-")
    sources = [{"id": "yahoo-estimates", "title": f"{ticker} analyst estimates (EPS trend)",
                "provider": "Yahoo Finance", "url": f"https://finance.yahoo.com/quote/{symbol}/analysis",
                "published_at": None, "observed_at": observed_at,
                "fields": "earningsTrend +1y: current, 30/90 days ago, up/down last 30 days, analysts"},
               {"id": "yahoo-price", "title": f"{ticker} daily closes", "provider": "Yahoo Finance",
                "url": f"https://finance.yahoo.com/quote/{symbol}/history", "published_at": None,
                "observed_at": observed_at, "fields": "chart close (split-adjusted)"}]
    if profile_observed:
        sources.append({"id": "yahoo-profile", "title": f"{ticker} company profile", "provider": "Yahoo Finance",
                        "url": f"https://finance.yahoo.com/quote/{symbol}/profile", "published_at": None,
                        "observed_at": observed_at, "fields": "assetProfile industry, sector, business summary"})
    return sources


# EPS fields that identify the claim. yield_change_* divides by the price, so it is an observation.
VERSION_EPS_KEYS = ("eps_now", "eps_30d", "eps_90d", "eps_target_period", "eps_currency", "eps_basis",
                    "analysts", "up30", "down30", "pct_90", "steady", "turnaround")
MARKET_EPS_KEYS = ("yield_change_90_pp", "yield_change_30_pp")


def observation_key(cid: str, snapshot_sha256: str, version: str, policy: str) -> str:
    return "OB-" + digest([cid, snapshot_sha256, version, policy])[:16].upper()


RESEARCH_NOTES = {
    "no_relevant_document": "최근 120일 공식 발표에서 관련 원문을 확인하지 못했습니다(원문에서 확인 못 함).",
    "unavailable": "발행사 식별 또는 공시 목록을 확보하지 못했습니다(원문 미확보).",
    "failed": "원문 접근에 실패했습니다. 24시간 뒤 다시 시도합니다(원문 접근 실패).",
    "identity_conflict": "등록된 식별자와 SEC 식별자가 달라 조사를 보류했습니다.",
    "deferred_budget": "오늘 조사 한도를 다 써서 다음 실행에서 이어갑니다.",
    "queued": "원문 조사 대기 중입니다.",
}
LINK_LABELS = {
    "unconfirmed": "EPS 예상 상향과 이 발표의 연결: 확인되지 않음(인과 미확인)",
    "temporal_context": "EPS 예상 상향과 같은 시기의 회사 발표(인과 미확인)",
    "explicit_link": "원문이 추정치 변화와의 연결을 직접 언급함",
}
KIND_LABELS = {"fact": "실적", "guidance": "회사 전망", "interpretation": "해석"}


def context_view(record: dict | None) -> dict | None:
    """The part of a draft that is a claim on the card (generation time is not part of it)."""
    if not record:
        return None
    return {k: record.get(k) for k in ("context_id", "input_sha", "context_status", "claims", "limitations",
                                       "next_check", "link", "link_note", "source_coverage", "documents")}


def research_state(entry: dict | None, context: dict | None, human: dict | None) -> str:
    """not_started / queued / source_linked / draft_ready / review_needed; never a recommendation."""
    if context and context.get("context_status") == "draft_ready":
        imported = (human or {}).get("imported_from") == context.get("context_id")
        return "review_needed" if imported and not (human or {}).get("approval") else "draft_ready"
    if not entry:
        return "not_started"
    return "source_linked" if entry.get("status") == "success" else "queued"


def build(snapshot: dict, snapshot_ref: dict, registry: dict, evidence: dict, translations: dict,
          ideas: list[dict], policy_version: str, contexts: dict | None = None,
          research: dict | None = None) -> list[dict]:
    """Candidates in display order from one screener snapshot (pure: no I/O)."""
    derived = snapshot.get("derived", {})
    rows = {r["ticker"]: r for r in derived.get("rows", []) if r.get("candidate")}
    partial = snapshot.get("run", {}).get("status") != "success"
    result = []
    for position, (ticker, lists) in enumerate(display_order(derived), 1):
        row = rows.get(ticker)
        if row is None:
            continue
        identity = identify(row, registry)
        cid = candidate_id(identity["entity_id"]) if identity["entity_id"] else None
        observed = row.get("eps_retrieved_at") or snapshot["run"]["finished_at"]
        summary_text = (row.get("summary") or "").strip()
        translated = translations.get(translation_key(summary_text)) if summary_text else None
        description = ({"text": translated["text_ko"], "kind": "fact", "source_ids": ["yahoo-profile"],
                        "status": "translated", "model": translated.get("model")} if translated else
                       {"text": None, "kind": "fact", "source_ids": ["yahoo-profile"] if summary_text else [],
                        "status": "pending" if summary_text else "no_profile_text"})
        description["source_text"] = summary_text or None  # the English original, reviewable next to it
        price = price_block(row)
        missing = []
        if not identity["verified"]:
            missing.append({"field": "identity", "reason": "exchange_unknown"})
        if price["price_status"] != "success":
            missing.append({"field": "price_comparison", "reason": price["price_note"] or "unavailable"})
        if not row.get("industry"):
            missing.append({"field": "industry", "reason": "profile_missing"})
        human = evidence.get(cid) if cid else None
        problems = evidence_problems(human)
        flagged = (human or {}).get("review_status") == "needs_evidence"
        explanations = {"company_description_ko": description}
        for field in EXPLANATIONS:
            statements = (human or {}).get("explanations", {}).get(field) or []
            explanations[field] = ({"statements": statements} if statements else
                                   {"statements": [], "reason": "원문 근거 미연결 (EPS 스크린만 통과)"})
        context = context_view((contexts or {}).get(cid)) if cid else None
        doc_sources = [{"id": d["document_id"], "provider": "SEC EDGAR", "url": d["url"],
                        "title": f"SEC {d['form']} {d['document_type']}"
                                 + (f" — {d['title']}" if d.get("title") and d["title"] != d["document_type"] else ""),
                        "published_at": None, "filed_at": d["filed_at"], "observed_at": d["observed_at"],
                        "fields": f"{d['form']} {d['document_type']}"} for d in (context or {}).get("documents") or []]
        content = {
            "candidate_id": cid, "identity": identity, "thesis_key": THESIS_KEY,
            "context": context,
            "name": row.get("name"), "industry": row.get("industry"), "sector": row.get("sector"),
            "eps": {k: row.get(k) for k in VERSION_EPS_KEYS},
            "eps_provider": "Yahoo Finance earningsTrend (+1y)",
            "lists": sorted({m["list"] for m in lists}),
            "missing": missing,
            # Data completeness (missing) and a human 'needs evidence' mark are shown apart.
            "evidence_review": ({"status": "needs_evidence", "reason": (human or {}).get("review_reason") or "사유 미기재"}
                                if flagged else None),
            "base_classification": "needs_evidence" if missing or flagged else "found",
            "explanations": explanations,
            "sources": base_sources(ticker, observed, bool(summary_text)) + list((human or {}).get("sources", []))
                       + doc_sources,
            "generator_version": GENERATOR_VERSION,
        }
        version = content_version(content)
        research_entry = (research or {}).get(cid) if cid else None
        approval = (human or {}).get("approval")
        approved = (bool(approval) and approval.get("candidate_version") == version and not problems
                    and not missing and not flagged
                    and approval.get("evidence_sha256", evidence_hash(human)) == evidence_hash(human))
        classification = "recommended" if approved else content["base_classification"]
        review_note = None
        if approval and not approved:
            review_note = ("승인 후 내용이 바뀜: 재검토 필요" if approval.get("candidate_version") != version
                           else "승인 근거 불충분: " + ", ".join(problems))
        result.append({
            **content, "eps": {**content["eps"], **{k: row.get(k) for k in MARKET_EPS_KEYS}},
            "candidate_version": version, "classification": classification,
            "observation_id": (observation_key(cid, snapshot_ref.get("sha256", ""), version, policy_version)
                               if cid else None),
            "approval": approval if approved else None, "review_note": review_note,
            "evidence_problems": problems,
            "display_rank": position, "memberships": lists,
            "price": price, "market_cap": row.get("market_cap"),
            "observed_at": observed, "run_quality": "partial" if partial else "complete",
            "scope_note": "확보 범위 내 순위 (일부 조회 누락)" if partial else "전체 조회 범위 순위",
            "tracking": ledger_tracking(identity["entity_id"], ideas, THESIS_KEY),
            "research_status": research_state(research_entry, context, human),
            "research_note": RESEARCH_NOTES.get((research_entry or {}).get("status")) if not context else None,
            "context_id": (context or {}).get("context_id"),
            "source_snapshot": snapshot_ref, "policy_version": policy_version,
        })
    return result


def content_version(content: dict) -> str:
    """Hash of what the card claims. When a source was observed is not part of the claim."""
    claim = {**content, "sources": [{k: v for k, v in s.items() if k != "observed_at"} for s in content["sources"]]}
    return "CV-" + digest(claim)[:16].upper()


def version_record(candidate: dict) -> dict:
    """The immutable claim of a version (no observation time, price window or rank)."""
    keys = ("candidate_id", "candidate_version", "identity", "thesis_key", "name", "industry", "sector",
            "eps_provider", "lists", "missing", "base_classification", "explanations", "sources",
            "generator_version", "context", "evidence_review")
    record = {k: candidate.get(k) for k in keys}
    record["eps"] = {k: candidate["eps"].get(k) for k in VERSION_EPS_KEYS}
    return c.validate_record("candidate_version", record)


def observation_record(candidate: dict) -> dict:
    """What was seen at one observation: enough to show the card as it was then."""
    record = {k: candidate.get(k) for k in (
        "observation_id", "candidate_id", "candidate_version", "thesis_key", "identity", "observed_at",
        "source_snapshot", "eps", "price", "display_rank", "memberships", "lists", "missing", "run_quality",
        "scope_note", "classification", "policy_version", "generator_version", "market_cap",
        "context_id", "research_status", "research_note")}
    record["entity_id"] = candidate["identity"]["entity_id"]
    record["approval_version"] = (candidate.get("approval") or {}).get("candidate_version")
    return c.validate_record("candidate_observation", record)


def store_versions(cands: list[dict]) -> int:
    """Write each new version once; an existing file must hold the same claim."""
    written = 0
    for cand in cands:
        if not cand["candidate_id"]:
            continue
        path = history_dir() / f"{cand['candidate_version']}.json"
        record = version_record(cand)
        if path.exists():
            stored = c.read_json(path, {})
            if stored.get("candidate_id") != cand["candidate_id"]:
                raise ValueError(f"version collision {cand['candidate_version']}")
            continue
        c.atomic_json(path, record)
        written += 1
    return written


def store_observations(cands: list[dict]) -> int:
    """One immutable file per observation; re-rendering the same input writes nothing."""
    written = 0
    for cand in cands:
        if not cand.get("observation_id"):
            continue
        record = observation_record(cand)
        path = observations_dir() / f"{record['observation_id']}.json"
        if path.exists():
            if c.read_json(path, {}).get("candidate_id") != record["candidate_id"]:
                raise ValueError(f"observation collision {record['observation_id']}")
            continue
        c.atomic_json(path, record)
        written += 1
    return written


def migrate_legacy_versions(now: datetime) -> int:
    """cards-v1 version files carried their first observation; move only that one, marked as migrated.

    No later observation is invented. The version file itself is left unchanged.
    """
    referenced = {c.read_json(p, {}).get("candidate_version") for p in observations_dir().glob("OB-*.json")}
    moved = 0
    for path in sorted(history_dir().glob("CV-*.json")):
        record = c.read_json(path, {})
        if record.get("candidate_version") in referenced or not record.get("observed_at"):
            continue
        snapshot = record.get("source_snapshot") or {}
        obs = {
            "observation_id": observation_key(record["candidate_id"], snapshot.get("sha256", ""),
                                              record["candidate_version"], record.get("policy_version", "")),
            "candidate_id": record["candidate_id"], "candidate_version": record["candidate_version"],
            "entity_id": record["identity"]["entity_id"], "thesis_key": record["thesis_key"],
            "identity": record["identity"], "observed_at": record["observed_at"], "source_snapshot": snapshot,
            "eps": record.get("eps", {}), "lists": record.get("lists", []), "missing": record.get("missing", []),
            "price": {"price_status": "unknown", "price_note": "legacy_version_only"},
            "display_rank": None, "memberships": [], "run_quality": "unknown", "scope_note": None,
            "classification": record.get("base_classification"), "policy_version": record.get("policy_version"),
            "generator_version": record.get("generator_version"), "approval_version": None,
            "migrated": {"from": f"candidate_history/{path.name}", "at": now.isoformat(timespec="seconds"),
                         "note": "cards-v1 first observation only; later observations were not recorded"},
        }
        c.atomic_json(observations_dir() / f"{obs['observation_id']}.json", c.validate_record("candidate_observation", obs))
        moved += 1
    return moved


def observation_order(record: dict) -> tuple:
    # At the same instant a migrated cards-v1 record precedes the record the current generator made.
    return (record["observed_at"], 0 if record.get("migrated") else 1, record["observation_id"])


def known_candidates() -> dict:
    """candidate_id -> first/last seen, latest observation and version timeline, from observations."""
    by_id: dict[str, list[dict]] = {}
    for path in observations_dir().glob("OB-*.json"):
        record = c.read_json(path, {})
        if record.get("candidate_id"):
            by_id.setdefault(record["candidate_id"], []).append(record)
    known = {}
    for cid, records in by_id.items():
        records.sort(key=observation_order)
        keys = {f"{r['entity_id']}|{r['thesis_key']}" for r in records}
        if len(keys) != 1:
            raise ValueError(f"candidate id collision {cid}: {sorted(keys)}")
        timeline = []
        for r in records:  # version segments in time order: A -> B -> A stays three segments
            if not timeline or timeline[-1]["version"] != r["candidate_version"]:
                timeline.append({"version": r["candidate_version"], "from": r["observed_at"], "to": r["observed_at"]})
            timeline[-1]["to"] = r["observed_at"]
        known[cid] = {"key": keys.pop(), "ticker": records[-1]["identity"]["ticker"],
                      "first_seen_at": records[0]["observed_at"], "last_seen_at": records[-1]["observed_at"],
                      "latest_observation": records[-1]["observation_id"],
                      "latest_version": records[-1]["candidate_version"], "timeline": timeline}
    return known


def assemble(version: dict, observation: dict, ideas: list[dict], as_of: str | None = None) -> dict:
    """A card as it was at one stored observation, with today's tracking state and the
    approval state as it stood at as_of (default now) from the review events."""
    card = _assemble(version, observation, ideas)
    state = review_state(version.get("candidate_id"), version.get("candidate_version"), as_of)
    card["review_state"] = state
    if state == "approved":
        card["classification"] = "recommended"
    elif card.get("classification") == "recommended":
        card["classification"] = version.get("base_classification") or "found"
    return card


def _assemble(version: dict, observation: dict, ideas: list[dict]) -> dict:
    explanations = {"company_description_ko": {"text": None, "kind": "fact", "source_ids": [], "status": "unknown"},
                    **{f: {"statements": [], "reason": "기록 없음"} for f in EXPLANATIONS},
                    **(version.get("explanations") or {})}
    return {**version, "explanations": explanations, "sources": version.get("sources") or [],
            "memberships": [], "missing": version.get("missing") or [],
            "eps": {**version.get("eps", {}), **(observation.get("eps") or {})},
            **{k: observation.get(k) for k in ("observation_id", "observed_at", "price", "display_rank",
                                               "memberships", "run_quality", "scope_note", "classification",
                                               "source_snapshot", "policy_version", "market_cap",
                                               "context_id", "research_status", "research_note")},
            # The draft is the one this observation showed, never a later one.
            "context": version.get("context"),
            "approval": None, "review_note": None, "evidence_problems": [],
            "tracking": ledger_tracking(version["identity"]["entity_id"], ideas, version.get("thesis_key", THESIS_KEY))}


def load_observation(observation_id: str) -> tuple[dict, dict] | None:
    obs = c.read_json(observations_dir() / f"{observation_id}.json", None)
    if obs is None:
        return None
    return c.read_json(history_dir() / f"{obs['candidate_version']}.json", {}), obs


def registered_observation(idea: dict) -> str | None:
    match = re.search(r"관측 (OB-[0-9A-F]{16})", idea.get("당시 판단", ""))
    return match.group(1) if match else None


def verified_target(entity_id: str, ticker: str, registration: str | None = None) -> dict:
    """Entity, ticker and currency verified by candidate observations, for tickers not in the registry.

    The observation recorded at registration comes first; later observations are compared in
    observation time (never by hash file name). A later currency or exchange change is a conflict:
    collection is held and the conflict reported instead of silently switching.
    """
    records = sorted((r for r in (c.read_json(p, {}) for p in observations_dir().glob("OB-*.json"))
                      if r.get("entity_id") == entity_id and (r.get("identity") or {}).get("ticker") == ticker
                      and (r.get("identity") or {}).get("verified") and (r.get("eps") or {}).get("eps_currency")),
                     key=observation_order)
    if not records:
        return {}
    registered = next((r for r in records if r["observation_id"] == registration), None)
    base = registered or records[-1]
    # Compare from the registration on; without one, every verified observation must agree.
    compared = [r for r in records if registered is None or observation_order(r) >= observation_order(registered)]
    seen = {((r["eps"] or {}).get("eps_currency"), r["identity"].get("exchange")) for r in compared}
    if len(seen) > 1:
        return {"entity_id": entity_id, "conflict": sorted(str(x) for x in seen)}
    return {"entity_id": entity_id, "currency": base["eps"]["eps_currency"], "exchange": base["identity"].get("exchange"),
            "identity_source": base["identity"].get("source"), "observation_id": base["observation_id"]}


# ------------------------------------------------------------------ translation

def translation_key(text: str) -> str:
    return hashlib.sha256(f"{TRANSLATION_PROMPT_VERSION}\n{text}".encode("utf-8")).hexdigest()


def translation_prompt(items: dict[str, str]) -> str:
    return (
        "다음은 미국 상장사의 영문 사업 설명이다. 각 회사가 무엇으로 돈을 버는지 한국어 한 문장(80자 이내)으로 써라.\n"
        "규칙: 원문에 있는 내용만 쓴다. 숫자, 고객명, 시장점유율, 전망, 평가 표현을 추가하지 않는다. "
        "어려운 전문용어는 쉬운 말로 풀어쓴다.\n"
        "출력: JSON 객체 하나. 키는 입력의 티커 그대로, 값은 한국어 문장.\n\n"
        + json.dumps(items, ensure_ascii=False, indent=1))


def translation_problem(text: Any, source: str) -> str | None:
    """Why a translation is refused. Passing is not proof of meaning; the original stays reviewable."""
    if not isinstance(text, str) or not text.strip():
        return "missing"
    if not 8 <= len(text.strip()) <= 160:
        return "length"
    if not re.search(r"[가-힣]", text):
        return "not_korean"
    # Numbers that are not in the source text would be invented facts.
    if not set(re.findall(r"\d+", text)) <= set(re.findall(r"\d+", source)):
        return "numbers_not_in_source"
    return None


def valid_translation(text: Any, source: str) -> bool:
    return translation_problem(text, source) is None


def translate(rows: list[dict], cache: dict, api_key: str, cfg: dict, call=None, rejects: dict | None = None) -> dict:
    """Fill the cache for untranslated summaries in batches, within the shared daily budget."""
    import extract
    if call is None:
        call = lambda prompt: extract.call_gemini_prompt(prompt, api_key, "cards")  # noqa: E731
    todo = {}
    for row in rows:
        text = (row.get("summary") or "").strip()
        if text and translation_key(text) not in cache:
            todo[row["ticker"]] = text
    tickers = list(todo)
    report = {"requested": len(tickers), "translated": 0, "rejected": 0, "failed_calls": 0, "calls": 0}
    for start in range(0, len(tickers), cfg["translation_batch"]):
        if report["calls"] >= cfg["translation_max_calls"] or not api_key:
            break
        if c.model_calls_remaining("cards") <= 0:
            report["budget_exhausted"] = True
            break
        batch = {t: todo[t] for t in tickers[start:start + cfg["translation_batch"]]}
        report["calls"] += 1
        try:
            answer = call(translation_prompt(batch))
        except c.ModelBudgetExhausted:
            report["budget_exhausted"] = True  # a retry ran out of budget; the rest waits for tomorrow
            break
        except (OSError, ValueError, KeyError, IndexError, TimeoutError) as error:
            report["failed_calls"] += 1
            report["last_error"] = type(error).__name__
            continue
        for ticker, source in batch.items():
            text = answer.get(ticker) if isinstance(answer, dict) else None
            problem = translation_problem(text, source)
            if problem is None:
                cache[translation_key(source)] = {"text_ko": text.strip(), "model": extract.GEMINI_MODEL,
                                                  "prompt_version": TRANSLATION_PROMPT_VERSION,
                                                  "created_at": c.utc_now()}
                report["translated"] += 1
            else:
                # Kept with the source hash; the next daily run tries again within the budget.
                key = translation_key(source)
                previous = (rejects if rejects is not None else {}).get(key, {})
                if rejects is not None:
                    rejects[key] = {"ticker": ticker, "reason": problem, "source_sha256": key,
                                    "at": c.utc_now(), "attempts": previous.get("attempts", 0) + 1}
                report["rejected"] += 1
    return report


# ------------------------------------------------------------------ rendering

def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def money(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "-"
    return f"-${-value:,.2f}" if value < 0 else f"${value:,.2f}"


def eps_change(eps: dict) -> str:
    if eps.get("pct_90") is not None:
        return f"{eps['pct_90']:+.0f}%"
    if eps.get("turnaround") or (eps.get("eps_90d") or 0) < 0:
        return "적자→흑자"
    return "기저가 작아 % 생략"


def selection_lines(cand: dict) -> list[str]:
    eps = cand["eps"]
    lines = []
    for m in cand["memberships"]:
        if m["list"] == "A":
            lines.append(f"A {m['rank']}위: 이익수익률 변화 {eps['yield_change_90_pp']:+.2f}%p "
                         f"(내년 EPS 예상 증가분 ÷ 현재 주가, 기준 1.0%p 이상)")
        else:
            lines.append(f"B {m['rank']}위: 내년 EPS 예상 90일 변화 {eps_change(eps)} "
                         f"(기준 +25% 이상, 90일 전 EPS $0.25 이상)")
    lines.append(f"최근 30일 추정 상향 {eps['up30']} / 하향 {eps['down30']}, 분석가 {eps['analysts']}명"
                 + (", 30일·90일 모두 상향" if eps.get("steady") else ""))
    return lines


def price_line(cand: dict) -> str:
    p = cand["price"]
    if p["price_status"] != "success":
        return f"주가 비교 미확보: {PRICE_NOTES.get(p['price_note'], p['price_note'] or '조회 실패')}"
    line = (f"주가 {p['price_start_date']} → {p['price_end_date']}: {p['price_pct_90']:+.1f}% "
            f"(분할 조정 종가, 배당 미조정)")
    if p.get("pe_change_pct") is not None:
        line += f" · 같은 기간 PER 참고 변화 {p['pe_change_pct']:+.0f}% (저평가 입증 아님)"
    elif p.get("price_note") == "split_in_window":
        line += " · 기간 중 분할로 PER 비교 생략"
    return line


def headline(cand: dict) -> str:
    if cand["classification"] == "recommended":
        return "추적 추천"
    if cand.get("missing"):
        return "발굴 후보 · 자료 부족"
    if cand.get("evidence_review"):
        return "발굴 후보 · 근거 보강 필요"
    return "발굴 후보"


def tracking_label(cand: dict) -> str:
    t = cand["tracking"]
    return {"tracked": f"이 가설 추적 중 ({', '.join(t['idea_ids'])})",
            "entity_tracked": f"기업은 추적 중·이 가설 미등록 ({', '.join(t['idea_ids'])})",
            "closed": "추적 종료됨", "untracked": "미추적"}[t["status"]]


def card_lines(cand: dict, stale: list[str] | None = None) -> list[tuple[str, str]]:
    """(kind, text) lines in the card order shared by Telegram, Markdown and HTML."""
    eps = cand["eps"]
    desc = cand["explanations"]["company_description_ko"]
    lines = [("title", f"{headline(cand)} · {cand['identity']['ticker']} {cand.get('name') or ''}".strip()),
             ("meta", f"{cand['candidate_id'] or 'ID 없음(거래소 미확인)'} · {cand.get('industry') or '업종 미확인'}"
                      f" · {tracking_label(cand)}")]
    if stale:
        lines.append(("warn", "최신 수집 실패 또는 오래된 결과: 마지막 유효 관측 " + cand["observed_at"][:10]))
    if cand["run_quality"] == "partial":
        lines.append(("warn", cand["scope_note"]))
    lines.append(("section", "무엇으로 돈을 버나"))
    lines.append(("text", desc["text"] if desc["text"] else f"회사 설명 확인 중 ({cand['identity']['ticker']})"))
    if desc.get("source_text"):
        lines.append(("source_text", desc["source_text"]))
    if cand.get("evidence_review"):
        lines.append(("warn", f"근거 보강 필요(사람 지정): {cand['evidence_review']['reason']}"))
    lines.append(("section", "후보가 된 이유"))
    lines += [("item", x) for x in selection_lines(cand)]
    lines.append(("section", f"숫자 (관측 {cand['observed_at'][:16].replace('T', ' ')} UTC)"))
    lines.append(("item", f"내년 EPS 예상 ({eps['eps_target_period']} 회계연도 말, {eps['eps_currency']}, "
                          f"{cand['eps_provider']}, 회계기준 미표시): 90일 전 {money(eps['eps_90d'])} → "
                          f"30일 전 {money(eps['eps_30d'])} → 현재 {money(eps['eps_now'])} ({eps_change(eps)})"))
    lines.append(("item", price_line(cand)))
    context = cand.get("context") or {}
    docs = {d["document_id"]: d for d in context.get("documents") or []}

    def claim_line(item, label):
        doc = docs.get(item.get("document_id"), {})
        return ("claim", json.dumps({"label": label, "text": item["text_ko"], "quote": item.get("quote"),
                                     "title": (f"SEC {doc['form']} {doc['document_type']}" if doc.get("form")
                                               else item.get("document_id")), "url": doc.get("url"),
                                     "filed": doc.get("filed_at"), "period": item.get("period")}, ensure_ascii=False))

    lines.append(("section", "공식 발표에서 확인한 변화 (자동 정리·미검토)"))
    stated = [x for x in context.get("claims") or [] if x.get("kind") in ("fact", "guidance")][:3]
    if stated:
        lines += [claim_line(x, KIND_LABELS[x["kind"]]) for x in stated]
    elif context.get("context_status") == "no_supported_claims":
        lines.append(("text", "원문은 확보했지만 근거가 붙은 문장을 만들지 못했습니다. 원문을 직접 확인해야 합니다."))
    else:
        lines.append(("text", cand.get("research_note") or "아직 공식 발표 원문을 연결하지 않았습니다."))
    interpreted = [x for x in context.get("claims") or [] if x.get("kind") == "interpretation"][:2]
    if interpreted:
        lines.append(("section", "이익으로 이어질 수 있는 경로 (해석)"))
        lines += [claim_line(x, "해석") for x in interpreted]
    lines.append(("section", "사람이 확인한 사업 근거"))
    human = [(f, cand["explanations"][f]["statements"]) for f in ("earnings_path", "persistence_evidence")]
    if any(s for _, s in human):
        for field, statements in human:
            for s in statements:
                lines.append(("item", f"{EXPLANATION_LABELS[field]} [{s['kind']}] {s['text']} ({', '.join(s['source_ids'])})"))
    else:
        lines.append(("text", "아직 없음. EPS 예상 상향이 왜 생겼는지 원문으로 확인하지 않았습니다."))
    lines.append(("section", "미확인 · 반증"))
    for item in cand["missing"]:
        lines.append(("item", f"자료 부족: {item['field']} ({PRICE_NOTES.get(item['reason'], item['reason'])})"))
    gap = cand["explanations"]["market_expectation_gap"]["statements"]
    falsification = cand["explanations"]["falsification"]["statements"]
    for s in gap + falsification:
        lines.append(("item", f"[{s['kind']}] {s['text']} ({', '.join(s['source_ids'])})"))
    if not falsification:
        lines.append(("item", "스크린 조건 기준 반증: 다음 관측에서 내년 EPS 예상이 30일 전보다 낮아지거나 "
                              "30일 하향 수가 상향 수 이상이면 후보 조건이 깨집니다."))
    if not gap:
        lines.append(("item", "시장이 이 상향을 반영하지 않았는지는 확인되지 않았습니다. PER 변화는 참고 지표입니다."))
    for item in (context.get("limitations") or [])[:2]:
        lines.append(claim_line({**item, "kind": "fact"}, "반대 근거·한계"))
    if context.get("link"):
        lines.append(("item", LINK_LABELS.get(context["link"], context["link"])))
    if cand.get("review_note"):
        lines.append(("warn", cand["review_note"]))
    lines.append(("section", "다음 확인"))
    checks = cand["explanations"]["next_check"]["statements"]
    if checks:
        lines += [("item", s["text"]) for s in checks]
    elif [x for x in context.get("next_check") or [] if isinstance(x, str) and not x.startswith("{")]:
        first = next(x for x in context["next_check"] if isinstance(x, str) and not x.startswith("{"))
        lines.append(("item", f"{first} (자동 제안)"))
    else:
        lines.append(("item", "최근 실적 발표·가이던스 원문에서 이익 증가 원인과 지속 기간 확인"))
    lines.append(("section", "출처"))
    for s in cand["sources"]:
        seen = f"제출 {s['filed_at']}" if s.get("filed_at") else f"관측 {(s.get('observed_at') or '')[:10]}"
        lines.append(("link", f"{s['title']}|{s['url']}|{seen}"))
    status = cand["tracking"]["status"]
    if status in ("tracked", "entity_tracked"):
        lines.append(("command", f"/history {cand['identity']['ticker']}"))
    if status != "tracked" and cand["candidate_id"]:
        lines.append(("command", f"/track {cand['candidate_id']}"))
    return lines


def telegram_card(cand: dict, stale: list[str] | None = None) -> str:
    out = []
    for kind, text in card_lines(cand, stale):
        if kind == "title":
            out.append(f"<b>{esc(text)}</b>")
        elif kind == "section":
            out.append(f"\n<b>{esc(text)}</b>")
        elif kind == "warn":
            out.append(f"⚠️ {esc(text)}")
        elif kind == "item":
            out.append(f"· {esc(text)}")
        elif kind == "link":
            title, url, observed = text.split("|")
            if safe_url(url):
                out.append(f'· <a href="{esc(url)}">{esc(title)}</a> ({esc(observed)})')
        elif kind == "claim":
            item = json.loads(text)
            out.append(f"· [{esc(item['label'])}] {esc(item['text'])} ({esc(item['title'])}, 제출 {esc(item['filed'])})")
        elif kind == "source_text":
            continue
        elif kind == "command":
            label = "관측 이력" if text.startswith("/history") else "추적 등록"
            out.append(f"\n{label}: <code>{esc(text)}</code>")
        else:
            out.append(esc(text))
    out.append("\n추적 추천은 매수 추천이 아닙니다. 목표가·상승 확률을 제시하지 않습니다.")
    return "\n".join(out)


def markdown_card(cand: dict, stale: list[str] | None = None) -> str:
    out = []
    for kind, text in card_lines(cand, stale):
        text_md = text.replace("|", "\\|") if kind != "link" else text
        if kind == "title":
            out.append(f"### {text_md}")
        elif kind == "section":
            out.append(f"\n**{text_md}**\n")
        elif kind == "warn":
            out.append(f"> ⚠️ {text_md}")
        elif kind == "item":
            out.append(f"- {text_md}")
        elif kind == "link":
            title, url, observed = text.split("|")
            if safe_url(url):
                out.append(f"- [{title}]({url}) ({observed})")
        elif kind == "claim":
            item = json.loads(text)
            source = f"[{item['title']}]({item['url']})" if safe_url(item.get("url")) else item["title"]
            out.append(f"- [{item['label']}] {item['text']} — “{item['quote']}” ({source}, 제출 {item['filed']}, "
                       f"기간 {item.get('period') or '미표시'})")
        elif kind == "source_text":
            out.append(f"<small>원문(영문): {text_md}</small>")
        elif kind == "command":
            out.append(f"\n텔레그램: `{text}`")
        else:
            out.append(text_md)
    return "\n".join(out)


# ------------------------------------------------------------------ index & views

def load_index() -> dict:
    return c.read_json(index_path(), {})


KST = timezone(timedelta(hours=9))
DEPARTURES = {
    "rank_outside": "스크린 조건은 통과했지만 A·B 상위 목록 밖",
    "screen_condition_not_met": "최신 관측에서 스크린 조건 미충족",
    "not_observed": "최신 관측에서 EPS 자료 없음 또는 조회 대상 제외",
}


def kst_date(stamp: str) -> str:
    return datetime.fromisoformat(stamp).astimezone(KST).date().isoformat()


def find(cid: str) -> tuple[dict | None, str]:
    """(candidate, state) where state is current / stale / not_current / unknown.

    A candidate that left the list is shown as it was at its latest stored observation.
    """
    index = load_index()
    for cand in index.get("candidates", []):
        if cand["candidate_id"] and cand["candidate_id"] == cid:
            return cand, "stale" if index.get("stale") else "current"
    known = index.get("known", {}).get(cid)
    loaded = load_observation(known["latest_observation"]) if known else None
    if loaded:
        version, obs = loaded
        cand = assemble(version, obs, c.read_live_rows("investment_review_log"))
        cand["departure"] = (index.get("departed") or {}).get(cid)
        return cand, "not_current"
    return None, "unknown"


def screen_summary(index: dict) -> dict:
    return {k: index.get(k) for k in ("generated_at", "observed_at", "run_status", "stale", "coverage",
                                      "screen_candidates")}


def telegram_screen(limit: int = 5) -> list[str]:
    index = load_index()
    if not index.get("candidates"):
        return ["후보 카드가 아직 없습니다. 다음 일간 실행(09:17 KST) 뒤 다시 조회해 주세요."]
    cov = index["coverage"]
    lines = [f"<b>EPS 상향 발굴 후보 · 관측 {esc(index['observed_at'][:16].replace('T', ' '))} UTC</b>",
             f"조회 {cov['earnings_success']:,}/{cov['earnings_requested']:,}종목 · 스크린 통과 {index['screen_candidates']}개"
             f" · 카드 {len(index['candidates'])}개 ({'전체 범위' if index['run_status'] == 'success' else '일부 누락, 확보 범위 내 순위'})"]
    if index.get("stale"):
        lines.append(f"⚠️ 최신 수집 실패 또는 오래된 결과 ({esc(', '.join(index['stale']))}). 마지막 유효 관측입니다.")
    lines.append("")
    listed = [x for x in index["candidates"] if x["candidate_id"]]
    if not listed:
        lines.append(f"카드 {len(index['candidates'])}개 모두 거래소 확인 전이라 ID가 없습니다. 다음 스크린 이후 조회할 수 있습니다.")
    for cand in listed[:limit]:
        eps = cand["eps"]
        desc = cand["explanations"]["company_description_ko"]["text"] or "회사 설명 확인 중"
        lines.append(f"{cand['display_rank']}. <b>{esc(cand['identity']['ticker'])}</b> {esc(headline(cand))} · "
                     f"{esc(cand.get('industry') or '업종 미확인')}\n   {esc(desc)}\n"
                     f"   내년 EPS 예상 {esc(money(eps['eps_90d']))} → {esc(money(eps['eps_now']))} ({esc(eps_change(eps))})"
                     f" · {esc(tracking_label(cand))}\n   <code>/candidate {esc(cand['candidate_id'])}</code>")
    lines.append("\n순서는 A(이익수익률 변화)·B(90일 증가율) 목록을 번갈아 놓은 것이며 투자 점수가 아닙니다."
                 " 명령은 하루 4번(03:23·09:17·15:23·21:23 KST 무렵) 처리되며 실시간 응답이 아닙니다.")
    return ["\n".join(lines)]


def telegram_candidate(argument: str) -> list[str]:
    cid = normalize_id(argument)
    if not cid:
        return ["후보 ID 형식이 아닙니다. 예: /candidate CAN-0123456789ABCDEF (/screen으로 목록 확인)"]
    cand, state = find(cid)
    if state == "unknown":
        return [f"없는 후보 ID입니다: {esc(cid)}. /screen으로 최신 목록을 확인해 주세요."]
    if state == "not_current":
        reason = DEPARTURES.get((cand.get("departure") or {}).get("reason"), "이유 미확인")
        note = (f"⚠️ 최신 후보 목록에 없습니다({esc(reason)}). 아래는 마지막 관측 "
                f"{esc(kst_date(cand['observed_at']))}(KST) 당시 카드입니다.\n\n")
        return [note + telegram_card(cand)]
    stale = load_index().get("stale") if state == "stale" else None
    return [telegram_card(cand, stale)]


def render_markdown(index: dict) -> str:
    cov = index.get("coverage") or {}
    lines = [f"# EPS 상향 발굴 후보 카드 ({c.today()})", "",
             "매일 전 종목 스크린에서 내년 EPS 예상이 꾸준히 오른 회사를 골라 카드로 정리합니다. "
             "'발굴 후보'는 숫자 조건만 통과한 상태이고, '추적 추천'은 사람이 원문 근거를 확인·승인한 경우에만 붙습니다. "
             "매수 추천·목표가·상승 확률이 아닙니다.", ""]
    if not index.get("observed_at"):
        return "\n".join(lines + ["유효한 스크린 결과가 없습니다.", ""])
    lines.append(f"관측 {index['observed_at']} · 조회 {cov['earnings_success']:,}/{cov['earnings_requested']:,}종목 · "
                 f"스크린 통과 {index['screen_candidates']}개 · 카드 {len(index['candidates'])}개 · "
                 f"원자료 `{index['source_snapshot']['path']}`")
    if index.get("stale"):
        lines.append(f"\n> ⚠️ 최신 수집 실패 또는 오래된 결과({', '.join(index['stale'])}). 마지막 유효 관측입니다. 새 알림은 보내지 않습니다.")
    if index["run_status"] != "success":
        lines.append("\n> ⚠️ 일부 조회가 누락된 실행입니다. 순위는 확보 범위 내 순위입니다.")
    lines += ["", "|순서|종목|분류|업종|내년 EPS 예상 90일|주가 90일|추적|후보 ID|", "|---|---|---|---|---|---|---|---|"]
    for cand in index["candidates"]:
        p = cand["price"]
        price = f"{p['price_pct_90']:+.0f}%" if p["price_status"] == "success" else "미확보"
        lines.append(f"|{cand['display_rank']}|{cand['identity']['ticker']}|{headline(cand)}|"
                     f"{(cand.get('industry') or '미확인')}|{eps_change(cand['eps'])}|{price}|"
                     f"{tracking_label(cand)}|`{cand['candidate_id'] or 'ID 없음(거래소 미확인)'}`|")
    lines.append("")
    for cand in index["candidates"]:
        lines += [markdown_card(cand, index.get("stale")), ""]
    departed = departed_rows(index)
    if departed:
        lines += ["## 최근 목록에서 빠진 후보", "", "|종목|후보 ID|마지막 관측(KST)|이유(최신 관측 기준)|",
                  "|---|---|---|---|"]
        lines += [f"|{d['ticker']}|`{d['candidate_id']}`|{d['last_seen']}|{d['reason']}|" for d in departed]
        lines.append("")
    lines.append("화면(필터·상세 카드): `reports/generated/candidates.html`. 새 후보의 과거 그래프는 만들지 않으며, "
                 "추적을 시작한 뒤부터 관측이 쌓입니다.")
    return "\n".join(lines) + "\n"


def departed_rows(index: dict, limit: int = 30) -> list[dict]:
    known = index.get("known", {})
    rows = [{"candidate_id": cid, "ticker": known[cid]["ticker"], "last_seen_at": known[cid]["last_seen_at"],
             "last_seen": kst_date(known[cid]["last_seen_at"]),
             "reason": DEPARTURES.get(item.get("reason"), "이유 미확인")}
            for cid, item in (index.get("departed") or {}).items() if cid in known]
    rows.sort(key=lambda d: d["last_seen_at"], reverse=True)
    return rows[:limit]


def render_html(index: dict) -> str:
    payload = {"index": {k: v for k, v in index.items() if k not in ("candidates", "known", "departed")},
               "departed": departed_rows(index),
               "cards": [{"candidate": cand, "lines": card_lines(cand, index.get("stale")),
                          "headline": headline(cand), "tracking": tracking_label(cand),
                          "change": eps_change(cand["eps"])} for cand in index.get("candidates", [])]}
    data = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c").replace("&", "\\u0026")
    template = (c.ROOT / "templates" / "candidates.html").read_text(encoding="utf-8")
    return template.replace("__CANDIDATES__", data).replace("__DATE__", c.today())


# ------------------------------------------------------------------ run

def policy_version() -> str:
    path = c.ROOT / "config" / "research_policy.json"
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def generate(now: datetime | None = None, translate_now: bool = True, call=None) -> dict:
    import screen_revisions
    now = now or datetime.now(timezone.utc)
    cfg = settings()
    choice = choose_snapshot(list(screen_revisions.SCREEN_DIR.glob("*.json.gz")), now, cfg["stale_hours"])
    valid_run = choice["valid"]["snapshot"]["run"].get("run_id") if choice["valid"] else None
    # A screen attempt that died without writing a snapshot is only visible in the daily record.
    for reason in screen_attempt_stale(c.read_json(c.DATA_DIR / "daily_runs.json", {}), valid_run):
        if reason not in choice["stale"]:
            choice["stale"].append(reason)
    index: dict[str, Any] = {"generated_at": now.isoformat(timespec="seconds"), "generator_version": GENERATOR_VERSION,
                             "thesis_key": THESIS_KEY, "stale": choice["stale"], "candidates": []}
    report: dict[str, Any] = {"stale": choice["stale"]}
    if choice["valid"]:
        snapshot, path = choice["valid"]["snapshot"], choice["valid"]["path"]
        ref = {"path": path.relative_to(c.ROOT).as_posix() if path.is_relative_to(c.ROOT) else path.name,
               "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "run_id": snapshot["run"]["run_id"],
               "finished_at": snapshot["run"]["finished_at"]}
        cache = c.read_json(translation_path(), {})
        derived = snapshot.get("derived", {})
        ranked = {t for t, _ in display_order(derived)}
        rows = [r for r in derived.get("rows", []) if r.get("candidate") and r["ticker"] in ranked]
        if translate_now:
            rejects = c.read_json(rejection_path(), {})
            report["translation"] = translate(rows, cache, c.load_dotenv_value("GEMINI_API_KEY"), cfg, call, rejects)
            c.atomic_json(translation_path(), cache)
            c.atomic_json(rejection_path(), rejects)
        contexts, research = context_inputs()
        cands = build(snapshot, ref, c.read_json(c.ROOT / "config" / "entities.json", {}),
                      c.read_json(evidence_path(), {}), cache,
                      c.read_live_rows("investment_review_log"), policy_version(), contexts=contexts, research=research)
        report["new_versions"] = store_versions(cands)
        report["new_observations"] = store_observations(cands)
        earnings = snapshot.get("stages", {}).get("earnings", {})
        index.update(observed_at=snapshot["run"]["finished_at"], run_status=snapshot["run"]["status"],
                     source_snapshot=ref, screen_candidates=sum(1 for r in derived.get("rows", []) if r.get("candidate")),
                     coverage={"universe": snapshot["run"].get("universe_size"),
                               "earnings_requested": earnings.get("requested", 0),
                               "earnings_success": earnings.get("success", 0)},
                     # Unidentified rows stay visible (no ID, no tracking command) instead of vanishing.
                     candidates=cands,
                     unidentified=[x["identity"]["ticker"] for x in cands if not x["candidate_id"]])
    report["migrated_legacy"] = migrate_legacy_versions(now)
    index["known"] = known_candidates()
    for cand in index["candidates"]:
        seen = index["known"].get(cand["candidate_id"] or "", {})
        cand["first_seen_at"], cand["last_seen_at"] = seen.get("first_seen_at"), seen.get("last_seen_at")
    if choice["valid"] and not choice["stale"]:
        # Why a known candidate is not on today's list, only as far as today's snapshot shows.
        current = {x["candidate_id"] for x in index["candidates"]}
        rows = {r["ticker"]: r for r in choice["valid"]["snapshot"].get("derived", {}).get("rows", [])}
        index["departed"] = {}
        for cid, item in index["known"].items():
            if cid in current:
                continue
            row = rows.get(item["ticker"])
            reason = "not_observed" if row is None else ("rank_outside" if row.get("candidate") else "screen_condition_not_met")
            index["departed"][cid] = {"reason": reason, "as_of": index["observed_at"]}
    c.atomic_json(index_path(), index)
    (c.ROOT / "docs" / "candidates.md").write_text(render_markdown(index), encoding="utf-8")
    out = c.ROOT / "reports" / "generated"
    out.mkdir(parents=True, exist_ok=True)
    (out / "candidates.html").write_text(render_html(index), encoding="utf-8")
    report.update(cards=len(index["candidates"]), unidentified=len(index.get("unidentified", [])))
    return report


def context_inputs() -> tuple[dict, dict]:
    """(drafts with their document titles, research state) as cards and approval both read them."""
    import candidate_context
    import company_filings
    research = candidate_context.load_state()["candidates"]
    contexts = {}
    for cid, entry in research.items():
        record = c.read_json(candidate_context.history_dir() / f"{entry.get('context_id')}.json", None) \
            if entry.get("context_id") else None
        if not record:
            continue
        docs = []
        for document_id in record["document_ids"]:
            doc = company_filings.load_document(document_id)
            if doc:
                docs.append({k: doc.get(k) for k in ("document_id", "title", "url", "filed_at", "observed_at",
                                                      "form", "document_type")})
        contexts[cid] = {**record, "documents": docs}
    return contexts, research


def review_events_dir() -> Path:
    return c.DATA_DIR / "candidate_review_events"


def record_review(event: str, cid: str, version: str, actor: str, **details) -> dict:
    """Append-only: approvals and revocations are separate from market observations."""
    # Microseconds: an approval and a revocation in the same second must keep their order.
    record = {"event": event, "candidate_id": cid, "candidate_version": version, "actor": actor,
              "at": datetime.now(timezone.utc).isoformat(timespec="microseconds"), **details}
    record["review_event_id"] = "RE-" + digest(record)[:16].upper()
    c.atomic_json(review_events_dir() / f"{record['review_event_id']}.json", record)
    return record


def review_state(cid: str, version: str, as_of: str | None = None) -> str | None:
    """'approved', 'revoked' or None for one version, as it stood at as_of (default: now)."""
    events = [c.read_json(p, {}) for p in review_events_dir().glob("RE-*.json")]
    events = sorted((e for e in events if e.get("candidate_id") == cid and e.get("candidate_version") == version
                     and (as_of is None or e.get("at", "") <= as_of)), key=lambda e: e["at"])
    return events[-1]["event"] if events else None


def recompute(cid: str, index: dict) -> dict | None:
    """The card rebuilt from the index's snapshot with today's evidence, ledger, translations and drafts."""
    ref = index.get("source_snapshot") or {}
    path = c.ROOT / ref.get("path", "")
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != ref.get("sha256"):
        raise ValueError("source snapshot missing or changed; regenerate cards first")
    contexts, research = context_inputs()
    cands = build(read_snapshot(path), ref, c.read_json(c.ROOT / "config" / "entities.json", {}),
                  c.read_json(evidence_path(), {}), c.read_json(translation_path(), {}),
                  c.read_live_rows("investment_review_log"), policy_version(), contexts=contexts, research=research)
    return next((x for x in cands if x["candidate_id"] == cid), None)


def approve(cid: str, approver: str) -> str:
    """Record a person's approval of the current version, after re-checking it from current inputs.

    Refused for stale cards, cards built before the evidence changed, missing data, a
    'needs evidence' mark or incomplete sources. Approving never sends an alert.
    """
    cid = normalize_id(cid) or ""
    if not str(approver or "").strip():
        raise ValueError("approver name required")
    index = load_index()
    stale = current_freshness(index)
    if stale:
        raise ValueError("cards are stale (" + ", ".join(stale) + "); regenerate after a fresh screen and review again")
    shown = next((x for x in index.get("candidates", []) if x["candidate_id"] == cid), None)
    if shown is None:
        raise ValueError("candidate not in the latest index; regenerate cards first")
    current = recompute(cid, index)
    if current is None or current["candidate_version"] != shown["candidate_version"]:
        raise ValueError("inputs changed since the cards were built; regenerate cards and review again")
    if current["missing"]:
        raise ValueError("candidate data incomplete: " + ", ".join(m["field"] for m in current["missing"]))
    evidence = c.read_json(evidence_path(), {})
    problems = evidence_problems(evidence.get(cid))
    if problems:
        raise ValueError("evidence incomplete: " + ", ".join(problems))
    evidence[cid]["approval"] = {"approved_by": approver.strip(), "approved_at": c.utc_now(),
                                 "candidate_version": current["candidate_version"],
                                 "evidence_sha256": evidence_hash(evidence[cid]),
                                 "observation_id": shown.get("observation_id")}
    c.atomic_json(evidence_path(), evidence)
    record_review("approved", cid, current["candidate_version"], approver.strip(),
                  evidence_sha256=evidence[cid]["approval"]["evidence_sha256"],
                  observation_id=shown.get("observation_id"))
    return current["candidate_version"]


def revoke(cid: str, actor: str, reason: str) -> str:
    cid = normalize_id(cid) or ""
    evidence = c.read_json(evidence_path(), {})
    approval = (evidence.get(cid) or {}).get("approval")
    if not approval:
        raise ValueError("no approval to revoke")
    evidence[cid].pop("approval")
    c.atomic_json(evidence_path(), evidence)
    record_review("revoked", cid, approval["candidate_version"], actor, reason=reason)
    return approval["candidate_version"]


def import_context(cid: str) -> str:
    """Copy the current automatic draft into candidate_evidence for a person to check.

    Never copies or creates an approval, never overwrites an existing human entry, and
    leaves fields the draft cannot support empty. The imported entry is marked
    needs_evidence until a person compares it with the source and clears the mark.
    """
    cid = normalize_id(cid) or ""
    evidence = c.read_json(evidence_path(), {})
    if cid in evidence:
        raise ValueError("candidate already has human evidence; merge by hand")
    contexts, _ = context_inputs()
    context = contexts.get(cid)
    if not context or context.get("context_status") != "draft_ready":
        raise ValueError("no automatic draft with supported claims for this candidate")
    docs = {d["document_id"]: d for d in context["documents"]}
    stated = [x for x in context["claims"] if x["kind"] in ("fact", "guidance")]

    def statement(item, kind=None):
        return {"text": item["text_ko"], "kind": kind or item.get("kind", "fact"), "source_ids": [item["document_id"]]}

    quotes = {}
    for item in context["claims"] + context["limitations"]:
        quotes.setdefault(item["document_id"], item.get("quote"))
    evidence[cid] = {
        "explanations": {"earnings_path": [statement(x) for x in stated], "persistence_evidence": [],
                         "market_expectation_gap": [],
                         "falsification": [statement(x, "fact") for x in context["limitations"]],
                         "next_check": [{"text": t, "kind": "interpretation", "source_ids": []} for t in context["next_check"]]},
        "sources": [{"id": d, "title": docs[d]["title"], "provider": "SEC EDGAR", "url": docs[d]["url"],
                     "published_at": None, "observed_at": (docs[d]["observed_at"] or "")[:10], "quote": quotes.get(d)}
                    for d in quotes if d in docs],
        "imported_from": context["context_id"], "imported_at": c.utc_now(),
        "review_status": "needs_evidence",
        "review_reason": "자동 초안을 가져옴: 원문 대조 후 빈 항목을 채우고 이 표시를 지워야 승인 가능",
    }
    c.atomic_json(evidence_path(), evidence)
    return context["context_id"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="action")
    gen = sub.add_parser("generate", help="build cards from the latest screener snapshot (default)")
    gen.add_argument("--no-translate", action="store_true")
    ap = sub.add_parser("approve", help="approve the current version after evidence is complete")
    ap.add_argument("candidate_id")
    ap.add_argument("--by", required=True)
    rv = sub.add_parser("revoke", help="withdraw an approval (recorded as a review event)")
    rv.add_argument("candidate_id")
    rv.add_argument("--by", required=True)
    rv.add_argument("--reason", required=True)
    im = sub.add_parser("import-context", help="copy the automatic draft into candidate_evidence (no approval)")
    im.add_argument("candidate_id")
    args = parser.parse_args(argv)
    if args.action == "approve":
        print(approve(args.candidate_id, args.by))
        return 0
    if args.action == "revoke":
        print(revoke(args.candidate_id, args.by, args.reason))
        return 0
    if args.action == "import-context":
        print(import_context(args.candidate_id))
        return 0
    try:
        report = generate(translate_now=not getattr(args, "no_translate", False))
    except (OSError, ValueError, KeyError) as error:
        c.record_run("cards", "failed", error_type=type(error).__name__)
        print(f"[cards] failed: {type(error).__name__}: {error}")
        return 1
    status = "stale" if report["stale"] else "success"
    c.record_run("cards", status, **{k: v for k, v in report.items() if k != "stale"}, stale=report["stale"])
    print(f"[cards] {json.dumps(report, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
