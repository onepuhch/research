"""Collect FMP analyst EPS estimates into metric_log."""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
import add_entry  # noqa: E402
import common as c  # noqa: E402

WATCHLIST_PATH = c.ROOT / "config" / "eps_watchlist.json"
FMP_ENDPOINT = "https://financialmodelingprep.com/api/v3/analyst-estimates"
TIMEOUT = 20
TICKER_PATTERN = re.compile(r"^[A-Z0-9.-]+$")


def console(value: Any) -> None:
    encoding = sys.stdout.encoding or "utf-8"
    safe = str(value).encode(encoding, errors="backslashreplace").decode(encoding)
    print(safe)


def load_watchlist() -> list[str]:
    if not WATCHLIST_PATH.exists():
        raise FileNotFoundError(f"watchlist file not found: {WATCHLIST_PATH}")
    try:
        raw = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"failed to parse watchlist JSON: {error}") from error
    if not isinstance(raw, list):
        raise ValueError("eps_watchlist.json must contain a JSON array.")

    tickers: list[str] = []
    seen: set[str] = set()
    for value in raw:
        ticker = str(value or "").strip().upper()
        if not ticker:
            continue
        if not TICKER_PATTERN.fullmatch(ticker):
            console(f"[warn] 유효하지 않은 ticker skip: {ticker}")
            continue
        if ticker not in seen:
            seen.add(ticker)
            tickers.append(ticker)
    return tickers


def fetch_estimates(ticker: str, api_key: str) -> list[dict[str, Any]]:
    query = urlencode({"apikey": api_key, "limit": 2})
    url = f"{FMP_ENDPOINT}/{quote(ticker, safe='.-')}?{query}"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "investment-research-system"})
    with urlopen(request, timeout=TIMEOUT) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        message = payload.get("Error Message") if isinstance(payload, dict) else "invalid response"
        raise ValueError(str(message or "invalid FMP response"))
    return [item for item in payload if isinstance(item, dict)]


def eps_value(record: dict[str, Any]) -> str:
    value = record.get("estimatedEpsAvg")
    if isinstance(value, bool) or value is None:
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(number):
        return ""
    return format(number, ".12g")


def fiscal_year(record: dict[str, Any]) -> str:
    for key in ("calendarYear", "fiscalYear"):
        value = str(record.get(key, "") or "").strip()
        match = re.search(r"\b(19|20)\d{2}\b", value)
        if match:
            return match.group(0)
    date_text = str(record.get("date", "") or "").strip()
    match = re.match(r"((?:19|20)\d{2})", date_text)
    return match.group(1) if match else ""


def estimate_sort_key(record: dict[str, Any]) -> tuple[str, str]:
    return (
        str(record.get("date", "") or ""),
        str(record.get("calendarYear", record.get("fiscalYear", "")) or ""),
    )


def build_metric(ticker: str, estimates: list[dict[str, Any]]) -> dict[str, Any] | None:
    ordered = sorted(estimates, key=estimate_sort_key, reverse=True)
    if not ordered:
        return None
    current = ordered[0]
    year = fiscal_year(current)
    current_eps = eps_value(current)
    if not year or not current_eps:
        return None
    previous_eps = next(
        (
            eps_value(record)
            for record in ordered[1:]
            if fiscal_year(record) == year and eps_value(record)
        ),
        "",
    )
    data = {
        "종목/업종": ticker,
        "지표명": f"EPS 컨센서스 (FY{year})",
        "현재값": current_eps,
        "출처": "FMP",
    }
    if previous_eps:
        data["이전값"] = previous_eps
    return {
        "target_table": "metric_log",
        "data": data,
    }


def main() -> int:
    try:
        tickers = load_watchlist()
    except (FileNotFoundError, ValueError) as error:
        console(f"[error] {error}")
        return 1
    if not tickers:
        console("watchlist 비어있음")
        return 0

    api_key = c.load_dotenv_value("FMP_API_KEY")
    if not api_key:
        console("[warn] FMP_API_KEY 없음; EPS 수집 건너뜀")
        return 0

    added = 0
    skipped = 0
    for ticker in tickers:
        try:
            estimates = fetch_estimates(ticker, api_key)
            metric = build_metric(ticker, estimates)
            if metric is None:
                console(f"[warn] {ticker}: 유효한 EPS 추정치를 찾을 수 없어 skip")
                skipped += 1
                continue
            add_entry.process(metric)
            added += 1
        except (
            HTTPError,
            URLError,
            TimeoutError,
            OSError,
            json.JSONDecodeError,
            ValueError,
        ) as error:
            console(f"[warn] {ticker}: {error}; skip")
            skipped += 1

    console(f"[eps] 추가 {added}건, skip {skipped}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
