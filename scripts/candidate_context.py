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
    # First seen by day: candidates seen the same day keep the A1/B1/A2... display order.
    pool.sort(key=lambda t: (state["candidates"].get(t["candidate_id"], {}).get("status") == "success",
                             t["first_seen_at"][:10], t["rank"], t["candidate_id"]))
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
    found, examined, notes, bodies, failures = [], [], [], 0, 0
    for filing in filings:
        if bodies >= cfg["documents_per_company"]:
            break
        if found and filing["rank"] == 2 and any(cf.load_document(d).get("relevance", {}).get("core_earnings") for d in found):
            break  # a results release was found: the large periodic report is not needed
        index_url = cf.filing_index_url(issuer["cik"], filing["accessionNumber"])
        try:
            page, final, _ = client.get(index_url)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            # One unreachable filing does not discard what other filings gave (quality=partial).
            failures += 1
            notes.append(f"{filing['accessionNumber']} index {getattr(error, 'code', type(error).__name__)}")
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
                except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
                    failures += 1
                    notes.append(f"{doc['name']} {getattr(error, 'code', type(error).__name__)}")
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
        return {"status": "success", "quality": "partial" if failures else "complete", "document_ids": found,
                "examined": examined, "notes": notes, "failures": failures}
    if not filings:
        notes.append(f"no 8-K/6-K results or periodic report in {cfg['lookback_days']} days")
    return {"status": "failed" if failures else "no_relevant_document", "document_ids": [], "examined": examined,
            "notes": notes, "failures": failures}


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
    chosen = select(ready, state, now, max(0, cfg["companies_per_day"] - usage["companies"]))
    for target in chosen:
        entry = state["candidates"].setdefault(target["candidate_id"], {})
        usage["companies"] += 1
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

PROMPT_VERSION = "context-ko-v3"
PARSER_VERSION = "context-check-v5"
KINDS = ("fact", "guidance", "interpretation")
SUBJECTS = ("issuer", "subsidiary", "segment", "customer", "other")
DRIVERS = ("volume", "price", "mix", "margin_cost", "capacity", "backlog", "buyback_sharecount", "tax", "fx",
           "acquisition_disposal", "one_off", "accounting", "unknown")
DIRECTIONS = ("positive", "negative", "mixed", "unknown")
# Automatic drafts never assert a direct link to the estimate revision; a person confirms that elsewhere.
LINKS = ("temporal_context", "unconfirmed")
FORWARD = ("expect", "outlook", "guidance", "forecast", "anticipate", "project", "will ", "target")
RAISE = ("raise", "raised", "increase", "increased", "higher", "above", "up from", "improv")
LOWER = ("lower", "lowered", "reduce", "reduced", "cut", "decrease", "decreased", "below", "down from", "declin")
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
        for b_index, block in enumerate(doc["blocks"]):
            text = cf.block_text(block)
            score = block_score(text)
            if score > 0:
                scored.append((score, d_index, b_index, {"document_id": doc["document_id"], "block_id": block["id"],
                                                         "text": text}))
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
        "7. gaap: 원문에 GAAP/non-GAAP/adjusted 표기가 있을 때만 적고 없으면 unknown.\n"
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


def metric_problem(metric: str, figures: list[str], quote_raw: str) -> str | None:
    """Each figure's nearest metric mention is the claimed one, within the same statement."""
    q, m = squash(quote_raw), squash(metric)
    if not m or m not in q:
        return "metric_not_in_quote"
    names = {squash(x) for x in METRIC_KO} | {m}
    mentions = [(x.start(), x.end(), name) for name in names
                for x in re.finditer(r"(?<![a-z])" + re.escape(name) + r"(?![a-z])", q)]
    claimed = [(s, e) for s, e, name in mentions if name == m]
    for figure in figures:
        at = q.find(squash(figure))
        if at < 0 or not mentions:
            continue
        # Nearest mention by distance; at a tie the longer name wins ('adjusted ebitda' over 'ebitda').
        s, e, name = min(mentions, key=lambda x: (min(abs(x[0] - at), abs(x[1] - at)), -len(x[2])))
        # A shorter name counts as the claimed metric only inside a mention of it: 'revenue' within
        # 'total company revenue', never a separate 'net income' next to 'net income attributable to ...'.
        if name != m and not any(cs <= s and e <= ce for cs, ce in claimed):
            return "figure_belongs_to_another_metric"
        # 'operating income' inside 'adjusted operating income' is another metric unless claimed so.
        qualifier = re.search(r"(adjusted|non-gaap|organic|core|segment|pro forma)\s+$", q[max(0, s - 14):s])
        if qualifier and qualifier.group(1) not in m:
            return "figure_belongs_to_another_metric"
        between = q[min(e, at):max(s, at)]
        if re.search(r"[.;]\s", between):
            return "figure_belongs_to_another_metric"
    return None


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


def check_item(item: dict, blocks: dict, issuer: dict, what: str) -> tuple[str | None, dict]:
    """(problem, checked item). Structural checks only: passing means 'automatic, unreviewed'."""
    if not isinstance(item, dict):
        return "not_an_object", {}
    key = (item.get("document_id"), item.get("block_id"))
    if key not in blocks:
        return "unknown_block", {}
    quote_raw = str(item.get("quote", ""))
    quote, block = squash(quote_raw), blocks[key]
    if len(quote) < 8 or quote not in squash(block):
        return "quote_not_in_block", {}
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
    if gaap != "unknown" and gaap != expected:
        return "gaap_not_as_stated", {}  # an asserted label must be the source's; unknown is filled from it
    currencies = {"$": "USD", "€": "EUR", "£": "GBP"}
    derived = sorted({v for k, v in currencies.items() if any(k in f for f in figures)})
    if item.get("currency") and item["currency"] not in derived:
        return "currency_not_in_figures", {}
    if item.get("unit") and not any(str(item["unit"]).lower() in f.lower() for f in figures):
        return "unit_not_in_figures", {}
    if kind == "fact" and any(w in quote for w in FORWARD):
        return "guidance_written_as_fact", {}
    if kind == "guidance" and not any(w in quote for w in FORWARD):
        return "guidance_without_forward_wording", {}
    if any(w in note for w in KO_UP) and (not any(w in quote for w in RAISE) or any(w in quote for w in LOWER)):
        return "raise_not_in_quote", {}
    if any(w in note for w in KO_DOWN) and not any(w in quote for w in LOWER):
        return "cut_not_in_quote", {}
    subject = item.get("subject") or "issuer"
    if subject not in SUBJECTS:
        return "bad_subject", {}
    subject_name = str(item.get("subject_name") or "")
    if subject == "issuer" and re.search(r"\b(subsidiary|mplx|customer)\b", quote):
        return "unverified_issuer_subject", {}
    if subject != "issuer" and (not subject_name or squash(subject_name) not in quote):
        return "subject_not_in_quote", {}
    core = subject == "issuer" and issuer_named(quote_raw, issuer)
    if what == "claim" and (item.get("direction", "unknown") not in DIRECTIONS
                            or not set(item.get("drivers") or ["unknown"]) <= set(DRIVERS)):
        return "bad_tag", {}
    label = METRIC_KO.get(metric.lower(), metric) if metric else ""
    period = item.get("period") if item.get("period") and item["period"] != "unknown" else ""
    head = "".join([f"[{subject_name}] " if subject != "issuer" else "",
                    f"{label}({metric})" if label and label != metric else label,
                    f" · {period}" if period else ""])
    body = " / ".join(figures)
    text_ko = f"{head}: {body} — {note}" if head and body else (f"{head} — {note}" if head else note)
    return None, {"text_ko": text_ko, "note_ko": note, "kind": kind, "quote": quote_raw, "document_id": key[0],
                  "block_id": key[1], "metric": metric or None, "figures": figures, "period": item.get("period") or "unknown",
                  "currency": derived[0] if len(derived) == 1 else None, "gaap": expected, "subject": subject,
                  "subject_name": subject_name or None, "core": core,
                  "drivers": item.get("drivers") or ["unknown"], "direction": item.get("direction", "unknown")}


def excerpt(item) -> dict:
    """What was refused, kept short for review; never used on the card."""
    if not isinstance(item, dict):
        return {}
    return {"note_ko": str(item.get("note_ko") or item.get("text_ko") or "")[:200],
            "figures": [str(f)[:40] for f in (item.get("figures") or [])[:5]] if isinstance(item.get("figures"), list) else [],
            "quote": str(item.get("quote", ""))[:200], "where": f"{item.get('document_id')}#{item.get('block_id')}"}


def validate_draft(answer: dict, blocks: list[dict], issuer: dict | None = None) -> dict:
    index = {(b["document_id"], b["block_id"]): b["text"] for b in blocks}
    issuer = issuer or {}
    claims, limitations, rejected = [], [], []
    answer = answer if isinstance(answer, dict) else {}
    for what, items, out, cap in (("claim", answer.get("claims"), claims, 5),
                                  ("limitation", answer.get("limitations"), limitations, 3)):
        for item in (items or [])[:cap] if isinstance(items, list) else []:
            problem, checked = check_item(item, index, issuer, what)
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


def run_drafts(now: datetime | None = None, call=None, deadline: float | None = None,
               current: dict[str, str] | None = None, clock=time.monotonic) -> dict:
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
    for cid, entry in draft_queue(state, current, now):
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

        def finish(outcome, **fields):
            audit.update(outcome=outcome, finished_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         budget={"candidate_context_before": before_component,
                                 "candidate_context_after": component_calls(day),
                                 "requests_sent": c.model_calls_today() - before_calls},
                         raw_response={"available": "text" in raw_seen,
                                       **{k: raw_seen.get(k) for k in ("text", "finish_reason", "usage")}},
                         **fields)
            if not write_audit(audit, day):
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
        answer_copy = json.loads(json.dumps(answer, ensure_ascii=False, default=str))  # before validation
        checked = validate_draft(answer, blocks, {**(entry.get("issuer") or {}), "ticker": entry.get("ticker")})
        finish("answered", answer=answer_copy, validation=checked, context_id="CTX-" + sha[:16].upper())
        record = {"context_id": "CTX-" + sha[:16].upper(), "candidate_id": cid, "ticker": entry.get("ticker"),
                  "issuer_cik": (entry.get("issuer") or {}).get("cik"), "document_ids": entry["document_ids"],
                  "eps_target_period": entry.get("eps_target_period"),
                  "source_blocks": [f"{b['document_id']}#{b['block_id']}" for b in blocks], "input_sha": sha,
                  "model": extract.GEMINI_MODEL, "prompt_version": PROMPT_VERSION, "parser_version": PARSER_VERSION,
                  "generated_at": now.isoformat(timespec="seconds"),
                  "source_coverage": coverage_state, "review": "자동 정리·미검토", **checked}
        store_context(record)
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
        report["drafts"] = {"held": True} if report["held"] else run_drafts(deadline=deadline, current=report.get("current", {}))
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
