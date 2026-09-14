"""Observe dated regular-session quotes; never substitute premarket prices or backdate retrievals."""
import json
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import common as c
import metrics
import add_entry
from collect_eps import load_targets


def parse_quote(payload, target, observed=None):
    now = datetime.fromisoformat(observed) if observed else datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("retrieval timezone required")
    result = payload.get("chart", {}).get("result") or []
    if len(result) != 1:
        raise ValueError("one quote required")
    meta = result[0].get("meta", {})
    if meta.get("symbol") != target["ticker"] or meta.get("currency") != target["currency"]:
        raise ValueError("quote identity mismatch")
    value = metrics.number(meta.get("regularMarketPrice"))
    stamp = metrics.number(meta.get("regularMarketTime"))
    if value is None or value <= 0 or stamp is None:
        raise ValueError("positive price and market timestamp required")
    market_time = datetime.fromtimestamp(stamp, timezone.utc)
    if not timedelta(0) <= now - market_time <= timedelta(days=7):
        raise ValueError("future or stale market quote")
    return {"target_table": "metric_log", "data": {
        "종목/업종": target["ticker"], "entity_id": target["entity_id"], "idea_id": target.get("idea_id", ""),
        "지표명": "Regular session price", "metric_kind": "price", "as_of": now.isoformat(),
        "현재값": str(value), "단위": "per share", "통화": target["currency"],
        "회계기준": "not-applicable", "출처": "Yahoo Finance chart",
        "출처URL": f"https://query1.finance.yahoo.com/v8/finance/chart/{target['ticker']}?range=5d&interval=1d",
        "메모": json.dumps({"market_time_utc": market_time.isoformat(), "session": "regular",
                            "limitation": "Latest regular-session quote, not necessarily a closing auction price. Retrieval date is not trading date."}),
        "data_quality": "live"}}


def main():
    targets, failures, count = load_targets(), [], 0
    for target in targets:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{target['ticker']}?range=5d&interval=1d"
            with urlopen(Request(url, headers={"User-Agent": "investment-research-system/2.0"}), timeout=20) as response:
                payload = json.load(response)
            add_entry.process(parse_quote(payload, target))
            count += 1
        except (HTTPError, URLError, OSError, ValueError, OverflowError) as error:
            failures.append({"ticker": target["ticker"], "error_type": type(error).__name__, "http_status": getattr(error, "code", None)})
    c.record_run("prices", "degraded" if failures else "success" if targets else "empty",
                 targets=len(targets), observations=count, failures=failures)
    print(f"[prices] observations={count}, failures={len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
