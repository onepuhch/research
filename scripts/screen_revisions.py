"""Screen US-listed stocks for sustained upward EPS estimate revisions.

Yahoo reports each estimate's value today and 7/30/60/90 days ago. Those
provider-reported past values rank candidates on day one; they are stored in
the screen snapshot only and never written to metric_log as our own past
observations.
"""
from __future__ import annotations

import gzip
import http.cookiejar
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from urllib.request import HTTPCookieProcessor, Request, build_opener

import common as c

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126 Safari/537.36"}
SEC_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
EXCHANGES = {"Nasdaq", "NYSE"}
SCREEN_DIR = c.DATA_DIR / "revision_screen"
DOC_PATH = c.ROOT / "docs" / "revision_screen.md"
DEFAULTS = {"min_market_cap_usd": 300_000_000, "min_analysts": 3, "top_n": 20,
            "min_yield_change_pp": 1.0, "min_growth_pct": 25.0, "workers": 6}
KST = timezone(timedelta(hours=9))


def settings() -> dict:
    return {**DEFAULTS, **c.policy().get("revision_screen", {})}


class Yahoo:
    def __init__(self) -> None:
        self.opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.crumb = self.find_crumb()

    def find_crumb(self) -> str:
        try:
            self.opener.open(Request("https://fc.yahoo.com", headers=UA), timeout=15)
        except OSError:
            pass  # Sets the session cookie even when it answers 404.
        for host in ("query2", "query1"):
            try:
                crumb = self.get_text(f"https://{host}.finance.yahoo.com/v1/test/getcrumb").strip()
                if crumb and len(crumb) <= 40 and "<" not in crumb:
                    return crumb
            except OSError:
                continue
        # Cloud runners are sometimes refused by getcrumb; the quote page embeds one.
        page = self.get_text("https://finance.yahoo.com/quote/AAPL/")
        match = re.search(r'"crumb":"([^"]{5,40})"', page)
        if not match:
            raise ValueError("Yahoo crumb unavailable")
        return match.group(1).encode().decode("unicode_escape")

    def get_text(self, url: str) -> str:
        with self.opener.open(Request(url, headers=UA), timeout=20) as response:
            return response.read(5_000_001).decode("utf-8")

    def get_json(self, url: str) -> dict:
        sep = "&" if "?" in url else "?"
        return json.loads(self.get_text(f"{url}{sep}crumb={quote(self.crumb)}"))

    def quotes(self, symbols: list[str]) -> list[dict]:
        fields = "marketCap,epsCurrentYear,epsForward,quoteType,currency,regularMarketPrice,shortName,longName"
        url = (f"https://query2.finance.yahoo.com/v7/finance/quote?symbols={','.join(symbols)}"
               f"&fields={fields}")
        return self.get_json(url).get("quoteResponse", {}).get("result", [])

    def summary(self, symbol: str, modules: str) -> dict:
        data = self.get_json(f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}?modules={modules}")
        return (data.get("quoteSummary", {}).get("result") or [{}])[0]

    def price_days_ago(self, symbol: str, days: int) -> float | None:
        data = self.get_json(f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?range=6mo&interval=1d")
        result = (data.get("chart", {}).get("result") or [{}])[0]
        stamps = result.get("timestamp") or []
        closes = ((result.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose")
                  or (result.get("indicators", {}).get("quote") or [{}])[0].get("close") or [])
        cutoff = time.time() - days * 86400
        past = [(t, v) for t, v in zip(stamps, closes) if v is not None and t <= cutoff]
        return past[-1][1] if past else None


def raw(value):
    return value.get("raw") if isinstance(value, dict) else value


def load_universe(user_agent: str) -> list[dict]:
    request = Request(SEC_URL, headers={"User-Agent": user_agent})
    with build_opener().open(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    index = {name: i for i, name in enumerate(payload["fields"])}
    seen, rows = set(), []
    for item in payload["data"]:
        ticker, exchange = item[index["ticker"]], item[index["exchange"]]
        if exchange not in EXCHANGES or not ticker or ticker in seen:
            continue
        seen.add(ticker)
        rows.append({"ticker": ticker, "symbol": ticker.replace(".", "-"), "name": item[index["name"]],
                     "exchange": exchange})
    return rows


def trend_rows(summary: dict) -> dict[str, dict]:
    rows = {}
    for row in summary.get("earningsTrend", {}).get("trend", []):
        eps = {k: raw(v) for k, v in (row.get("epsTrend") or {}).items()}
        rev = {k: raw(v) for k, v in (row.get("epsRevisions") or {}).items()}
        rows[row.get("period")] = {
            "end": row.get("endDate"), "analysts": raw((row.get("earningsEstimate") or {}).get("numberOfAnalysts")),
            "current": eps.get("current"), "d7": eps.get("7daysAgo"), "d30": eps.get("30daysAgo"),
            "d60": eps.get("60daysAgo"), "d90": eps.get("90daysAgo"), "currency": eps.get("epsTrendCurrency"),
            "up30": rev.get("upLast30days"), "down30": rev.get("downLast30days")}
    return rows


def score(trend: dict[str, dict], price: float | None, cfg: dict) -> dict | None:
    """Rank on the next fiscal year's estimate change, scaled by share price.

    The change in EPS divided by price is the change in forward earnings
    yield. It compares companies of different size and handles loss-making
    turnarounds, where a percentage change on a tiny base would mislead.
    """
    row = trend.get("+1y")
    if not row or not price or price <= 0 or row.get("currency") not in (None, "USD"):
        return None
    cur, d7, d30, d60, d90 = (row.get(k) for k in ("current", "d7", "d30", "d60", "d90"))
    if None in (cur, d30, d90) or (row.get("analysts") or 0) < cfg["min_analysts"]:
        return None
    if d90 == 0 or d30 == 0:
        return None  # Provider leaves 0 when coverage is new; not a real past estimate.
    up30, down30 = row.get("up30") or 0, row.get("down30") or 0
    chain = [v for v in (d90, d60, d30, d7, cur) if v is not None]
    result = {
        "fy_end": row.get("end"), "analysts": row.get("analysts"),
        "eps_now": cur, "eps_30d": d30, "eps_90d": d90,
        "yield_change_90_pp": round((cur - d90) / price * 100, 3),
        "yield_change_30_pp": round((cur - d30) / price * 100, 3),
        "pct_90": round((cur - d90) / abs(d90) * 100, 1) if abs(d90) >= 0.05 else None,
        "pct_30": round((cur - d30) / abs(d30) * 100, 1) if abs(d30) >= 0.05 else None,
        "up30": up30, "down30": down30,
        "steady": cur > d90 and all(a <= b for a, b in zip(chain, chain[1:])),
    }
    # Profitable next year: shrinking losses (often R&D timing) is not earning more.
    rising = cur > 0 and cur > d30 and up30 > down30
    # A: large relative to the share price (cyclicals, low P/E). B: fast growth
    # from a real profit base (growth stocks, whose high price shrinks A).
    result["by_yield"] = rising and result["yield_change_90_pp"] >= cfg["min_yield_change_pp"]
    result["by_growth"] = (rising and d90 >= 0.25 and result["pct_90"] is not None
                           and result["pct_90"] >= cfg["min_growth_pct"])
    result["candidate"] = result["by_yield"] or result["by_growth"]
    return result


def market_follow(eps_now: float, eps_90d: float, price_now: float, price_90d: float | None) -> dict:
    """How much the share price followed the estimate change over 90 days."""
    if not price_90d or price_90d <= 0:
        return {"price_pct_90": None, "pe_change_pct": None}
    price_pct = (price_now / price_90d - 1) * 100
    pe = ((price_now / price_90d) / (eps_now / eps_90d) - 1) * 100 if eps_now > 0 and eps_90d > 0 else None
    return {"price_pct_90": round(price_pct, 1), "pe_change_pct": round(pe, 1) if pe is not None else None}


def fmt_cap(value: float) -> str:
    return f"${value / 1e9:.1f}B" if value >= 1e9 else f"${value / 1e6:.0f}M"


def industry_clusters(candidates: list[dict], minimum: int = 3) -> list[dict]:
    """Industries where several companies are being revised up at once."""
    groups: dict[str, list[dict]] = {}
    for r in candidates:
        if r.get("industry"):
            groups.setdefault(r["industry"], []).append(r)
    return sorted(({"industry": k, "count": len(v), "tickers": [r["ticker"] for r in v]}
                   for k, v in groups.items() if len(v) >= minimum), key=lambda g: g["count"], reverse=True)


def render_table(rows: list[dict]) -> list[str]:
    lines = ["|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        pct = f"{r['pct_90']:+.0f}%" if r["pct_90"] is not None else "적자→흑자 등"
        price = f"{r['price_pct_90']:+.0f}%" if r.get("price_pct_90") is not None else "-"
        pe = f"{r['pe_change_pct']:+.0f}%" if r.get("pe_change_pct") is not None else "-"
        lines.append(f"|{i}|{r['ticker']}|{r.get('industry') or '-'}|{fmt_cap(r['market_cap'])}|"
                     f"${r['eps_90d']:.2f} → ${r['eps_now']:.2f}|{pct}|{r['yield_change_90_pp']:+.2f}%p|"
                     f"{r['up30']}/{r['down30']}|{price}|{pe}|{'예' if r['steady'] else '-'}|")
    return lines


def render_doc(meta: dict, top_yield: list[dict], top_growth: list[dict], clusters: list[dict] | None = None) -> str:
    lines = [
        "# 이익 예상치 상향 스크리너",
        "",
        f"기준: {meta['generated_kst']} KST · 대상 {meta['screened']}개(미국 상장, 시가총액 {fmt_cap(meta['min_cap'])} 이상, "
        f"분석가 {meta['min_analysts']}명 이상) · 후보 {meta['candidates']}개 · 조회 실패 {meta['failed']}개",
        "",
        "증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다. 순위는 두 가지다.",
        "",
        "- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.",
        "- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다. 주가가 비싼 고성장주는 A에서 작게 나오므로 따로 본다.",
        "",
        "- **주가 90일**이 EPS 증가율보다 작으면 **PER 변화**가 음수다. 시장이 이익 증가를 아직 덜 반영했을 수 있다는 뜻이며 저평가의 증거는 아니다.",
        "- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다. 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다.",
        "- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.",
        "",
    ]
    if clusters:
        lines += ["## 여러 회사가 동시에 상향되는 업종", "",
                  "같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.", ""]
        lines += [f"- **{g['industry']}** {g['count']}곳: {', '.join(g['tickers'])}" for g in clusters]
        lines += [""]
    lines += ["## A. 이익 규모 대비 상향", ""] + render_table(top_yield)
    lines += ["", "## B. 성장률 상향", ""] + render_table(top_growth)
    lines += ["", f"전체 결과: `data/processed/revision_screen/{meta['date']}.json.gz`", ""]
    return "\n".join(lines)


def write_gz(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def main() -> int:
    cfg = settings()
    started = datetime.now(timezone.utc)
    stage = "sec_universe"
    try:
        universe = load_universe(os.environ.get("SEC_USER_AGENT") or "investment-research-system/2.0 research-bot")
        stage = "yahoo_crumb"
        yahoo = Yahoo()
    except (OSError, ValueError, KeyError) as error:
        detail = {"stage": stage, "error_type": type(error).__name__, "http_status": getattr(error, "code", None)}
        c.record_run("revision_screen", "failed", **detail)
        print(f"[revision_screen] setup failed: {detail}")
        return 1

    by_symbol = {row["symbol"]: row for row in universe}
    quotes, quote_failures = {}, 0
    symbols = list(by_symbol)
    for i in range(0, len(symbols), 100):
        try:
            for q in yahoo.quotes(symbols[i:i + 100]):
                quotes[q["symbol"]] = q
        except (OSError, ValueError):
            quote_failures += 1
    eligible = [s for s, q in quotes.items()
                if q.get("quoteType") == "EQUITY" and q.get("currency") == "USD"
                and (q.get("marketCap") or 0) >= cfg["min_market_cap_usd"] and q.get("epsForward") is not None
                and q.get("regularMarketPrice")]

    def fetch(symbol):
        try:
            return symbol, trend_rows(yahoo.summary(symbol, "earningsTrend")), None
        except (OSError, ValueError, KeyError, IndexError) as error:
            return symbol, None, type(error).__name__

    rows, failures = [], {}
    with ThreadPoolExecutor(max_workers=cfg["workers"]) as pool:
        for symbol, trend, error in pool.map(fetch, eligible):
            if error:
                failures[error] = failures.get(error, 0) + 1
                continue
            q = quotes[symbol]
            scored = score(trend, q["regularMarketPrice"], cfg)
            if scored:
                rows.append({"ticker": by_symbol[symbol]["ticker"], "symbol": symbol,
                             "name": q.get("longName") or q.get("shortName") or by_symbol[symbol]["name"],
                             "market_cap": q["marketCap"], "price": q["regularMarketPrice"], **scored})

    candidates = [r for r in rows if r["candidate"]]
    top_yield = sorted((r for r in candidates if r["by_yield"]), key=lambda r: r["yield_change_90_pp"], reverse=True)[:cfg["top_n"]]
    top_growth = sorted((r for r in candidates if r["by_growth"]), key=lambda r: r["pct_90"], reverse=True)[:cfg["top_n"]]
    top = top_yield + [r for r in top_growth if r not in top_yield]
    for r in candidates:
        try:
            profile = yahoo.summary(r["symbol"], "assetProfile").get("assetProfile", {})
            r["industry"], r["sector"] = profile.get("industry"), profile.get("sector")
            r["summary"] = (profile.get("longBusinessSummary") or "")[:600]
            if r in top:
                r.update(market_follow(r["eps_now"], r["eps_90d"], r["price"], yahoo.price_days_ago(r["symbol"], 90)))
        except (OSError, ValueError, KeyError, IndexError):
            r.update({"price_pct_90": None, "pe_change_pct": None})

    now_kst = datetime.now(KST)
    meta = {"date": now_kst.strftime("%Y-%m-%d"), "generated_kst": now_kst.strftime("%Y-%m-%d %H:%M"),
            "retrieved_at": started.isoformat(timespec="seconds"), "universe": len(universe),
            "quoted": len(quotes), "screened": len(eligible), "scored": len(rows),
            "candidates": len(candidates), "failed": sum(failures.values()), "failures": failures,
            "quote_batch_failures": quote_failures, "min_cap": cfg["min_market_cap_usd"],
            "min_analysts": cfg["min_analysts"], "source": "Yahoo Finance earningsTrend (provider-reported 7/30/60/90-day values)"}
    clusters = industry_clusters(candidates)
    write_gz(SCREEN_DIR / f"{meta['date']}.json.gz", {"meta": meta, "top_yield": [r["ticker"] for r in top_yield],
             "top_growth": [r["ticker"] for r in top_growth], "clusters": clusters, "rows": rows})
    DOC_PATH.write_text(render_doc(meta, top_yield, top_growth, clusters), encoding="utf-8")
    degraded = meta["failed"] > max(20, len(eligible) * 0.1) or quote_failures
    c.record_run("revision_screen", "degraded" if degraded else "success" if rows else "empty",
                 screened=len(eligible), scored=len(rows), candidates=len(candidates), failed=meta["failed"])
    print(f"[revision_screen] universe={len(universe)} screened={len(eligible)} scored={len(rows)} "
          f"candidates={len(candidates)} failed={meta['failed']}")
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
