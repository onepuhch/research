"""Compare dated prices with identified EPS periods, without an implied fair-value ranking."""
import json
from datetime import date, datetime, timezone, timedelta
import common as c
import metrics


def compare(eps_rows, prices, today=None):
    day = date.fromisoformat(today or c.today())
    eps = metrics.daily_observations(eps_rows)
    quotes = [r for r in prices if r.get("data_quality") == "live"]
    if not eps or not quotes:
        return {"status": "가격 또는 EPS 자료 부족"}
    if len({metrics.series_key(r) for r in eps_rows}) != 1:
        return {"status": "EPS 정의 혼합"}
    latest = eps[-1]
    quote = max(quotes, key=lambda r: r["as_of"])
    if latest.get("지표명") != "EPS consensus" or latest.get("metric_kind") != "consensus" or latest.get("fiscal_period") != "annual":
        return {"status": "연간 EPS 정의 필요"}
    if quote.get("metric_kind") != "price" or quote.get("지표명") != "Regular session price" or any(quote.get(k) != latest.get(k) for k in ["entity_id", "통화", "단위"]):
        return {"status": "가격 정의 불일치"}
    if any(not 0 <= (day - date.fromisoformat(metrics.observation_date(r))).days <= 7 for r in [latest, quote]):
        return {"status": "관측 노후화 또는 미래 관측"}
    try:
        market_time = datetime.fromisoformat(json.loads(quote["메모"])["market_time_utc"])
        if market_time.tzinfo is None:
            raise ValueError("timezone required")
        market_day = market_time.astimezone(timezone(timedelta(hours=9))).date()
        if not 0 <= (day - market_day).days <= 7:
            raise ValueError("stale quote")
    except (ValueError, KeyError, TypeError):
        return {"status": "거래 시각 확인 필요"}
    e, p = metrics.number(latest["현재값"]), metrics.number(quote["현재값"])
    if e is None or e <= 0 or p is None or p <= 0:
        return {"status": "양수 EPS·가격 필요"}
    first = eps[0]
    old = metrics.number(first["현재값"])
    revision = (e / old - 1) * 100 if old and old > 0 else None
    return {"status": "참고 비교", "eps": e, "price": p, "pe": p / e,
            "eps_date": latest["as_of"], "price_observed": quote["as_of"], "market_time": market_time.isoformat(),
            "first_date": first["as_of"], "revision_pct": revision, "period_end": latest["period_end"],
            "eps_url": latest["출처URL"], "price_url": quote["출처URL"]}


def render(case, observations):
    from gen_report import table
    rows = []
    for candidate in case["candidates"]:
        entity = candidate["entity_id"]
        groups = {}
        for row in observations:
            if row.get("entity_id") == entity and row.get("지표명") == "EPS consensus" and row.get("metric_kind") == "consensus":
                groups.setdefault(metrics.series_key(row), []).append(row)
        prices = [r for r in observations if r.get("entity_id") == entity and r.get("출처") == "Yahoo Finance chart" and r.get("지표명") == "Regular session price"]
        for group in groups.values():
            result = compare(group, prices)
            if result["status"] != "참고 비교":
                rows.append([candidate["ticker"], group[-1]["period_end"], result["status"], "", "", "", ""])
                continue
            delta = result["revision_pct"]
            rows.append([candidate["ticker"], result["period_end"], f"[{result['eps']:.5f}]({result['eps_url']}) / {result['eps_date']}",
                         f"[{result['price']:.2f}]({result['price_url']}) / {result['market_time']}",
                         f"{result['pe']:.2f}", f"{delta:+.3f}% (최초 {result['first_date']})" if delta is not None else "비교 불가", result["price_observed"]])
    return "\n## 가격과 시장 기대\n\n정규장 최종 시세와 최신 연간 non-GAAP EPS의 참고 비교입니다. 거래 시각과 EPS 관측일이 다를 수 있으며, 아래 PER은 동시점 역사적 밸류에이션이나 적정가치가 아닙니다. 대상 회계연도가 달라 기업 간 단순 순위로 사용하지 않습니다. 시세는 정규장 체결값이며 종가 경매 가격을 보장하지 않습니다.\n\n" + table(
        ["기업", "EPS 대상 기간 말", "EPS / 관측일", "USD 시세 / 거래시각 UTC", "참고 PER", "동일 기간 EPS 변화", "시세 수집시각"], rows)
