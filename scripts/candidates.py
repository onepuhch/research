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

Versions
  candidate_version is a hash of what the card claims: identity, estimate
  numbers and target period, which screen lists it met, classification inputs,
  explanations and their sources. Collection times, ranks and the daily price
  window are observations of that version, not a new version. Each version is
  stored once, immutably, in candidate_history/{version}.json with the source
  snapshot path, SHA256, observation time and generator/policy versions.

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
GENERATOR_VERSION = "cards-v1"
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
}


# ------------------------------------------------------------------ paths

def cards_dir() -> Path:
    return c.DATA_DIR / "candidates"


def index_path() -> Path:
    return cards_dir() / "index.json"


def history_dir() -> Path:
    return c.DATA_DIR / "candidate_history"


def evidence_path() -> Path:
    return c.DATA_DIR / "candidate_evidence.json"


def translation_path() -> Path:
    return c.DATA_DIR / "translation_cache.json"


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


def ledger_tracking(entity_id: str | None, ideas: list[dict]) -> dict:
    if not entity_id:
        return {"status": "untracked", "idea_ids": []}
    rows = [r for r in ideas if r.get("entity_id") == entity_id]
    active = [r for r in rows if r.get("현재 단계") != "제외" and r.get("검토 상태") != "종료"]
    if active:
        return {"status": "tracked", "idea_ids": [r["idea_id"] for r in active]}
    if rows:
        return {"status": "closed", "idea_ids": [r["idea_id"] for r in rows]}
    return {"status": "untracked", "idea_ids": []}


def evidence_problems(entry: dict | None) -> list[str]:
    """Why human evidence is not enough for a recommendation (empty = sufficient)."""
    if not entry:
        return ["evidence_missing"]
    sources = {s.get("id") for s in entry.get("sources", []) if s.get("id") and safe_url(s.get("url"))}
    problems = []
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


def build(snapshot: dict, snapshot_ref: dict, registry: dict, evidence: dict, translations: dict,
          ideas: list[dict], policy_version: str) -> list[dict]:
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
        explanations = {"company_description_ko": description}
        for field in EXPLANATIONS:
            statements = (human or {}).get("explanations", {}).get(field) or []
            explanations[field] = ({"statements": statements} if statements else
                                   {"statements": [], "reason": "원문 근거 미연결 (EPS 스크린만 통과)"})
        content = {
            "candidate_id": cid, "identity": identity, "thesis_key": THESIS_KEY,
            "name": row.get("name"), "industry": row.get("industry"), "sector": row.get("sector"),
            "eps": {k: row.get(k) for k in ("eps_now", "eps_30d", "eps_90d", "eps_target_period", "eps_currency",
                                            "eps_basis", "analysts", "up30", "down30", "pct_90",
                                            "yield_change_90_pp", "yield_change_30_pp", "steady", "turnaround")},
            "eps_provider": "Yahoo Finance earningsTrend (+1y)",
            "lists": sorted({m["list"] for m in lists}),
            "missing": missing,
            "base_classification": "needs_evidence" if missing else "found",
            "explanations": explanations,
            "sources": base_sources(ticker, observed, bool(summary_text)) + list((human or {}).get("sources", [])),
            "generator_version": GENERATOR_VERSION,
        }
        version = content_version(content)
        approval = (human or {}).get("approval")
        approved = bool(approval) and approval.get("candidate_version") == version and not problems
        classification = "recommended" if approved else content["base_classification"]
        review_note = None
        if approval and not approved:
            review_note = ("승인 후 내용이 바뀜: 재검토 필요" if approval.get("candidate_version") != version
                           else "승인 근거 불충분: " + ", ".join(problems))
        result.append({
            **content, "candidate_version": version, "classification": classification,
            "approval": approval if approved else None, "review_note": review_note,
            "evidence_problems": problems,
            "display_rank": position, "memberships": lists,
            "price": price, "market_cap": row.get("market_cap"),
            "observed_at": observed, "run_quality": "partial" if partial else "complete",
            "scope_note": "확보 범위 내 순위 (일부 조회 누락)" if partial else "전체 조회 범위 순위",
            "tracking": ledger_tracking(identity["entity_id"], ideas),
            "source_snapshot": snapshot_ref, "policy_version": policy_version,
        })
    return result


def content_version(content: dict) -> str:
    """Hash of what the card claims. When a source was observed is not part of the claim."""
    claim = {**content, "sources": [{k: v for k, v in s.items() if k != "observed_at"} for s in content["sources"]]}
    return "CV-" + digest(claim)[:16].upper()


def version_record(candidate: dict) -> dict:
    """The immutable part of a version, with the observation it was first seen in."""
    keys = ("candidate_id", "candidate_version", "identity", "thesis_key", "name", "industry", "sector",
            "eps", "eps_provider", "lists", "missing", "base_classification", "explanations", "sources",
            "generator_version", "source_snapshot", "observed_at", "policy_version")
    return {k: candidate.get(k) for k in keys}


def store_versions(cands: list[dict]) -> int:
    """Write each new version once; an existing file must hold the same content."""
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


def known_candidates() -> dict:
    """candidate_id -> first/last seen, versions and full key, rebuilt from history."""
    known: dict[str, dict] = {}
    for path in sorted(history_dir().glob("CV-*.json")):
        record = c.read_json(path, {})
        cid = record.get("candidate_id")
        if not cid:
            continue
        key = f"{record['identity']['entity_id']}|{record['thesis_key']}"
        item = known.setdefault(cid, {"key": key, "first_seen_at": record["observed_at"], "versions": []})
        if item["key"] != key:
            raise ValueError(f"candidate id collision {cid}: {item['key']} vs {key}")
        item["first_seen_at"] = min(item["first_seen_at"], record["observed_at"])
        item["versions"].append({"version": record["candidate_version"], "observed_at": record["observed_at"]})
    for item in known.values():
        item["versions"].sort(key=lambda v: v["observed_at"])
    return known


def verified_target(entity_id: str, ticker: str) -> dict:
    """Entity, ticker and currency a candidate version verified, for tickers not in the registry."""
    for path in sorted(history_dir().glob("CV-*.json"), reverse=True):
        record = c.read_json(path, {})
        identity = record.get("identity") or {}
        if identity.get("verified") and identity.get("entity_id") == entity_id and identity.get("ticker") == ticker:
            currency = (record.get("eps") or {}).get("eps_currency")
            if currency:
                return {"entity_id": entity_id, "currency": currency, "exchange": identity.get("exchange"),
                        "identity_source": identity.get("source")}
    return {}


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


def valid_translation(text: Any, source: str) -> bool:
    if not isinstance(text, str) or not 8 <= len(text.strip()) <= 160:
        return False
    if not re.search(r"[가-힣]", text):
        return False
    # Numbers that are not in the source text would be invented facts.
    return set(re.findall(r"\d+", text)) <= set(re.findall(r"\d+", source))


def translate(rows: list[dict], cache: dict, api_key: str, cfg: dict, call=None) -> dict:
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
        if c.model_calls_today() >= c.policy()["max_model_calls"]:
            report["budget_exhausted"] = True
            break
        batch = {t: todo[t] for t in tickers[start:start + cfg["translation_batch"]]}
        report["calls"] += 1
        try:
            answer = call(translation_prompt(batch))
        except (OSError, ValueError, KeyError, IndexError, TimeoutError) as error:
            report["failed_calls"] += 1
            report["last_error"] = type(error).__name__
            continue
        for ticker, source in batch.items():
            text = answer.get(ticker) if isinstance(answer, dict) else None
            if valid_translation(text, source):
                cache[translation_key(source)] = {"text_ko": text.strip(), "model": extract.GEMINI_MODEL,
                                                  "prompt_version": TRANSLATION_PROMPT_VERSION,
                                                  "created_at": c.utc_now()}
                report["translated"] += 1
            else:
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
    label = "추적 추천" if cand["classification"] == "recommended" else (
        "발굴 후보 · 자료 보강 필요" if cand["classification"] == "needs_evidence" else "발굴 후보")
    return label


def tracking_label(cand: dict) -> str:
    t = cand["tracking"]
    return {"tracked": f"추적 중 ({', '.join(t['idea_ids'])})", "closed": "추적 종료됨",
            "untracked": "미추적"}[t["status"]]


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
    lines.append(("section", "후보가 된 이유"))
    lines += [("item", x) for x in selection_lines(cand)]
    lines.append(("section", f"숫자 (관측 {cand['observed_at'][:16].replace('T', ' ')} UTC)"))
    lines.append(("item", f"내년 EPS 예상 ({eps['eps_target_period']} 회계연도 말, {eps['eps_currency']}, "
                          f"{cand['eps_provider']}, 회계기준 미표시): 90일 전 {money(eps['eps_90d'])} → "
                          f"30일 전 {money(eps['eps_30d'])} → 현재 {money(eps['eps_now'])} ({eps_change(eps)})"))
    lines.append(("item", price_line(cand)))
    lines.append(("section", "확인된 사업 근거"))
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
    if cand.get("review_note"):
        lines.append(("warn", cand["review_note"]))
    lines.append(("section", "다음 확인"))
    checks = cand["explanations"]["next_check"]["statements"]
    if checks:
        lines += [("item", s["text"]) for s in checks]
    else:
        lines.append(("item", "최근 실적 발표·가이던스 원문에서 이익 증가 원인과 지속 기간 확인"))
    lines.append(("section", "출처"))
    for s in cand["sources"]:
        lines.append(("link", f"{s['title']}|{s['url']}|{(s.get('observed_at') or '')[:10]}"))
    if cand["tracking"]["status"] == "tracked":
        lines.append(("command", f"/history {cand['identity']['ticker']}"))
    elif cand["candidate_id"]:
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
                out.append(f'· <a href="{esc(url)}">{esc(title)}</a> (관측 {esc(observed)})')
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
                out.append(f"- [{title}]({url}) (관측 {observed})")
        elif kind == "command":
            out.append(f"\n텔레그램: `{text}`")
        else:
            out.append(text_md)
    return "\n".join(out)


# ------------------------------------------------------------------ index & views

def load_index() -> dict:
    return c.read_json(index_path(), {})


def find(cid: str) -> tuple[dict | None, str]:
    """(candidate, state) where state is current / stale / not_current / unknown."""
    index = load_index()
    for cand in index.get("candidates", []):
        if cand["candidate_id"] and cand["candidate_id"] == cid:
            return cand, "stale" if index.get("stale") else "current"
    known = index.get("known", {}).get(cid)
    if known:
        last = known["versions"][-1]["version"]
        record = c.read_json(history_dir() / f"{last}.json", None)
        return record, "not_current"
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
        note = (f"⚠️ 최신 후보 목록에 없습니다. 마지막 관측 {esc(cand['observed_at'][:10])} 기준 기록입니다.\n\n")
        return [note + telegram_history_card(cand)]
    stale = load_index().get("stale") if state == "stale" else None
    return [telegram_card(cand, stale)]


def telegram_history_card(record: dict) -> str:
    eps = record["eps"]
    return (f"<b>{esc(record['identity']['ticker'])} {esc(record.get('name') or '')}</b>\n"
            f"{esc(record['candidate_id'])} · 버전 {esc(record['candidate_version'])}\n"
            f"내년 EPS 예상 ({esc(eps['eps_target_period'])}) {esc(money(eps['eps_90d']))} → {esc(money(eps['eps_now']))}")


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
    lines.append("화면(필터·상세 카드): `reports/generated/candidates.html`. 새 후보의 과거 그래프는 만들지 않으며, "
                 "추적을 시작한 뒤부터 관측이 쌓입니다.")
    return "\n".join(lines) + "\n"


def render_html(index: dict) -> str:
    payload = {"index": {k: v for k, v in index.items() if k not in ("candidates", "known")},
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
            report["translation"] = translate(rows, cache, c.load_dotenv_value("GEMINI_API_KEY"), cfg, call)
            c.atomic_json(translation_path(), cache)
        cands = build(snapshot, ref, c.read_json(c.ROOT / "config" / "entities.json", {}),
                      c.read_json(evidence_path(), {}), cache,
                      c.read_live_rows("investment_review_log"), policy_version())
        report["new_versions"] = store_versions(cands)
        earnings = snapshot.get("stages", {}).get("earnings", {})
        index.update(observed_at=snapshot["run"]["finished_at"], run_status=snapshot["run"]["status"],
                     source_snapshot=ref, screen_candidates=sum(1 for r in derived.get("rows", []) if r.get("candidate")),
                     coverage={"universe": snapshot["run"].get("universe_size"),
                               "earnings_requested": earnings.get("requested", 0),
                               "earnings_success": earnings.get("success", 0)},
                     # Unidentified rows stay visible (no ID, no tracking command) instead of vanishing.
                     candidates=cands,
                     unidentified=[x["identity"]["ticker"] for x in cands if not x["candidate_id"]])
    index["known"] = known_candidates()
    for cand in index["candidates"]:
        cand["first_seen_at"] = index["known"].get(cand["candidate_id"] or "", {}).get("first_seen_at")
    c.atomic_json(index_path(), index)
    (c.ROOT / "docs" / "candidates.md").write_text(render_markdown(index), encoding="utf-8")
    out = c.ROOT / "reports" / "generated"
    out.mkdir(parents=True, exist_ok=True)
    (out / "candidates.html").write_text(render_html(index), encoding="utf-8")
    report.update(cards=len(index["candidates"]), unidentified=len(index.get("unidentified", [])))
    return report


def approve(cid: str, approver: str) -> str:
    """Record a human approval of the current version; refuses unsourced evidence."""
    cid = normalize_id(cid) or ""
    cand = next((x for x in load_index().get("candidates", []) if x["candidate_id"] == cid), None)
    if cand is None:
        raise ValueError("candidate not in the latest index; regenerate cards first")
    evidence = c.read_json(evidence_path(), {})
    problems = evidence_problems(evidence.get(cid))
    if problems:
        raise ValueError("evidence incomplete: " + ", ".join(problems))
    evidence[cid]["approval"] = {"approved_by": approver, "approved_at": c.utc_now(),
                                 "candidate_version": cand["candidate_version"]}
    c.atomic_json(evidence_path(), evidence)
    return cand["candidate_version"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="action")
    gen = sub.add_parser("generate", help="build cards from the latest screener snapshot (default)")
    gen.add_argument("--no-translate", action="store_true")
    ap = sub.add_parser("approve", help="approve the current version after evidence is complete")
    ap.add_argument("candidate_id")
    ap.add_argument("--by", required=True)
    args = parser.parse_args(argv)
    if args.action == "approve":
        print(approve(args.candidate_id, args.by))
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
