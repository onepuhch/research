"""Read annual EPS estimates embedded in the publicly accessible analysis page."""
import json
from html.parser import HTMLParser
from datetime import date
from urllib.request import Request, urlopen
import common as c
import metrics


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.active = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)


def parse_estimates(page, target):
    parser = Scripts()
    parser.feed(page)
    observations = {}
    for part in parser.parts:
        try:
            payload = json.loads(part)
            if isinstance(payload, dict) and isinstance(payload.get("body"), str):
                payload = json.loads(payload["body"])
        except (ValueError, TypeError):
            continue
        results = payload.get("quoteSummary", {}).get("result", []) if isinstance(payload, dict) else []
        for result in results or []:
            if result.get("price", {}).get("symbol") != target["ticker"]:
                continue
            # Do not silently substitute the unlabeled/general module or GAAP series.
            for row in result.get("earningsTrendNonGaap", {}).get("trend", []):
                if row.get("period") not in {"0y", "+1y"}:
                    continue
                period = row.get("endDate", "")
                end = date.fromisoformat(period)
                if end < date.fromisoformat(c.today()):
                    continue
                estimate = row.get("earningsEstimate", {})
                value = metrics.number(estimate.get("avg", {}).get("raw"))
                analysts = metrics.number(estimate.get("numberOfAnalysts", {}).get("raw"))
                if value is None or analysts is None or analysts < 1:
                    continue
                if estimate.get("earningsCurrency") != target["currency"]:
                    raise ValueError("estimate currency mismatch")
                if period in observations and observations[period]["현재값"] != str(value):
                    raise ValueError("conflicting annual estimates")
                observations[period] = {
                    "종목/업종": target["ticker"], "entity_id": target["entity_id"],
                    "idea_id": target.get("idea_id", ""), "지표명": "EPS consensus",
                    "as_of": c.today(), "period_end": period, "fiscal_period": "annual",
                    "metric_kind": "consensus", "현재값": str(value), "단위": "per share",
                    "통화": target["currency"], "회계기준": "non-GAAP", "출처": "Yahoo Finance non-GAAP",
                    "출처URL": f"https://finance.yahoo.com/quote/{target['ticker']}/analysis/",
                    "메모": f"Analysts: {int(analysts)}. Period end is the provider label, not independently inferred issuer year end. Observation is retrieval date; no historical revision inferred.",
                    "data_quality": "live"}
    if len(observations) != 2:
        raise ValueError("two identified annual non-GAAP estimates required")
    return [{"target_table": "metric_log", "data": observations[k]} for k in sorted(observations)]


def fetch_metrics(target):
    url = f"https://finance.yahoo.com/quote/{target['ticker']}/analysis/"
    request = Request(url, headers={"User-Agent": "investment-research-system/2.0", "Accept": "text/html"})
    with urlopen(request, timeout=20) as response:
        page = response.read(5_000_001)
    if len(page) > 5_000_000:
        raise ValueError("analysis page exceeds size limit")
    return parse_estimates(page.decode("utf-8"), target)
