"""Point-in-time observations and same-definition comparison; no inferred history."""
import hashlib
import json
import math
from datetime import date, datetime, timedelta, timezone
import common as c


def number(value):
    try:
        x = float(str(value).replace(",", "").replace("%", ""))
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def observation_date(row):
    return str(row.get("as_of") or row.get("날짜") or "")[:10]


def series_key(row):
    fields = c.table_def("metric_log")["series_key"]
    return tuple("" if key == "종목/업종" and row.get("entity_id") else str(row.get(key, "")) for key in fields)


def prepare(data, rows):
    if not data.get("종목/업종") or not data.get("지표명"):
        raise ValueError("metric requires subject and metric name")
    quality = data.setdefault("data_quality", "live")
    if quality == "live":
        required = ["entity_id", "as_of", "metric_kind", "단위", "통화", "회계기준", "출처", "출처URL"]
        if data.get("metric_kind") != "price":
            required.append("period_end")
        missing = [x for x in required if not data.get(x)]
        if missing or number(data.get("현재값")) is None:
            raise ValueError(f"metric definition incomplete: {missing or ['현재값']}")
        data["entity_id"] = c.resolve_entity(data["entity_id"])[0]
        if len(data["as_of"]) != 10:
            timestamp = datetime.fromisoformat(data["as_of"])
            if timestamp.tzinfo is None:
                raise ValueError("as_of timestamp requires timezone")
            if timestamp > datetime.now(timezone.utc):
                raise ValueError("future observation timestamp is not allowed")
            data["as_of"] = timestamp.astimezone(timezone(timedelta(hours=9))).isoformat()
        observed = date.fromisoformat(observation_date(data))
        if observed > date.fromisoformat(c.today()):
            raise ValueError("future observation date is not allowed")
        if data.get("period_end"):
            date.fromisoformat(data["period_end"])
        data["날짜"] = observed.isoformat()
        # Values must be derived from actual earlier observations, not supplied deltas.
        data.update({"이전값": "", "변화율": "", "방향": ""})
    key = series_key(data)
    observed_at = str(data.get("as_of") or data.get("날짜", ""))
    candidates = [r for r in rows if series_key(r) == key and r.get("data_quality") == quality
                  and str(r.get("as_of") or r.get("날짜", "")) < observed_at]
    previous = max(candidates, key=lambda r: str(r.get("as_of") or r.get("날짜")), default=None)
    if previous:
        data["이전값"] = previous["현재값"]
    old, new = number(data.get("이전값")), number(data.get("현재값"))
    if old is not None and new is not None:
        data["방향"] = "상향" if new > old else "하향" if new < old else "유지"
        if old != 0:
            data["변화율"] = f"{(new-old)/abs(old)*100:.4g}%"
    data["observation_key"] = hashlib.sha256(json.dumps([key, observed_at], ensure_ascii=False).encode()).hexdigest()


def daily_observations(rows):
    by_day = {}
    for row in sorted(rows, key=lambda r: str(r.get("as_of") or r.get("날짜", ""))):
        if row.get("data_quality") == "live" and number(row.get("현재값")) is not None:
            by_day[observation_date(row)] = row
    return [by_day[d] for d in sorted(by_day)]


def revision_stats(rows):
    daily = daily_observations(rows)
    count = 0
    last_up = ""
    # Recompute from observations, including late backfills; unchanged days do not erase history.
    for old, new in zip(daily, daily[1:]):
        delta = number(new["현재값"]) - number(old["현재값"])
        if delta > 0:
            count += 1
            last_up = observation_date(new)
        elif delta < 0:
            count = 0
    months = {}
    for row in daily:
        months[observation_date(row)[:7]] = number(row["현재값"])
    month_streak = 0
    previous_month = None
    previous_value = None
    for month, value in sorted(months.items()):
        year, mon = map(int, month.split("-"))
        index = year * 12 + mon
        if previous_month is not None and index == previous_month + 1 and value > previous_value:
            month_streak += 1
        elif previous_month is not None:
            month_streak = 0
        previous_month, previous_value = index, value
    latest = daily[-1] if daily else {}
    age = (date.fromisoformat(c.today()) - date.fromisoformat(observation_date(latest))).days if latest else None
    return {"up_events": count, "up_months": month_streak, "last_up": last_up,
            "age_days": age, "observations": len(daily), "latest": latest}


def aligned_valuation(eps_rows, price_rows, days=90):
    # Validate definitions before daily collapsing, which could hide a conflicting series.
    live_eps = [r for r in eps_rows if r.get("data_quality") == "live"]
    live_prices = [r for r in price_rows if r.get("data_quality") == "live"]
    if len({series_key(r) for r in live_eps}) > 1 or len({series_key(r) for r in live_prices}) > 1:
        return {"status": "지표 정의 혼합"}
    eps = daily_observations(eps_rows)
    prices = {observation_date(r): r for r in daily_observations(price_rows)}
    if not eps:
        return {"status": "EPS 관측 없음"}
    if any(r.get("metric_kind") != "consensus" for r in eps):
        return {"status": "컨센서스 EPS만 비교 가능"}
    if len({series_key(r) for r in eps}) != 1 or len({series_key(r) for r in prices.values()}) > 1:
        return {"status": "지표 정의 혼합"}
    if any(r.get("entity_id") != eps[-1].get("entity_id") or r.get("통화") != eps[-1].get("통화") for r in prices.values()):
        return {"status": "기업 또는 통화 불일치"}
    end = observation_date(eps[-1])
    start = (date.fromisoformat(end) - timedelta(days=days)).isoformat()
    first = next((r for r in eps if observation_date(r) == start), None)
    if first is None or start not in prices or end not in prices:
        return {"status": "동일 날짜 baseline 부족", "start": start, "end": end}
    e0, e1 = number(first["현재값"]), number(eps[-1]["현재값"])
    p0, p1 = number(prices[start]["현재값"]), number(prices[end]["현재값"])
    if min(e0, e1, p0, p1) <= 0:
        return {"status": "양의 EPS·가격 필요"}
    # Price basis must explicitly assert split alignment; total-return series is not P/E price.
    if any(r.get("단위") != "split-aligned price" for r in prices.values()):
        return {"status": "주식분할 기준 확인 필요"}
    return {"status": "비교 가능", "start": start, "end": end,
            "eps_revision_pct": (e1/e0-1)*100, "price_change_pct": (p1/p0-1)*100,
            "pe_change_pct": ((p1/p0)/(e1/e0)-1)*100}
