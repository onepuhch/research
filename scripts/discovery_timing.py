"""First discovery times and later outcomes of screen candidates (P3, minimal; no new collection).

Fixed records, one per company|thesis, built from the stored daily screens, the stored candidate
drafts and the alert ledger. The population is every condition-passing company of every stored
screen (shown cards, industry-folded and outside the top lists); a company that leaves the list or
does badly stays in it. A 'first' value is written once from the snapshot it came from and never
moves: a re-render, a later snapshot or a newer draft never changes it, and rendered_at is never
used as a discovery time. Unknown values stay null.

mode: 'retrospective' when the first pass is older than this store (rebuilt from archives after the
fact, like N's manual AEHR/OSCR selection), 'prospective' when the store already existed when it was
first seen. Claims about earlier discovery use prospective records only.

Latency is the first measure of earliness, never 'earlier than the market':
  evidence document: SEC filing date -> our download (date precision; the filing time is not kept)
  first condition pass -> first card -> first alert receipt (hours)
Our own later EPS observation for the same comparison key is shown apart.
Outcome: research_returns.compare with the first card (else the first pass) as the registration time:
first regular close after it, 30/90/180 calendar days, USD adjusted closes, SPY, 0.20%p round-trip
cost, from stored price batches only. A ticker without stored prices is 'price not collected'.

    python scripts/discovery_timing.py           # update the store and write the report
    python scripts/discovery_timing.py --render  # report from the store as it is
"""
from __future__ import annotations

import argparse
import statistics
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import common as c

VERSION = "discovery-timing-v2"
HORIZONS = (30, 90, 180)
PRICE_MISSING = "시세 미수집"


def store_path() -> Path:
    return c.DATA_DIR / "discovery_timing.json"


def load() -> dict:
    store = c.read_json(store_path(), None)
    if store is None:
        return {"version": VERSION, "created_at": None, "snapshots": [], "records": {}}
    if not isinstance(store.get("records"), dict):
        raise ValueError("invalid discovery timing store; restore it before updating")
    return store


def screen_states(derived: dict) -> dict[str, str]:
    import candidates
    shown = {t for t, _ in candidates.display_order(derived)}
    folded = {t for g in derived.get("industry_groups") or [] for t in g.get("folded", [])} - shown
    return {r["ticker"]: "card" if r["ticker"] in shown else "folded" if r["ticker"] in folded else "outside"
            for r in derived.get("rows", []) if r.get("candidate")}


def observation(path: Path, run: dict, row: dict, state: str) -> dict:
    import material_updates
    cfg = run.get("config") or {}
    return {"snapshot": path.name, "run_id": run.get("run_id"), "observed_at": run["finished_at"], "state": state,
            "eps": {k: row.get(k) for k in ("eps_now", "eps_30d", "eps_90d", "up30", "down30", "analysts")},
            "comparison_key": material_updates.comparison_key(row, material_updates.SCREEN_PROVIDER),
            "rule": {"code_version": run.get("code_version"), "top_n": cfg.get("top_n"),
                     "max_per_industry": cfg.get("max_per_industry")}}


def new_record(entity: str | None, ticker: str, cid: str | None) -> dict:
    return {"entity_id": entity, "ticker": ticker, "candidate_id": cid, "mode": None, "passes": 0,
            "first_pass": None, "first_card": None, "first_folded": None, "last_pass": None,
            "first_evidence": None, "first_alert": None, "bootstrap": None}


def first_evidence(cid: str) -> dict | None:
    """The earliest stored draft that the validator accepts, with its cited documents' dates."""
    import candidates
    records = [c.read_json(p, {}) for p in (c.DATA_DIR / "candidate_context_history").glob("CTX-*.json")]
    for record in sorted((r for r in records if r.get("candidate_id") == cid), key=lambda r: r.get("generated_at") or ""):
        if record.get("context_status") != "draft_ready":
            continue
        view, _ = candidates.verified_context(record)
        claims = (view or {}).get("claims") or []
        if not claims:
            continue
        cited = {x.get("document_id") for x in claims}
        return {"context_id": record["context_id"], "generated_at": record.get("generated_at"),
                "validator": view.get("display_validator_version"), "claims": len(claims),
                "documents": [{k: d.get(k) for k in ("document_id", "form", "filed_at", "observed_at", "url")}
                              for d in view.get("documents") or [] if d.get("document_id") in cited]}
    return None


def first_alert(ledger: dict, entity: str) -> dict | None:
    events = [e for e in ledger.get("events", {}).values()
              if e.get("entity_id") == entity and e.get("status") in ("sent", "uncertain")]
    receipts = []
    for e in events:
        attempt = next((x for x in e.get("attempts") or [] if x.get("status") in ("sent", "uncertain")), None)
        if attempt:
            receipts.append({"at": attempt["at"], "status": attempt["status"], "message_id": attempt.get("message_id"),
                             "channel": e.get("channel"), "event": e.get("event"), "day": e.get("day")})
    return min(receipts, key=lambda r: r["at"]) if receipts else None


def update(now: datetime | None = None) -> dict:
    """Add the snapshots not yet read and fill first values that are still null; returns a report."""
    import candidate_alerts
    import candidates
    import screen_revisions
    now = now or datetime.now(timezone.utc)
    store = load()
    store["created_at"] = store["created_at"] or now.isoformat(timespec="seconds")
    created = datetime.fromisoformat(store["created_at"])
    registry = c.read_json(c.ROOT / "config" / "entities.json", {})
    seen, added = set(store["snapshots"]), 0
    paths = screen_revisions.snapshots()
    # Early screens did not record the exchange: a ticker identified by any stored screen keeps that entity.
    known = {r["ticker"]: candidates.identify(r, registry)["entity_id"]
             for p in paths for r in screen_revisions.load_snapshot(p).get("derived", {}).get("rows", [])
             if candidates.identify(r, registry)["entity_id"]}
    for path in paths:
        if path.name in seen:
            continue
        snap = screen_revisions.load_snapshot(path)
        run = snap.get("run") or {}
        store["snapshots"].append(path.name)
        if run.get("status") not in ("success", "degraded") or not run.get("finished_at"):
            continue  # no usable observation time: never back-filled from a file name
        added += 1
        states = screen_states(snap.get("derived", {}))
        for row in snap["derived"]["rows"]:
            if not row.get("candidate"):
                continue
            entity = candidates.identify(row, registry)["entity_id"] or known.get(row["ticker"])
            key = f"{entity or 'unidentified:' + row['ticker']}|{candidates.THESIS_KEY}"
            rec = store["records"].setdefault(key, new_record(entity, row["ticker"],
                                                              candidates.candidate_id(entity) if entity else None))
            obs = observation(path, run, row, states[row["ticker"]])
            if rec["first_pass"] is None:
                rec["first_pass"] = obs
                rec["mode"] = ("retrospective" if datetime.fromisoformat(obs["observed_at"]) < created
                               else "prospective")
            if obs["state"] == "card" and rec["first_card"] is None:
                rec["first_card"] = obs
            if obs["state"] == "folded" and rec["first_folded"] is None:
                rec["first_folded"] = obs
            if not rec["last_pass"] or obs["observed_at"] >= rec["last_pass"]["observed_at"]:
                rec["last_pass"] = {k: obs[k] for k in ("snapshot", "observed_at", "state", "eps", "comparison_key")}
            rec["passes"] += 1
    ledger = candidate_alerts.load_ledger()
    boot = ledger.get("bootstrap") or {}
    boot_entities = {k.split("|")[0] for k in boot.get("keys") or []}
    for rec in store["records"].values():
        if rec["entity_id"] and rec["first_alert"] is None:
            rec["first_alert"] = first_alert(ledger, rec["entity_id"])
        if rec["entity_id"] and rec["bootstrap"] is None and rec["entity_id"] in boot_entities:
            rec["bootstrap"] = {"date": boot.get("date"), "snapshot": (boot.get("source_snapshot") or {}).get("path")}
        if rec["candidate_id"] and rec["first_evidence"] is None:
            rec["first_evidence"] = first_evidence(rec["candidate_id"])
    store["version"], store["updated_at"] = VERSION, now.isoformat(timespec="seconds")
    c.atomic_json(store_path(), store)
    return {"snapshots_added": added, "records": len(store["records"])}


# ------------------------------------------------------------------ measures

def hours(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() / 3600


def latencies(rec: dict) -> dict:
    card = rec.get("first_card") or {}
    out = {"pass_to_card_h": hours((rec.get("first_pass") or {}).get("observed_at"), card.get("observed_at")),
           "card_to_alert_h": hours(card.get("observed_at"), (rec.get("first_alert") or {}).get("at")),
           "filing_to_download_days": []}
    for d in (rec.get("first_evidence") or {}).get("documents") or []:
        if d.get("filed_at") and d.get("observed_at"):
            out["filing_to_download_days"].append(
                (datetime.fromisoformat(d["observed_at"]).date() - datetime.fromisoformat(d["filed_at"]).date()).days)
    return out


def own_eps_change(rec: dict) -> dict:
    """Our own stored EPS for the same key since the first pass; not a claim about the market."""
    first, last = rec.get("first_pass") or {}, rec.get("last_pass") or {}
    if not first or not last or first.get("observed_at") == last.get("observed_at"):
        return {"status": "단일 관측"}
    if first.get("comparison_key") != last.get("comparison_key"):
        return {"status": "비교 기준 변경"}
    a, b = first["eps"].get("eps_now"), last["eps"].get("eps_now")
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)) or a <= 0:
        return {"status": "비교 불가(기준값)"}
    days = (datetime.fromisoformat(last["observed_at"]) - datetime.fromisoformat(first["observed_at"])).days
    return {"status": "관측", "pct": (b / a - 1) * 100, "days": days}


# ------------------------------------------------------------------ outcome definitions (Q3-A)

# Each definition has its own fixed start; results of different definitions are never mixed.
DEFINITIONS = {
    "population": "최초 조건 통과 이후 첫 정규장 종가(모집단 기본, 카드 진입으로 바뀌지 않음)",
    "card": "첫 대표 카드 이후 첫 정규장 종가(카드 경험 기업만)",
    "alert": "첫 발송 영수증(sent) 이후 첫 정규장 종가(실제 알림 기업만)",
}
NO_START = {"card": "대표 카드 없음", "alert": "알림 영수증 없음"}


def definition_start(rec: dict, definition: str) -> str | None:
    if definition == "population":
        return (rec.get("first_pass") or {}).get("observed_at")
    if definition == "card":
        return (rec.get("first_card") or {}).get("observed_at")
    alert = rec.get("first_alert") or {}
    return alert.get("at") if alert.get("status") == "sent" else None


def outcomes(rec: dict, batch: dict | None, definition: str = "population") -> dict[int, dict]:
    """research_returns.compare from the definition's own fixed start; a missing start is its own state
    (never replaced by another definition's start)."""
    import research_returns
    start = definition_start(rec, definition)
    if start is None:
        return {h: {"status": NO_START.get(definition, "기준 시각 없음"), "outcome_definition": definition} for h in HORIZONS}
    if not batch or rec["ticker"] not in batch.get("series", {}) or "SPY" not in batch.get("series", {}):
        return {h: {"status": PRICE_MISSING, "outcome_definition": definition} for h in HORIZONS}
    cohort = {"ticker": rec["ticker"], "captured_at": start}
    return {h: {**research_returns.compare(cohort, batch["series"][rec["ticker"]], batch["series"]["SPY"],
                                           batch["retrieved_at"], h), "outcome_definition": definition}
            for h in HORIZONS}


# ------------------------------------------------------------------ candidate prices (Q3-B)

PRICE_DEFAULTS = {"requests_per_day": 20, "time_budget_s": 120, "timeout_s": 15, "min_interval_s": 0.5,
                  "start_pad_days": 7, "stop_after_5xx": 2, "retries_per_day": 5, "retry_wait_days": [1, 3, 7]}


def price_settings() -> dict:
    return {**PRICE_DEFAULTS, **c.policy().get("candidate_prices", {})}


def price_dir() -> Path:
    return c.DATA_DIR / "candidate_prices"


def queue_path() -> Path:
    return price_dir() / "queue.json"


def price_batches() -> list[dict]:
    """Stored batches, oldest first: candidate batches and the tracked-company batches (same format)."""
    files = sorted(price_dir().glob("2*.json")) + sorted((c.DATA_DIR / "return_history").glob("*.json"))
    batches = [c.read_json(p, None) for p in files]
    return sorted((b for b in batches if b and b.get("retrieved_at")), key=lambda b: b["retrieved_at"])


def batch_for(ticker: str, batches: list[dict]) -> dict | None:
    """The latest batch holding this ticker and SPY, used whole: prices from different retrievals are
    never joined (adjusted closes can be revised). A newer failed batch never hides an older valid one."""
    for batch in reversed(batches):
        series = batch.get("series") or {}
        if series.get(ticker) and series.get("SPY"):
            return batch
    return None


def price_queue(store: dict, queue: dict) -> list[str]:
    """The fixed collection order: the first build orders today's identified companies (card or alert
    experience first, then first pass time); later entrants are appended in first-pass order (FIFO).
    Departed companies stay."""
    records = [r for r in store["records"].values() if r.get("entity_id") and r.get("first_pass")]
    by_pass = sorted(records, key=lambda r: (r["first_pass"]["observed_at"], r["ticker"]))
    if not queue.get("order"):
        first = [r for r in by_pass if r.get("first_card") or r.get("first_alert")]
        queue["order"] = [r["ticker"] for r in first] + [r["ticker"] for r in by_pass if r not in first]
        queue["fixed_at"] = c.utc_now()
    else:
        known = set(queue["order"])
        queue["order"] += [r["ticker"] for r in by_pass if r["ticker"] not in known]
    return queue["order"]


def end_confirmed(due: str, now: datetime) -> bool:
    """The first regular session on or after 'due' has closed (and an hour passed) by now."""
    import market_calendar
    day = datetime.fromisoformat(due).date()
    for _ in range(10):
        close = market_calendar.close_time(day)
        if close:
            return close + timedelta(hours=1) <= now
        day += timedelta(days=1)
    return False


def needs_prices(rec: dict, batch: dict | None, now: datetime) -> bool:
    """No stored prices yet, or an evaluation end close (or the start close) is confirmed by now but not
    in the stored batch. A data gap inside a batch is a state, not a reason to ask again every day.
    False once every definition with a start is evaluated for all horizons."""
    if batch is None:
        return True
    retrieved = datetime.fromisoformat(batch["retrieved_at"])
    for definition in DEFINITIONS:
        for result in outcomes(rec, batch, definition).values():
            if (result["status"] == "평가일 대기" and end_confirmed(result["due"], now)
                    and not end_confirmed(result["due"], retrieved)):
                return True
            if result["status"] == "기준 종가 대기" and retrieved.date() < now.date():
                return True
    return False


def yahoo_fetch(url: str, timeout: float) -> dict:
    from urllib.request import Request, urlopen
    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=timeout) as response:
        return json.load(response)


def collect_prices(now: datetime | None = None, fetch=None, sleep=None, clock=None) -> dict:
    """At most requests_per_day Yahoo requests a KST day (SPY, failures and retries included), sequential,
    within time_budget_s, each counted before it is sent; a 429 or stop_after_5xx consecutive 5xx ends
    today's collection. One SPY request per batch. Raw payloads are kept with the batch."""
    import time
    from urllib.error import HTTPError
    import research_returns
    now = now or datetime.now(timezone.utc)
    fetch, sleep, clock = fetch or yahoo_fetch, sleep or time.sleep, clock or time.monotonic
    cfg = price_settings()
    store = load()
    queue = c.read_json(queue_path(), {"order": [], "days": {}})
    order = price_queue(store, queue)
    day = now.astimezone(timezone(timedelta(hours=9))).date().isoformat()
    used = queue.setdefault("days", {}).setdefault(day, {"requests": 0, "retries": 0})
    if "retries" not in used:
        # A day recorded before retries were counted: none if it sent nothing, else its share is
        # treated as used (its retries cannot be proven) -- for that day only.
        used["retries"] = 0 if not used.get("requests") else cfg["retries_per_day"]
    batches = price_batches()
    by_ticker = {r["ticker"]: r for r in store["records"].values() if r.get("entity_id")}
    status = queue.setdefault("tickers", {})
    # R2: a ticker whose last request failed waits 1/3/7 days and then competes only for the day's few
    # retry places (rotated by its last attempt); untried and newly due tickers keep the rest, in order.
    due = [t for t in order if t in by_ticker and needs_prices(by_ticker[t], batch_for(t, batches), now)]
    failing = {t for t in due if (status.get(t) or {}).get("state") == "failed"}
    fresh = [t for t in due if t not in failing]
    ready = sorted((t for t in failing if (status[t].get("next_eligible_at") or "") <= now.isoformat()),
                   key=lambda t: (status[t].get("last_attempt_at") or "", order.index(t)))
    report = {"due": len(due), "fresh": len(fresh), "retry_waiting": len(failing) - len(ready), "retry_ready": len(ready),
              "retries": 0,
              "requests": 0, "collected": 0, "failures": 0, "stopped": None}
    if used.get("stopped"):
        report["stopped"] = f"stopped_today:{used['stopped']}"  # a 429/5xx stop holds for the rest of the KST day
        return report
    room = cfg["requests_per_day"] - used["requests"] - 1  # one for SPY
    # The retry share is per KST day across every call (R2 review), not per call.
    retry_left = max(0, cfg["retries_per_day"] - used["retries"])
    retries = ready[:max(0, min(retry_left, room))]
    plan = fresh[:max(0, room - len(retries))] + retries
    retry_set = set(retries)
    report.update(retry_share_left=retry_left)
    if not plan or used["requests"] >= cfg["requests_per_day"]:
        # Nothing to fetch means no SPY request either.
        report["stopped"] = ("daily_requests" if used["requests"] >= cfg["requests_per_day"] and (fresh or ready)
                             else "retry_share_used" if ready and not fresh and not retry_left
                             else "daily_requests" if (fresh or ready) else "nothing_due")
        c.atomic_json(queue_path(), queue)
        return report
    deadline = clock() + cfg["time_budget_s"]
    batch = {"retrieved_at": now.isoformat(), "kind": "candidate", "series": {}, "sources": {}, "failures": []}
    fivexx = 0

    def request(ticker: str, start: datetime) -> str | None:
        nonlocal fivexx
        if used["requests"] >= cfg["requests_per_day"]:
            return "daily_requests"
        if clock() + cfg["timeout_s"] > deadline:
            return "time_budget"
        used["requests"] += 1
        report["requests"] += 1
        entry = status.setdefault(ticker, {"attempts": 0})
        if ticker in retry_set:
            used["retries"] += 1  # stored with the request count, before sending; never given back
            report["retries"] += 1
        entry.update(attempts=entry.get("attempts", 0) + 1, last_attempt_at=now.isoformat())
        c.atomic_json(queue_path(), queue)  # counted before it is sent
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={int(start.timestamp())}"
               f"&period2={int(now.timestamp())}&interval=1d&events=div%2Csplits&includeAdjustedClose=true")
        try:
            payload = fetch(url, cfg["timeout_s"])
            batch["series"][ticker] = research_returns.parse(payload, ticker, now.isoformat())
            batch["sources"][ticker] = {"url": url, "payload": payload}
            fivexx = 0
            entry.update(state="ok", failures=0, next_eligible_at=None, reason=None)
        except HTTPError as error:
            batch["failures"].append({"ticker": ticker, "error_type": "HTTPError", "http_status": error.code})
            if error.code == 429:
                return "rate_limited"  # the provider's limit, not this ticker's failure
            fivexx = fivexx + 1 if error.code >= 500 else 0
            failed(entry, f"HTTP {error.code}")
            if fivexx >= cfg["stop_after_5xx"]:
                return "server_errors"
        except (OSError, ValueError, KeyError, TypeError, IndexError, OverflowError) as error:
            batch["failures"].append({"ticker": ticker, "error_type": type(error).__name__})
            failed(entry, type(error).__name__)
        sleep(cfg["min_interval_s"])
        return None

    def failed(entry: dict, reason: str) -> None:
        """Not delisted, not removed: the ticker stays in the population and waits 1, 3, then 7 days."""
        if entry is status.get("SPY"):
            return
        entry["failures"] = entry.get("failures", 0) + 1
        waits = cfg["retry_wait_days"]
        entry.update(state="failed", reason=reason,
                     next_eligible_at=(now + timedelta(days=waits[min(entry["failures"], len(waits)) - 1])).isoformat())

    starts = {t: datetime.fromisoformat(by_ticker[t]["first_pass"]["observed_at"]) for t in plan}
    earliest = min(starts.values()) - timedelta(days=cfg["start_pad_days"])
    stop = request("SPY", earliest)
    if stop is None and "SPY" not in batch["series"]:
        stop = "spy_missing"  # a batch without SPY cannot be compared; the tickers wait for tomorrow
    for ticker in plan if stop is None else []:
        stop = request(ticker, earliest)
        if stop:
            break
    if stop is None and len(fresh) + len(ready) > len(plan):
        stop = "daily_requests"  # the day's share is used; the rest waits in order
    if stop in ("rate_limited", "server_errors"):
        used["stopped"] = stop  # a same-day rerun cannot go around it; tomorrow starts again
    report.update(stopped=stop, collected=len([t for t in batch["series"] if t != "SPY"]), failures=len(batch["failures"]),
                  day_requests=used["requests"], day_retries=used["retries"])
    if batch["series"] or batch["failures"]:
        price_dir().mkdir(parents=True, exist_ok=True)
        c.atomic_json(price_dir() / (now.strftime("%Y%m%dT%H%M%S%f") + ".json"), batch)
    c.atomic_json(queue_path(), queue)
    return report


def price_summary(store: dict, batches: list[dict]) -> dict:
    records = [r for r in store["records"].values()]
    held = {r["ticker"] for r in records if batch_for(r["ticker"], batches)}
    queue = c.read_json(queue_path(), {"order": []})
    tickers = queue.get("tickers") or {}
    failed = {t for t, e in tickers.items() if e.get("state") == "failed"} - held
    untried = {r["ticker"] for r in records if r.get("entity_id") and r["ticker"] not in tickers and r["ticker"] not in held}
    state_of = lambda r: "card" if r.get("first_card") else "folded" if r.get("first_folded") else "outside"  # noqa: E731
    by_state = {}
    for r in records:
        if r.get("entity_id"):
            s = by_state.setdefault(state_of(r), [0, 0])
            s[0] += 1
            s[1] += r["ticker"] in held
    identified = [r for r in records if r.get("entity_id")]
    return {"targets": len(identified), "held": len([r for r in identified if r["ticker"] in held]),
            "waiting": len([r for r in identified if r["ticker"] not in held and r["ticker"] not in failed]),
            "failed": len(failed), "untried": len(untried), "unidentified": len(records) - len(identified),
            "by_state": by_state, "queue_fixed_at": queue.get("fixed_at")}


def median_text(values: list[float], unit: str, digits: int = 1) -> str:
    values = [v for v in values if v is not None]
    return f"중앙값 {statistics.median(values):.{digits}f}{unit} (n={len(values)})" if values else "자료 없음 (n=0)"


def render(store: dict | None = None) -> str:
    store = store or load()
    records = list(store["records"].values())
    batches = price_batches()
    lines = ["## 발견 시점과 이후 결과 (최소 기록)", "",
             f"조건 통과 기업 전체가 모집단입니다(대표 카드·업종 묶음·일반 순위 밖, 이탈 기업 포함). 기록 시작 "
             f"{store.get('created_at') or '-'}; 그 전에 처음 관측된 기업은 저장 스냅샷에서 복원한 **사후(retrospective)** 기록입니다. "
             "적중률·조기 발견 성과는 충분한 전향(prospective) 표본 전에는 표시하지 않습니다.", ""]
    if not records:
        return "\n".join(lines + ["기록 없음.", ""])
    count = lambda f: sum(1 for r in records if f(r))  # noqa: E731
    lines += [f"- 기업 {len(records)}곳 (사후 {count(lambda r: r['mode'] == 'retrospective')}, "
              f"전향 {count(lambda r: r['mode'] == 'prospective')}, 식별 불가 {count(lambda r: not r['entity_id'])})",
              f"- 대표 카드에 오른 적 있음 {count(lambda r: r['first_card'])} · 업종 묶음으로 접힌 적 있음 "
              f"{count(lambda r: r['first_folded'])} · 일반 순위 밖만 {count(lambda r: not r['first_card'] and not r['first_folded'])}",
              f"- 실제 알림 {count(lambda r: r['first_alert'])} · 초기 관측 목록(알림 없음) "
              f"{count(lambda r: r['bootstrap'] and not r['first_alert'])} · 유효 근거 초안 {count(lambda r: r['first_evidence'])}"]
    lat = [latencies(r) for r in records]
    lines += ["", "지연시간(빠르다는 뜻이 아니라 우리 경로의 소요 시간):",
              f"- 근거 문서 제출일→수집: {median_text([d for x in lat for d in x['filing_to_download_days']], '일')} (날짜 정밀도)",
              f"- 첫 조건 통과→첫 대표 카드: {median_text([x['pass_to_card_h'] for x in lat], '시간', 2)}",
              f"- 첫 대표 카드→첫 알림: {median_text([x['card_to_alert_h'] for x in lat], '시간', 2)}"]
    eps = [own_eps_change(r) for r in records]
    lines.append(f"- 첫 통과 이후 자체 관측 EPS(같은 비교 키): 관측 {sum(e['status'] == '관측' for e in eps)}곳, "
                 f"기준 변경 {sum(e['status'] == '비교 기준 변경' for e in eps)}곳, 단일 관측 {sum(e['status'] == '단일 관측' for e in eps)}곳")
    lines += ["", "이후 주가(기존 성과 정의: 30/90/180 달력일, USD 조정 종가, SPY 비교, 왕복 0.20%p). 기준마다 시작 시각이 고정되며 서로 섞지 않습니다:"]
    for definition, label in DEFINITIONS.items():
        lines.append(f"- {label}")
        for h in HORIZONS:
            statuses: dict[str, int] = {}
            for r in records:
                status = outcomes(r, batch_for(r["ticker"], batches), definition)[h]["status"]
                statuses[status] = statuses.get(status, 0) + 1
            lines.append(f"  - {h}일: " + ", ".join(f"{k} {v}" for k, v in sorted(statuses.items())))
    p = price_summary(store, batches)
    states = " · ".join(f"{name} {held}/{total}" for name, (total, held) in sorted(p["by_state"].items()))
    lines += ["", f"후보 시세 보관: 대상 {p['targets']}곳 중 보유 {p['held']} · 대기 {p['waiting']}(미시도 {p['untried']}) · "
              f"실패 후 재시도 대기 {p['failed']} · "
              f"식별 불가 {p['unidentified']} (상태별 보유/대상: {states}). 하루 추가 요청 {price_settings()['requests_per_day']}회 이내로 "
              "대표 카드·알림 경험 기업부터 순서대로 수집합니다. 시세가 없는 기업을 분모에서 빼지 않습니다.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--render", action="store_true", help="report only; the store is not updated")
    parser.add_argument("--collect-prices", action="store_true",
                        help="update the store, then fetch the day's share of candidate prices (Yahoo, budgeted)")
    args = parser.parse_args(argv)
    if not args.render:
        print(f"[discovery_timing] {update()}")
    if args.collect_prices:
        report = collect_prices()
        trouble = report["failures"] or report["stopped"] in ("rate_limited", "server_errors", "spy_missing")
        c.record_run("candidate_prices", "degraded" if trouble else "success", **report)
        print(f"[candidate_prices] {report}")
        return 0
    from gen_report import save
    print(save("discovery_timing", render()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
