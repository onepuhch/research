"""Screen US-listed stocks for sustained upward EPS estimate revisions.

Yahoo reports each estimate's value today and 7/30/60/90 days ago. Those
provider-reported past values rank candidates on day one; they are stored in
the screen snapshot only and never written to metric_log as our own past
observations.

Every ticker in every stage ends as success, unavailable (a valid answer with
too little data), failed (a technical error after retries) or not_attempted
(time budget or a blocked stage). The run status is derived from those counts,
so an incomplete run is never reported as a clean success.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import http.client
import http.cookiejar
import json
import math
import os
import random
import re
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import HTTPCookieProcessor, Request, build_opener

import common as c
import market_calendar

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126 Safari/537.36"}
SEC_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
YAHOO = "https://query2.finance.yahoo.com"
EXCHANGES = {"Nasdaq", "NYSE"}
SCREEN_DIR = c.DATA_DIR / "revision_screen"
DOC_PATH = c.ROOT / "docs" / "revision_screen.md"
SCHEMA_VERSION = 2
KST = timezone(timedelta(hours=9))
RETRYABLE = {429, 500, 502, 503, 504}
OUTCOMES = ("success", "unavailable", "failed", "not_attempted")
PRICE_BASIS = "Yahoo chart close: split-adjusted, not dividend-adjusted"
DEFAULTS = {
    "min_market_cap_usd": 300_000_000, "min_analysts": 3, "top_n": 20,
    "min_yield_change_pp": 1.0, "min_growth_pct": 25.0, "min_growth_base_eps": 0.25,
    # Pacing: ~4 requests/s finishes ~3,300 lookups in ~14 min. A run at ~32/s
    # (2026-09-25) lost 10% of lookups and every profile/price call.
    "workers": 3, "min_interval_s": 0.25, "max_interval_s": 1.0,
    "max_attempts": 3, "retry_waits_s": [2, 8], "retry_cooldown_s": 30,
    "time_budget_s": 1500, "failure_alert_rate": 0.02,
    # A 90-day price comparison needs closes at most this stale.
    "price_end_max_lag_sessions": 1, "price_start_max_gap_days": 7,
}


def settings() -> dict:
    return {**DEFAULTS, **c.policy().get("revision_screen", {})}


# ---------------------------------------------------------------- HTTP layer

class FetchError(Exception):
    """kind: failed | unavailable | blocked | budget. Holds no URL or body text."""

    def __init__(self, kind: str, reason: str, http_status: int | None = None, attempts: int = 0):
        super().__init__(f"{kind}:{reason}")
        self.kind, self.reason, self.http_status, self.attempts = kind, reason, http_status, attempts


class RealClock:
    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


class Pacer:
    """Spaces request starts across all threads; 429 widens the spacing."""

    def __init__(self, clock, interval: float, max_interval: float):
        self.clock, self.interval, self.max_interval = clock, interval, max_interval
        self.next_start = 0.0
        self.lock = threading.Lock()

    def wait(self) -> None:
        with self.lock:
            now = self.clock.now()
            start = max(now, self.next_start)
            self.next_start = start + self.interval
        self.clock.sleep(start - now)

    def back_off(self, pause: float) -> None:
        with self.lock:
            self.interval = min(self.max_interval, max(self.interval * 1.5, self.interval + 0.1))
            self.next_start = max(self.next_start, self.clock.now() + pause)


class IncompleteResponse(OSError):
    """An http.client protocol error (e.g. IncompleteRead), surfaced as a network failure."""


def urllib_transport(opener):
    """Return (status, body, headers); raise OSError (incl. timeouts) on network failure."""
    def send(url: str, headers: dict, timeout: float = 20.0) -> tuple[int, bytes, dict]:
        try:
            with opener.open(Request(url, headers=headers), timeout=timeout) as response:
                return response.status, response.read(5_000_001), dict(response.headers)
        except HTTPError as error:
            try:
                return error.code, error.read(5_000_001), dict(error.headers or {})
            except http.client.HTTPException as read_error:
                raise IncompleteResponse(type(read_error).__name__) from None
        except http.client.HTTPException as error:
            raise IncompleteResponse(type(error).__name__) from None
    return send


class Yahoo:
    def __init__(self, cfg: dict, clock=None, transport=None, jitter=random.random):
        self.cfg, self.clock, self.jitter = cfg, clock or RealClock(), jitter
        self.transport = transport or urllib_transport(build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar())))
        self.pacer = Pacer(self.clock, cfg["min_interval_s"], cfg["max_interval_s"])
        self.deadline = self.clock.now() + cfg["time_budget_s"]
        self.session_lock = threading.Lock()
        self.session_generation = 0
        self.crumb = ""
        self.local = threading.local()
        self.refresh_session(0)

    def take_attempts(self) -> int:
        """Requests sent by this thread since the last call; resets the count."""
        count = getattr(self.local, "attempts", 0)
        self.local.attempts = 0
        return count

    def remaining(self) -> float:
        return self.deadline - self.clock.now()

    def refresh_session(self, seen_generation: int) -> None:
        """Only one thread refreshes; others that saw the same generation reuse it."""
        with self.session_lock:
            if self.session_generation != seen_generation:
                return
            self.crumb = self.find_crumb()
            self.session_generation += 1

    def timeout(self) -> float:
        """Per-request timeout that never runs past the time budget."""
        remaining = self.remaining()
        if remaining <= 0:
            raise FetchError("budget", "time_budget")
        return max(1.0, min(20.0, remaining))

    def find_crumb(self) -> str:
        try:
            self.transport("https://fc.yahoo.com", UA, self.timeout())  # Sets the session cookie, even on 404.
        except OSError:
            pass
        for host in ("query2", "query1"):
            try:
                status, body, _ = self.transport(f"https://{host}.finance.yahoo.com/v1/test/getcrumb", UA,
                                                 self.timeout())
            except OSError:
                continue
            crumb = body.decode("utf-8", "replace").strip()
            if status == 200 and crumb and len(crumb) <= 40 and "<" not in crumb:
                return crumb
        # Cloud runners are sometimes refused by getcrumb; the quote page embeds one.
        try:
            status, body, _ = self.transport("https://finance.yahoo.com/quote/AAPL/", UA, self.timeout())
        except OSError as error:
            raise FetchError("blocked", "session_" + type(error).__name__) from None
        match = re.search(r'"crumb":"([^"]{5,40})"', body.decode("utf-8", "replace")) if status == 200 else None
        if not match:
            raise FetchError("blocked", "session_crumb_unavailable", status)
        return match.group(1).encode().decode("unicode_escape")

    def get_json(self, path: str) -> dict:
        """GET a Yahoo API path with pacing, bounded retry and one session refresh."""
        attempts, refreshed = 0, False
        while True:
            if self.remaining() <= 0:
                raise FetchError("budget", "time_budget", attempts=attempts)
            generation = self.session_generation
            self.pacer.wait()
            if self.remaining() <= 0:  # The wait itself can use up the budget; send nothing.
                raise FetchError("budget", "time_budget", attempts=attempts)
            attempts += 1
            self.local.attempts = getattr(self.local, "attempts", 0) + 1
            sep = "&" if "?" in path else "?"
            try:
                status, body, headers = self.transport(f"{YAHOO}{path}{sep}crumb={quote(self.crumb)}", UA,
                                                       self.timeout())
                network_error = ""
            except (OSError, http.client.HTTPException) as error:
                status, body, headers, network_error = None, b"", {}, type(error).__name__
            if status == 200:
                try:
                    return json.loads(body.decode("utf-8"))
                except ValueError:
                    raise FetchError("failed", "bad_json", 200, attempts) from None
            if status in (401, 403):
                if refreshed:
                    raise FetchError("blocked", "http_forbidden", status, attempts)
                refreshed = True
                self.refresh_session(generation)
                continue
            if status == 404:
                raise FetchError("unavailable", "not_found", 404, attempts)
            if (status is None or status in RETRYABLE) and attempts < self.cfg["max_attempts"]:
                waits = self.cfg["retry_waits_s"]
                wait = waits[min(attempts - 1, len(waits) - 1)] + self.jitter()
                if status == 429:
                    retry_after = _retry_after(headers)
                    if retry_after is not None:
                        wait = max(wait, retry_after)
                    if wait >= self.remaining():
                        raise FetchError("budget", "time_budget", status, attempts)
                    self.pacer.back_off(wait)
                elif wait < self.remaining():
                    self.clock.sleep(wait)
                else:
                    raise FetchError("budget", "time_budget", status, attempts)
                continue
            raise FetchError("failed", network_error or f"http_{status}", status, attempts)

    def summary(self, symbol: str, modules: str) -> dict:
        data = self.get_json(f"/v10/finance/quoteSummary/{quote(symbol)}?modules={modules}")
        block = data.get("quoteSummary") or {}
        error = block.get("error")
        if error:
            kind = "unavailable" if (error.get("code") or "").lower() == "not found" else "failed"
            raise FetchError(kind, "api_error", 200)
        results = block.get("result") or []
        if not results:
            raise FetchError("unavailable", "empty_result", 200)
        return results[0]

    def quotes(self, symbols: list[str]) -> list[dict]:
        fields = "marketCap,epsForward,quoteType,currency,regularMarketPrice,shortName,longName"
        data = self.get_json(f"/v7/finance/quote?symbols={','.join(quote(s) for s in symbols)}&fields={fields}")
        block = data.get("quoteResponse") or {}
        if block.get("error"):
            raise FetchError("failed", "api_error", 200)
        return block.get("result") or []

    def chart(self, symbol: str) -> dict:
        data = self.get_json(f"/v8/finance/chart/{quote(symbol)}?range=6mo&interval=1d&events=split")
        block = data.get("chart") or {}
        error = block.get("error")
        if error:
            kind = "unavailable" if (error.get("code") or "").lower() == "not found" else "failed"
            raise FetchError(kind, "api_error", 200)
        results = block.get("result") or []
        if not results:
            raise FetchError("unavailable", "empty_result", 200)
        return results[0]


def _retry_after(headers: dict) -> float | None:
    for key, value in (headers or {}).items():
        if key.lower() == "retry-after":
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
    return None


# --------------------------------------------------------------- stage runner

def outcome(status: str, value=None, reason: str = "", http_status=None, attempts: int = 0) -> dict:
    return {"status": status, "value": value, "reason": reason, "http_status": http_status, "attempts": attempts}


def run_stage(items: list[str], fetch, workers: int, yahoo: Yahoo, cooldown: float) -> dict[str, dict]:
    """Run fetch over items; retry only the failed ones once more after a cooldown.

    max_attempts applies per pass, so a failed item is sent at most
    2 x max_attempts times. The time budget overrides both passes.

    A blocked response (403 after a session refresh) stops the stage and marks
    the rest not_attempted, so a banned session does not burn the budget.
    """
    blocked = threading.Event()

    def one(item: str, prior_attempts: int = 0) -> tuple[str, dict]:
        if blocked.is_set():
            return item, outcome("not_attempted", reason="stage_blocked", attempts=prior_attempts)
        if yahoo.remaining() <= 0:
            return item, outcome("not_attempted", reason="time_budget", attempts=prior_attempts)
        yahoo.take_attempts()
        try:
            value = fetch(item)
            return item, outcome("success", value, attempts=prior_attempts + yahoo.take_attempts())
        except FetchError as error:
            # Validation after a response raises with attempts=0; the thread count keeps real sends.
            sent = max(error.attempts, yahoo.take_attempts())
            attempts = prior_attempts + sent
            if error.kind == "blocked":
                blocked.set()
                return item, outcome("failed", reason=error.reason, http_status=error.http_status, attempts=attempts)
            if error.kind == "budget":
                return item, outcome("not_attempted" if sent == 0 else "failed", reason="time_budget",
                                     http_status=error.http_status, attempts=attempts)
            return item, outcome(error.kind, reason=error.reason, http_status=error.http_status, attempts=attempts)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        results = dict(pool.map(one, items))
    retry = [item for item, o in results.items() if o["status"] == "failed" and not blocked.is_set()]
    if retry and yahoo.remaining() > cooldown:
        yahoo.clock.sleep(cooldown)
        for item in retry:
            again = one(item, results[item]["attempts"])[1]
            if again["status"] != "not_attempted":  # An item that already failed stays failed.
                results[item] = again
    return results


def stage_stats(results: dict[str, dict]) -> dict:
    stats = {"requested": len(results), **{k: 0 for k in OUTCOMES}}
    for o in results.values():
        stats[o["status"]] += 1
    return stats


# ------------------------------------------------------- validation & scoring

def raw(value):
    return value.get("raw") if isinstance(value, dict) else value


def finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def extract_source(summary: dict, retrieved_at: str) -> dict:
    """The fields scoring needs, kept verbatim so a snapshot can be rescored."""
    price = summary.get("price") or {}
    periods = {}
    for row in (summary.get("earningsTrend") or {}).get("trend", []):
        if row.get("period") not in ("0y", "+1y"):
            continue
        eps = {k: raw(v) for k, v in (row.get("epsTrend") or {}).items()}
        rev = {k: raw(v) for k, v in (row.get("epsRevisions") or {}).items()}
        est = row.get("earningsEstimate") or {}
        periods[row["period"]] = {
            "end": row.get("endDate"), "analysts": raw(est.get("numberOfAnalysts")),
            "estimate_currency": est.get("earningsCurrency"),
            "current": eps.get("current"), "d7": eps.get("7daysAgo"), "d30": eps.get("30daysAgo"),
            "d60": eps.get("60daysAgo"), "d90": eps.get("90daysAgo"), "currency": eps.get("epsTrendCurrency"),
            "up30": rev.get("upLast30days"), "down30": rev.get("downLast30days")}
    return {"symbol": price.get("symbol"), "price": raw(price.get("regularMarketPrice")),
            "price_currency": price.get("currency"), "price_time": raw(price.get("regularMarketTime")),
            "retrieved_at": retrieved_at, "periods": periods}


def evaluate(symbol: str, source: dict, cfg: dict) -> tuple[dict | None, str]:
    """Validate one ticker's next-fiscal-year estimate and score it.

    Returns (row, "") or (None, exclusion reason). Thresholds use unrounded
    values; stored numbers are rounded for display only.
    """
    if source.get("symbol") != symbol:
        return None, "ticker_mismatch"
    price = source.get("price")
    if not finite(price) or price <= 0:
        return None, "price_invalid"
    if source.get("price_currency") != "USD":
        return None, "price_currency"
    row = (source.get("periods") or {}).get("+1y")
    if not row:
        return None, "no_next_fiscal_year"
    try:
        date.fromisoformat(str(row.get("end")))
    except ValueError:
        return None, "period_missing"
    if row.get("currency") is None:
        return None, "eps_currency_missing"
    if row.get("currency") != "USD" or row.get("estimate_currency") not in (None, "USD"):
        return None, "eps_currency_mismatch"
    analysts = row.get("analysts")
    if not finite(analysts) or analysts < cfg["min_analysts"]:
        return None, "analysts_below_min"
    cur, d30, d90 = row.get("current"), row.get("d30"), row.get("d90")
    if any(v is None for v in (cur, d30, d90)):
        return None, "estimate_missing"
    if not all(finite(v) for v in (cur, d30, d90)):
        return None, "estimate_not_finite"
    if d90 == 0 or d30 == 0:
        # Cannot tell a provider blank from a true zero; exclude rather than guess.
        return None, "past_estimate_zero"
    d7, d60 = row.get("d7"), row.get("d60")
    up30, down30 = row.get("up30") or 0, row.get("down30") or 0
    yield90, yield30 = (cur - d90) / price * 100, (cur - d30) / price * 100
    pct90 = (cur - d90) / d90 * 100 if d90 >= 0.05 else None
    chain = [v for v in (d90, d60, d30, d7, cur) if finite(v)]
    rising = cur > 0 and cur > d30 and up30 > down30
    by_yield = rising and yield90 >= cfg["min_yield_change_pp"]
    by_growth = (rising and d90 >= cfg["min_growth_base_eps"] and pct90 is not None
                 and pct90 >= cfg["min_growth_pct"])
    return {
        "eps_target_period": row["end"], "eps_currency": "USD", "eps_basis": "provider-unspecified",
        "provider_history": True, "eps_retrieved_at": source.get("retrieved_at"),
        "analysts": int(analysts), "price": price, "price_time": source.get("price_time"),
        "eps_now": cur, "eps_30d": d30, "eps_90d": d90,
        "yield_change_90_pp": round(yield90, 3), "yield_change_30_pp": round(yield30, 3),
        "pct_90": round(pct90, 1) if pct90 is not None else None,
        "turnaround": d90 < 0 < cur, "up30": up30, "down30": down30,
        "steady": cur > d90 and all(a <= b for a, b in zip(chain, chain[1:])),
        "by_yield": by_yield, "by_growth": by_growth, "candidate": by_yield or by_growth,
    }, ""


def last_completed_session(as_of: datetime) -> date:
    """Most recent NYSE session whose close was at least an hour before as_of."""
    day = as_of.date()
    for _ in range(15):
        closed = market_calendar.close_time(day)
        if closed is not None and closed + timedelta(hours=1) <= as_of:
            return day
        day -= timedelta(days=1)
    raise ValueError("no completed session in 15 days")


def sessions_between(after: date, through: date) -> int:
    """Trading sessions in (after, through]; holidays and weekends do not count."""
    count, day = 0, after + timedelta(days=1)
    while day <= through:
        if market_calendar.close_time(day) is not None:
            count += 1
        day += timedelta(days=1)
    return count


def price_comparison(chart: dict, symbol: str, eps_now: float, eps_90d: float, as_of: float,
                     cfg: dict | None = None, days: int = 90) -> dict:
    """Price move over the same window as the provider's 90-day estimate change.

    Uses only completed sessions (close + 1 hour before as_of) from one chart
    response on one basis, and records the target and chosen dates. The
    dividend-adjusted return is separate. P/E change is left out across a
    split, because the provider's past estimate may be on another share basis.

    price_status: success (price_pct_90 computed), unavailable (a valid answer
    without comparable data: short history, stale or missing closes,
    unsupported calendar) or failed (wrong ticker/currency, malformed arrays).
    """
    cfg = {**DEFAULTS, **(cfg or {})}
    result = {"price_status": "unavailable", "price_note": "", "price_basis": PRICE_BASIS,
              "price_start_target": None, "price_start_date": None, "price_end_expected": None,
              "price_end_date": None, "close_start": None, "close_end": None,
              "price_pct_90": None, "adj_return_pct_90": None, "pe_change_pct": None}
    meta = chart.get("meta") or {}
    if meta.get("symbol") != symbol or meta.get("currency") != "USD":
        return {**result, "price_status": "failed", "price_note": "chart_mismatch"}
    stamps = chart.get("timestamp") or []
    indicators = chart.get("indicators") or {}
    closes = ((indicators.get("quote") or [{}])[0] or {}).get("close")
    adj = ((indicators.get("adjclose") or [{}])[0] or {}).get("adjclose")
    if closes is None and not stamps:
        return {**result, "price_note": "no_prices"}
    if (not isinstance(closes, list) or len(closes) != len(stamps)
            or (adj is not None and (not isinstance(adj, list) or len(adj) != len(stamps)))
            or not all(finite(t) for t in stamps)
            or any(b <= a for a, b in zip(stamps, stamps[1:]))):
        return {**result, "price_status": "failed", "price_note": "malformed_series"}
    as_of_dt = datetime.fromtimestamp(as_of, timezone.utc)
    try:
        expected = last_completed_session(as_of_dt)
        points = []
        for i, stamp in enumerate(stamps):
            day = datetime.fromtimestamp(stamp, timezone.utc).date()
            closed = market_calendar.close_time(day)
            if closed is None or closed + timedelta(hours=1) > as_of_dt:
                continue  # A closed-market bar, or a session not yet settled, is not a close.
            if finite(closes[i]) and closes[i] > 0:
                adjusted = adj[i] if adj is not None and finite(adj[i]) and adj[i] > 0 else None
                points.append((day, closes[i], adjusted))
    except ValueError:
        return {**result, "price_note": "calendar_unsupported"}
    target = as_of_dt.date() - timedelta(days=days)
    result.update(price_start_target=target.isoformat(), price_end_expected=expected.isoformat())
    if not points:
        return {**result, "price_note": "no_prices"}
    end = points[-1]
    if sessions_between(end[0], expected) > cfg["price_end_max_lag_sessions"]:
        return {**result, "price_end_date": end[0].isoformat(), "price_note": "stale_end_price"}
    starts = [pt for pt in points if pt[0] <= target]
    if not starts:
        return {**result, "price_end_date": end[0].isoformat(), "price_note": "window_not_covered"}
    start = starts[-1]
    if (target - start[0]).days > cfg["price_start_max_gap_days"]:
        return {**result, "price_start_date": start[0].isoformat(), "price_end_date": end[0].isoformat(),
                "price_note": "stale_start_price"}
    splits = [x for x in ((chart.get("events") or {}).get("splits") or {}).values() if finite(x.get("date"))]
    split_days = [datetime.fromtimestamp(x["date"], timezone.utc).date() for x in splits]
    result.update(price_status="success", price_start_date=start[0].isoformat(),
                  price_end_date=end[0].isoformat(), close_start=start[1], close_end=end[1],
                  price_pct_90=round((end[1] / start[1] - 1) * 100, 1))
    if start[2] is not None and end[2] is not None:
        result["adj_return_pct_90"] = round((end[2] / start[2] - 1) * 100, 1)
    if any(start[0] < d <= end[0] for d in split_days):
        result["price_note"] = "split_in_window"
    elif eps_now > 0 and eps_90d > 0:
        result["pe_change_pct"] = round(((end[1] / start[1]) / (eps_now / eps_90d) - 1) * 100, 1)
    return result


def industry_clusters(candidates: list[dict], minimum: int = 3) -> list[dict]:
    """Industries where several companies are being revised up at once."""
    groups: dict[str, list[dict]] = {}
    for r in candidates:
        if r.get("industry"):
            groups.setdefault(r["industry"], []).append(r)
    return sorted(({"industry": k, "count": len(v), "tickers": [r["ticker"] for r in v]}
                   for k, v in groups.items() if len(v) >= minimum), key=lambda g: g["count"], reverse=True)


def rank(rows: list[dict], top_n: int) -> tuple[list[dict], list[dict]]:
    candidates = [r for r in rows if r["candidate"]]
    top_yield = sorted((r for r in candidates if r["by_yield"]),
                       key=lambda r: r["yield_change_90_pp"], reverse=True)[:top_n]
    top_growth = sorted((r for r in candidates if r["by_growth"]), key=lambda r: r["pct_90"], reverse=True)[:top_n]
    return top_yield, top_growth


def run_status(stages: dict[str, dict]) -> str:
    """failed: a core input is missing entirely. degraded: any technical gap."""
    for core in ("universe", "session"):
        if stages.get(core, {}).get("success", 0) == 0:
            return "failed"
    if stages.get("earnings", {}).get("success", 0) == 0:
        return "failed"
    gaps = sum(s.get("failed", 0) + s.get("not_attempted", 0) for s in stages.values())
    return "degraded" if gaps else "success"


# ------------------------------------------------------------------ rendering

def fmt_cap(value) -> str:
    if not finite(value):
        return "-"
    return f"${value / 1e9:.1f}B" if value >= 1e9 else f"${value / 1e6:.0f}M"


def change_label(r: dict) -> str:
    if r.get("pct_90") is not None:
        return f"{r['pct_90']:+.0f}%"
    if r.get("turnaround") or r.get("eps_90d", 0) < 0:
        return "적자→흑자"
    return "기저 작음"


def render_table(rows: list[dict]) -> list[str]:
    lines = ["|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        price = f"{r['price_pct_90']:+.0f}%" if r.get("price_pct_90") is not None else "미확인"
        pe = f"{r['pe_change_pct']:+.0f}%" if r.get("pe_change_pct") is not None else "미산출"
        lines.append(f"|{i}|{r['ticker']}|{r.get('industry') or '미확인'}|{fmt_cap(r.get('market_cap'))}|"
                     f"${r['eps_90d']:.2f} → ${r['eps_now']:.2f}|{change_label(r)}|{r['yield_change_90_pp']:+.2f}%p|"
                     f"{r['up30']}/{r['down30']}|{price}|{pe}|{'예' if r['steady'] else '-'}|")
    return lines


STAGE_NAMES = {"universe": "상장 목록(SEC)", "session": "Yahoo 접속", "quotes": "시세 일괄 조회",
               "earnings": "EPS 예상치", "profile": "업종(후보)", "price": "주가 비교(상위)"}
STATUS_KO = {"success": "정상", "degraded": "일부 누락", "failed": "실패", "legacy": "구버전 기록"}


def render_doc(latest: dict, shown: dict, shown_path: str, last_success: str | None) -> str:
    """latest: newest attempt. shown: newest snapshot with usable rows (may equal latest)."""
    run = latest["run"]
    lines = ["# 이익 예상치 상향 스크리너", "",
             f"최신 시도: {run['started_kst']} KST · 상태 **{STATUS_KO.get(run['status'], run['status'])}**"
             + (f" · 마지막 완전 정상 결과: {last_success} KST" if last_success else " · 완전 정상 결과 없음"), ""]
    if shown is not latest:
        lines += [f"> 최신 시도는 결과를 만들지 못했다. 아래는 {shown['run']['started_kst']} KST 시도"
                  f"({STATUS_KO.get(shown['run']['status'], shown['run']['status'])})의 결과이며 오늘의 정상 결과가 아니다.", ""]
    stages = latest.get("stages") or {}
    if stages:
        lines += ["|단계|요청|정상|자료 부족|실패|미시도|", "|---|---|---|---|---|---|"]
        lines += [f"|{STAGE_NAMES.get(k, k)}|{s['requested']}|{s['success']}|{s['unavailable']}|{s['failed']}|{s['not_attempted']}|"
                  for k, s in stages.items()]
        lines += [""]
        if run["status"] != "success":
            lines += ["> 실패·미시도가 있는 단계의 종목은 이번 순위에서 빠졌거나 업종·주가가 미확인이다. 빠진 종목이 없다는 뜻이 아니다.", ""]
    derived = shown.get("derived") or {}
    rows = {r["ticker"]: r for r in derived.get("rows", [])}
    top_yield = [rows[t] for t in derived.get("top_yield", []) if t in rows]
    top_growth = [rows[t] for t in derived.get("top_growth", []) if t in rows]
    lines += [
        "증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.", "",
        "- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.",
        "- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.",
        f"- **주가 90일**은 같은 기간 정규장 종가 변화({PRICE_BASIS})다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.",
        "- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.",
        "- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.", ""]
    clusters = derived.get("clusters") or []
    profile = (shown.get("stages") or {}).get("profile")
    if clusters:
        lines += ["## 여러 회사가 동시에 상향되는 업종", "",
                  "같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.", ""]
        lines += [f"- **{g['industry']}** {g['count']}곳: {', '.join(g['tickers'])}" for g in clusters]
        lines += [""]
    if profile and profile["success"] < profile["requested"]:
        lines += [f"> 업종 확인 {profile['success']}/{profile['requested']}곳. 업종이 미확인인 후보는 묶음 판단에서 빠졌다.", ""]
    lines += ["## A. 이익 규모 대비 상향", ""] + render_table(top_yield)
    lines += ["", "## B. 성장률 상향", ""] + render_table(top_growth)
    lines += ["", f"전체 결과: `{shown_path}`", ""]
    return "\n".join(lines)


# ------------------------------------------------------------------ snapshots

def write_gz(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def load_snapshot(path: Path) -> dict:
    """Read a snapshot; schema 1 (date-named, 2026-09-25) is normalized to schema 2."""
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("schema_version") == SCHEMA_VERSION:
        return data
    meta = data.get("meta") or {}
    return {"schema_version": 1, "run": {"status": "legacy", "started_kst": meta.get("generated_kst", path.stem)},
            "stages": {}, "derived": {"rows": data.get("rows", []), "top_yield": data.get("top_yield", []),
                                      "top_growth": data.get("top_growth", []), "clusters": data.get("clusters", [])}}


def snapshot_key(path: Path) -> str:
    """Schema 2 names start with a UTC timestamp; schema 1 names are a KST date."""
    name = path.name
    if re.match(r"\d{4}-\d{2}-\d{2}\.json\.gz$", name):
        return name[:10].replace("-", "") + "T000000Z"
    return name[:16]


def snapshots() -> list[Path]:
    return sorted(SCREEN_DIR.glob("*.json.gz"), key=snapshot_key)


def code_version() -> str:
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"][:12]
    try:
        return subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=c.ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def publish(snapshot: dict, path: Path) -> None:
    """Write the latest document from the newest attempt and the newest usable result."""
    history = [(p, load_snapshot(p)) for p in snapshots()]
    usable = [(p, s) for p, s in history if s["run"]["status"] != "failed" and s["derived"]["rows"]]
    shown_path, shown = usable[-1] if usable else (path, snapshot)
    if shown_path == path:
        shown = snapshot
    success = [s["run"]["started_kst"] for _, s in history if s["run"]["status"] == "success"]
    rel = shown_path.relative_to(c.ROOT).as_posix() if shown_path.is_relative_to(c.ROOT) else shown_path.name
    DOC_PATH.write_text(render_doc(snapshot, shown, rel, success[-1] if success else None), encoding="utf-8")


# ----------------------------------------------------------------------- main

UNIVERSE_SOURCE: dict = {}


def load_universe(transport, user_agent: str) -> list[dict]:
    status, body, _ = transport(SEC_URL, {"User-Agent": user_agent})
    if status != 200:
        raise FetchError("failed", f"http_{status}", status, 1)
    payload = json.loads(body.decode("utf-8"))
    index = {name: i for i, name in enumerate(payload["fields"])}
    UNIVERSE_SOURCE.update(url=SEC_URL, sha256=hashlib.sha256(body).hexdigest(),
                           observed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    seen, rows = set(), []
    for item in payload["data"]:
        ticker, exchange = item[index["ticker"]], item[index["exchange"]]
        if exchange not in EXCHANGES or not ticker or ticker in seen:
            continue
        seen.add(ticker)
        cik = item[index["cik"]] if "cik" in index else None
        rows.append({"ticker": ticker, "symbol": ticker.replace(".", "-"), "name": item[index["name"]],
                     "exchange": exchange, "cik": f"{int(cik):010d}" if isinstance(cik, int) or str(cik).isdigit() else None})
    return rows


def issuers_path() -> Path:
    return c.DATA_DIR / "sec_issuers.json.gz"


def store_issuers(universe: list[dict], source: dict) -> bool:
    """Official ticker -> CIK/exchange list as read from SEC, kept for snapshots without CIKs.
    Rewritten only when the SEC file changed."""
    path = issuers_path()
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            if json.load(handle).get("source", {}).get("sha256") == source.get("sha256"):
                return False
    record = {"source": source, "issuers": {r["ticker"]: {"cik": r["cik"], "exchange": r["exchange"], "name": r["name"]}
                                            for r in universe if r.get("cik")}}
    write_gz(path, record)
    return True


def eligibility(q: dict, cfg: dict) -> str:
    if q.get("quoteType") != "EQUITY":
        return "not_equity"
    if q.get("currency") != "USD":
        return "not_usd"
    if not finite(q.get("marketCap")) or q["marketCap"] < cfg["min_market_cap_usd"]:
        return "market_cap_below_min"
    if q.get("epsForward") is None:
        return "no_eps_estimate"
    if not finite(q.get("regularMarketPrice")) or q["regularMarketPrice"] <= 0:
        return "price_invalid"
    return ""


def screen(cfg: dict, universe: list[dict], yahoo: Yahoo) -> dict:
    """Run the Yahoo stages over a known universe. Returns snapshot parts."""
    stages, issues, exclusions, source = {}, [], {}, {"earnings": {}, "profile": {}, "price": {}}
    by_symbol = {row["symbol"]: row for row in universe}
    symbols = list(by_symbol)

    batches = [symbols[i:i + 100] for i in range(0, len(symbols), 100)]
    batch_results = run_stage([",".join(b) for b in batches], lambda key: yahoo.quotes(key.split(",")),
                              cfg["workers"], yahoo, cfg["retry_cooldown_s"])
    quote_results, quotes = {}, {}
    for key, o in batch_results.items():
        returned = {q.get("symbol"): q for q in (o["value"] or [])} if o["status"] == "success" else {}
        for symbol in key.split(","):
            if o["status"] != "success":
                quote_results[symbol] = {**o, "value": None}
            elif symbol in returned:
                quote_results[symbol] = outcome("success", attempts=o["attempts"])
                quotes[symbol] = returned[symbol]
            else:
                quote_results[symbol] = outcome("unavailable", reason="not_returned", attempts=o["attempts"])
    stages["quotes"] = stage_stats(quote_results)

    eligible = []
    for symbol, q in quotes.items():
        reason = eligibility(q, cfg)
        if reason:
            exclusions[reason] = exclusions.get(reason, 0) + 1
        else:
            eligible.append(symbol)

    def fetch_earnings(symbol: str) -> dict:
        retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return extract_source(yahoo.summary(symbol, "earningsTrend,price"), retrieved)

    earn = run_stage(eligible, fetch_earnings, cfg["workers"], yahoo, cfg["retry_cooldown_s"])
    rows = []
    for symbol, o in earn.items():
        if o["status"] != "success":
            continue
        source["earnings"][symbol] = o["value"]
        row, reason = evaluate(symbol, o["value"], cfg)
        if row is None:
            exclusions[reason] = exclusions.get(reason, 0) + 1
            earn[symbol] = {**o, "status": "unavailable", "reason": reason}
            continue
        q = quotes[symbol]
        rows.append({"ticker": by_symbol[symbol]["ticker"], "symbol": symbol,
                     "name": q.get("longName") or q.get("shortName") or by_symbol[symbol]["name"],
                     "exchange": by_symbol[symbol].get("exchange"), "cik": by_symbol[symbol].get("cik"),
                     "market_cap": q.get("marketCap"), **row})
    stages["earnings"] = stage_stats(earn)

    candidates = [r for r in rows if r["candidate"]]
    by_sym = {r["symbol"]: r for r in rows}

    def fetch_profile(symbol: str) -> dict:
        p = yahoo.summary(symbol, "assetProfile").get("assetProfile") or {}
        if not p.get("industry"):
            raise FetchError("unavailable", "profile_missing", 200)
        return {"industry": p.get("industry"), "sector": p.get("sector"),
                "summary": (p.get("longBusinessSummary") or "")[:600]}

    prof = run_stage([r["symbol"] for r in candidates], fetch_profile, cfg["workers"], yahoo, cfg["retry_cooldown_s"])
    for symbol, o in prof.items():
        if o["status"] == "success":
            source["profile"][symbol] = o["value"]
            by_sym[symbol].update(o["value"])
    stages["profile"] = stage_stats(prof)

    top_yield, top_growth = rank(rows, cfg["top_n"])
    top = list(dict.fromkeys(r["symbol"] for r in top_yield + top_growth))
    price = run_stage(top, yahoo.chart, cfg["workers"], yahoo, cfg["retry_cooldown_s"])
    for symbol, o in price.items():
        r = by_sym[symbol]
        if o["status"] == "success":
            as_of = datetime.fromisoformat(r["eps_retrieved_at"]).timestamp()
            comparison = price_comparison(o["value"], symbol, r["eps_now"], r["eps_90d"], as_of, cfg)
            source["price"][symbol] = {k: comparison.get(k) for k in (
                "price_status", "price_note", "price_start_target", "price_start_date", "price_end_expected",
                "price_end_date", "close_start", "close_end")}
            r.update(comparison)
            if comparison["price_status"] != "success":
                # A 200 response is not a comparison; count only what could be compared.
                price[symbol] = {**o, "status": comparison["price_status"], "reason": comparison["price_note"]}
    stages["price"] = stage_stats(price)

    for name, results in (("quotes", quote_results), ("earnings", earn), ("profile", prof), ("price", price)):
        for item, o in results.items():
            if o["status"] in ("failed", "not_attempted"):
                issues.append({"stage": name, "ticker": item, "status": o["status"], "reason": o["reason"],
                               "http_status": o["http_status"], "attempts": o["attempts"]})
    return {"stages": stages, "issues": issues, "exclusions": exclusions, "source": source,
            "derived": {"rows": rows, "top_yield": [r["ticker"] for r in top_yield],
                        "top_growth": [r["ticker"] for r in top_growth],
                        "clusters": industry_clusters(candidates)}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tickers", help="comma-separated probe list; skips the SEC universe and saves nothing")
    parser.add_argument("--no-save", action="store_true", help="print a summary; write no files or run status")
    args = parser.parse_args(argv)
    args.no_save = args.no_save or bool(args.tickers)  # A probe must never become the published result.
    cfg = settings()
    started = datetime.now(timezone.utc)
    run_id = (f"{os.environ['GITHUB_RUN_ID']}-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}"
              if os.environ.get("GITHUB_RUN_ID") else f"local-{uuid.uuid4().hex[:8]}")
    stages, parts, universe = {}, {}, []
    try:
        if args.tickers:
            universe = [{"ticker": t.strip(), "symbol": t.strip().replace(".", "-"), "name": t.strip()}
                        for t in args.tickers.split(",") if t.strip()]
            stages["universe"] = {"requested": len(universe), "success": len(universe), "unavailable": 0,
                                  "failed": 0, "not_attempted": 0}
        else:
            sec = urllib_transport(build_opener())
            universe = load_universe(sec, os.environ.get("SEC_USER_AGENT") or "investment-research-system/2.0 research-bot")
            stages["universe"] = {"requested": 1, "success": 1, "unavailable": 0, "failed": 0, "not_attempted": 0}
    except (OSError, TimeoutError, ValueError, KeyError, FetchError) as error:
        stages["universe"] = {"requested": 1, "success": 0, "unavailable": 0, "failed": 1, "not_attempted": 0}
        parts["issues"] = [{"stage": "universe", "ticker": "", "status": "failed",
                            "reason": getattr(error, "reason", type(error).__name__),
                            "http_status": getattr(error, "http_status", None), "attempts": 1}]
    if stages["universe"]["success"]:
        try:
            yahoo = Yahoo(cfg)
            stages["session"] = {"requested": 1, "success": 1, "unavailable": 0, "failed": 0, "not_attempted": 0}
            parts = screen(cfg, universe, yahoo)
            stages.update(parts.pop("stages"))
        except FetchError as error:
            stages["session"] = {"requested": 1, "success": 0, "unavailable": 0, "failed": 1, "not_attempted": 0}
            parts["issues"] = [{"stage": "session", "ticker": "", "status": "failed", "reason": error.reason,
                                "http_status": error.http_status, "attempts": error.attempts}]

    status = run_status(stages)
    lookups = sum(s["requested"] for k, s in stages.items() if k not in ("universe", "session"))
    failed = sum(s["failed"] + s["not_attempted"] for k, s in stages.items() if k not in ("universe", "session"))
    finished = datetime.now(timezone.utc)
    derived = parts.get("derived") or {"rows": [], "top_yield": [], "top_growth": [], "clusters": []}
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "run": {"run_id": run_id, "code_version": code_version(), "status": status,
                "alert": bool(lookups) and failed / lookups > cfg["failure_alert_rate"],
                "started_at": started.isoformat(timespec="seconds"), "finished_at": finished.isoformat(timespec="seconds"),
                "started_kst": started.astimezone(KST).strftime("%Y-%m-%d %H:%M"), "config": cfg,
                "universe_size": len(universe),
                "source": "SEC company_tickers_exchange; Yahoo Finance quote, quoteSummary(earningsTrend,price,assetProfile), chart"},
        "stages": stages, "exclusions": parts.get("exclusions", {}), "issues": parts.get("issues", []),
        "derived": derived, "source": parts.get("source", {}),
    }
    summary = {"status": status, "run_id": run_id,
               "stages": {k: {kk: v for kk, v in s.items() if v} for k, s in stages.items()},
               "candidates": sum(1 for r in derived["rows"] if r["candidate"]),
               "alert": snapshot["run"]["alert"]}
    if args.no_save:
        print(json.dumps({**summary, "top_yield": derived["top_yield"], "top_growth": derived["top_growth"],
                          "issues": snapshot["issues"][:20]}, ensure_ascii=False, indent=1))
        return 1 if status == "failed" else 0
    path = SCREEN_DIR / f"{started.strftime('%Y%m%dT%H%M%SZ')}_{run_id}.json.gz"
    write_gz(path, snapshot)
    if UNIVERSE_SOURCE and not args.tickers:
        store_issuers(universe, dict(UNIVERSE_SOURCE))
    publish(snapshot, path)
    c.record_run("revision_screen", status, snapshot=path.name, candidates=summary["candidates"],
                 alert=summary["alert"], stages=summary["stages"])
    print(f"[revision_screen] {json.dumps(summary, ensure_ascii=False)}")
    return 1 if status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
