"""Collect dated consensus snapshots for the next two fiscal period ends."""
import json
import re
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import common as c
import metrics
import add_entry
import collect_yahoo

FMP_ENDPOINT = "https://financialmodelingprep.com/stable/analyst-estimates"


def load_targets():
    targets = {}
    registry = c.read_json(c.ROOT / "config" / "entities.json", {})
    for row in c.active_ideas():
        ticker = row.get("ticker", "").upper()
        if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", ticker):
            continue
        meta = registry.get(ticker, {})
        targets[ticker] = {"ticker": ticker, "entity_id": row.get("entity_id") or meta.get("entity_id"),
                           "idea_id": row["idea_id"], "currency": meta.get("currency", "")}
    for ticker in c.read_json(c.ROOT / "config" / "eps_watchlist.json", []):
        ticker = str(ticker).upper()
        if ticker not in targets and ticker in registry:
            targets[ticker] = {"ticker": ticker, "idea_id": "", **registry[ticker]}
    return list(targets.values())


def load_watchlist():
    return [target["ticker"] for target in load_targets()]


def fetch_estimates(ticker, api_key):
    query = urlencode({"symbol": ticker, "period": "annual", "limit": 10, "apikey": api_key})
    request = Request(FMP_ENDPOINT + "?" + query, headers={"Accept": "application/json", "User-Agent": "investment-research-system/2"})
    with urlopen(request, timeout=20) as response:
        data = json.load(response)
    if not isinstance(data, list):
        raise ValueError("invalid estimates response")
    return data


def build_metrics(target, estimates, as_of=None):
    observed = as_of or c.today()
    date.fromisoformat(observed[:10])
    by_period = {}
    for row in estimates:
        if not isinstance(row, dict):
            continue
        period = str(row.get("date", ""))[:10]
        try:
            end = date.fromisoformat(period)
        except ValueError:
            continue
        eps = metrics.number(row.get("epsAvg", row.get("estimatedEpsAvg")))
        if end < date.fromisoformat(observed[:10]) or eps is None:
            continue
        if period in by_period and by_period[period] != eps:
            raise ValueError("conflicting estimates for the same period")
        by_period[period] = eps
    result = []
    for period, eps in sorted(by_period.items())[:2]:
        result.append({"target_table": "metric_log", "data": {
            "종목/업종": target["ticker"], "entity_id": target["entity_id"], "idea_id": target.get("idea_id", ""),
            "지표명": "EPS consensus", "as_of": observed, "period_end": period,
            "fiscal_period": "annual", "metric_kind": "consensus", "현재값": format(eps, ".12g"),
            "단위": "per share", "통화": target.get("currency", ""), "회계기준": "provider-defined",
            "출처": "FMP stable", "출처URL": FMP_ENDPOINT + "?" + urlencode({"symbol": target["ticker"], "period": "annual"}),
            "메모": "Provider-defined consensus. Fiscal year label and GAAP adjustment not inferred; same provider/period comparisons only.",
            "data_quality": "live"}})
    return result


def main():
    targets = load_targets()
    if not targets:
        c.record_run("eps", "empty", targets=0, observations=0)
        print("[eps] no registered targets")
        return 0
    key = c.load_dotenv_value("FMP_API_KEY")
    provider = c.policy().get("eps_provider", "yahoo")
    failures = []
    added = 0
    for target in targets:
        try:
            if not target.get("currency") or not target.get("entity_id"):
                raise ValueError("entity or currency metadata missing")
            if provider == "yahoo":
                observations = collect_yahoo.fetch_metrics(target)
            elif provider == "fmp" and key:
                observations = build_metrics(target, fetch_estimates(target["ticker"], key))
            else:
                raise ValueError("provider configuration or credential missing")
            if not observations:
                raise ValueError("no valid future estimates")
            for observation in observations:
                add_entry.process(observation)
                added += 1
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            failures.append({"ticker": target["ticker"], "error_type": type(error).__name__,
                             "http_status": getattr(error, "code", None)})
            print(f"[eps] {target['ticker']}: {type(error).__name__} ({getattr(error, 'code', 'n/a')})")
    c.record_run("eps", "degraded" if failures else "success", targets=len(targets), observations=added, failures=failures, provider=provider)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
