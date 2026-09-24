"""Read-only observation coverage and history; never interpolate missing observations."""
import argparse
import hashlib
import html
import json
from collections import defaultdict
from datetime import date, timedelta
import common as c
import metrics


def groups(ticker=""):
    result = defaultdict(list)
    for row in c.read_rows("metric_log"):
        if row.get("data_quality") != "live":
            continue
        if ticker and row.get("종목/업종", "").upper() != ticker.upper():
            continue
        result[metrics.series_key(row)].append(row)
    return [result[k] for k in sorted(result)]


def describe(rows):
    daily = metrics.daily_observations(rows)
    if not daily:
        raise ValueError("live series without numeric observations")
    first, last = daily[0], daily[-1]
    start, end = map(date.fromisoformat, [metrics.observation_date(first), metrics.observation_date(last)])
    dates = {metrics.observation_date(r) for r in daily}
    gaps = [(start + timedelta(days=i)).isoformat() for i in range((end-start).days+1)
            if (start + timedelta(days=i)).isoformat() not in dates]
    age = (date.fromisoformat(c.today()) - end).days
    return {"series_id": hashlib.sha256(json.dumps(metrics.series_key(last)).encode()).hexdigest()[:12],
            "ticker": last["종목/업종"], "metric": last["지표명"], "kind": last["metric_kind"],
            "period_end": last.get("period_end", ""), "fiscal_period": last.get("fiscal_period", ""),
            "source": last["출처"], "basis": last["회계기준"], "unit": last["단위"], "currency": last["통화"],
            "rows": len(rows), "days": len(daily), "first": start.isoformat(), "last": end.isoformat(),
            "age_days": age, "calendar_gaps": gaps, "first_value": first["현재값"], "last_value": last["현재값"],
            "changed_days": sum(metrics.number(a["현재값"]) != metrics.number(b["현재값"])
                                for a, b in zip(daily, daily[1:])),
            "daily": daily}


def summary():
    items = [describe(g) for g in groups()]
    annual = [s for s in items if s["metric"] == "EPS consensus" and s["fiscal_period"] == "annual"]
    return (f"숫자 관측 {sum(s['rows'] for s in items)}건 / 비교 가능한 정의 {len(items)}개\n"
            f"연간 EPS {len(annual)}개 시계열 · 변동 없는 날도 보존\n"
            "이력: /history CRDO · 전체 저장 현황: /data\n"
            "명령은 약 6시간 간격 예약 처리이며 지연될 수 있습니다.")


def telegram(ticker=""):
    if not ticker:
        return [html.escape(summary())]
    items = [describe(g) for g in groups(ticker)]
    if not items:
        return [f"{html.escape(ticker)}: 저장된 실제 숫자 관측 없음"]
    chunks = []
    for s in items:
        daily = s["daily"]
        lines = [f"{s['ticker']} | {s['metric']} | 대상 {s['period_end'] or '시세'}",
                 f"{s['source']} · {s['basis']} · {s['currency']} {s['unit']}",
                 f"{s['first']} → {s['last']} / {s['days']}일·{s['rows']}건 / 값 변동 {s['changed_days']}일",
                 f"최초 {s['first_value']} → 최근 {s['last_value']} · 최근 관측 {s['age_days']}일 전",
                 "최근 최대 5관측일 (한국시간 수집일):"]
        lines += [f"{metrics.observation_date(r)}: {r['현재값']}" for r in daily[-5:]]
        lines += ["수집일은 거래일·실적 대상일과 다릅니다. 값 변동은 상향 횟수가 아닙니다."]
        block = html.escape("\n".join(lines))
        if chunks and len(chunks[-1]) + len(block) + 2 <= 3500:
            chunks[-1] += "\n\n" + block
        else:
            chunks.append(block)
    return chunks


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_html():
    items = [describe(g) for g in groups()]
    payload = json.dumps(items, ensure_ascii=False).replace('<', '\\u003c').replace('&', '\\u0026')
    template = (c.ROOT / 'templates' / 'data_history.html').read_text(encoding='utf-8')
    return template.replace('__OBSERVATIONS__', payload).replace('__DATE__', c.today())


def render():
    items = [describe(g) for g in groups()]
    lines = [f"# 데이터 누적 현황 — {c.today()}", "", summary(), "",
             "CSV 원장의 live 관측만 집계합니다. 시계열은 기업·지표·대상 기간·출처·통화·단위·회계기준을 분리합니다.",
             "날짜는 한국시간 관측/수집일입니다. 휴일에도 이전 거래 시세를 다시 관측할 수 있으므로 관측일 수는 거래일 수가 아닙니다.",
             "빈 날짜는 보간하지 않습니다. 아래 달력상 빈 날짜가 모두 수집 오류인 것은 아닙니다. 단일 관측은 추세가 아닙니다.", "",
             "|기업|지표|대상 기간|출처 / 기준|관측 건 / 일|최초 → 최근|최초값 → 최근값|값 변동 일수|최근 관측 경과일|",
             "|---|---|---|---|---|---|---|---|---|"]
    for s in items:
        values = [s['ticker'], s['metric'], s['period_end'] or '시세', f"{s['source']} / {s['basis']} / {s['currency']} {s['unit']}",
                  f"{s['rows']} / {s['days']}", f"{s['first']} → {s['last']}",
                  f"{s['first_value']} → {s['last_value']}", s['changed_days'], s['age_days']]
        lines.append("|" + "|".join(map(cell, values)) + "|")
    lines += ["", "## 원장과 보존 위치", "",
              "- 숫자: `data/processed/metric_log.csv` (동일 값의 후속 날짜 관측도 보존)",
              "- 판단 변경: `data/processed/review_history.csv`; 원래 가설: `research_journal/*.json`",
              "- 조정 주가 원자료: `return_history/*.json` (실제 조회 시점별 묶음)",
              "- 분기 컨센서스: `consensus_history/*.json` (신규 수집 시점부터)",
              "- 실행 이벤트: `run_history/*.json` (신규 기록 시점부터; 과거 실행을 소급 생성하지 않음)",
              "- 위 데이터는 Git 커밋으로 보존. 생성 보고서 Actions artifact 보존은 30일로 별도입니다.", "",
              "## 관측일과 빈 날짜", ""]
    for s in items:
        if s['kind'] not in {'consensus', 'price'}:
            continue
        lines += [f"### {s['ticker']} / {s['metric']} / {s['period_end'] or '시세'} / {s['series_id']}", "",
                  f"달력상 관측 없는 날짜 (최초~최근 사이): {', '.join(s['calendar_gaps']) or '없음'}", "",
                  "|관측 시각|값|시세 거래 시각|원문|", "|---|---|---|---|"]
        for r in s['daily']:
            # URLs are the already validated public provenance fields, not fetch credentials.
            lines.append("|" + "|".join(map(cell, [r.get('as_of'), r['현재값'], r.get('메모', '') if s['kind']=='price' else '', r.get('출처URL')])) + "|")
        lines.append("")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--save', action='store_true')
    args = parser.parse_args()
    content = render()
    if args.save:
        path = c.ROOT / 'docs' / 'data_history.md'
        path.write_text(content, encoding='utf-8')
        directory = c.ROOT / 'reports' / 'generated'
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'data_history.html').write_text(render_html(), encoding='utf-8')
        print(f"[history] {path.name}")
    else:
        print(content)


if __name__ == '__main__':
    main()
