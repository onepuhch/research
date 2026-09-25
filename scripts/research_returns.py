"""Research-cohort adjusted-price returns; retained vintages, no trades or invented history."""
import json
from datetime import datetime, timedelta, timezone, date
from urllib.request import Request, urlopen
import common as c
import metrics
import research_journal as journal

from market_calendar import EARLY, HOLIDAYS, close_time  # noqa: F401 (re-exported for callers)


def cohorts():
    result = {}
    snapshots = [journal.verify(c.read_json(p, {})) for p in journal.directory().glob('*.json')]
    for snap in sorted(snapshots, key=lambda x: journal.instant(x['captured_at'])):
        for candidate in snap['case']['candidates']:
            result.setdefault(candidate['entity_id'], {**candidate, 'captured_at': snap['captured_at']})
    return list(result.values())


def parse(payload, ticker, retrieved_at):
    results = payload['chart']['result']
    if len(results) != 1:
        raise ValueError('one chart required')
    item = results[0]
    meta = item['meta']
    if meta['symbol'] != ticker or meta['currency'] != 'USD':
        raise ValueError('return series identity mismatch')
    stamps = item['timestamp']
    adjusted = item['indicators']['adjclose'][0]['adjclose']
    if len(stamps) != len(adjusted) or not stamps:
        raise ValueError('adjusted series incomplete')
    output = {}
    for index, (stamp, value) in enumerate(zip(stamps, adjusted)):
        opened = datetime.fromtimestamp(stamp, timezone.utc)
        day = opened.date().isoformat()  # US regular open always falls on the same UTC date.
        if opened.year not in EARLY:
            raise ValueError('trading calendar needs renewal')
        # Yahoo daily bars use session open timestamps, including DST changes.
        closed = close_time(opened.date())
        if closed is None:
            raise ValueError('bar on a closed market date')
        if closed + timedelta(hours=1) > journal.instant(retrieved_at):
            continue  # Do not treat intraday bars as completed daily closes.
        if opened.hour not in {13, 14} or opened.minute != 30:
            raise ValueError('unexpected daily session timestamp')
        number = metrics.number(value)
        if (value is None and index == len(stamps) - 1
                and journal.instant(retrieved_at) - closed <= timedelta(hours=36)):
            # Yahoo publishes the latest session's close hours after the bell. A
            # blank final bar is "not yet published": leave the day out, never fill it.
            continue
        if number is None or number <= 0 or day in output:
            raise ValueError('missing, nonpositive or duplicate adjusted close')
        output[day] = {'adjusted_close': number, 'closed_at': closed.isoformat()}
    return output


def compare(cohort, stock, benchmark, retrieved_at, horizon):
    cutoff = journal.instant(retrieved_at)
    captured = journal.instant(cohort['captured_at'])
    days = []
    day = captured.date() - timedelta(days=1)
    while day <= cutoff.date():
        close = close_time(day)
        if close and captured < close and close + timedelta(hours=1) <= cutoff:
            days.append(day.isoformat())
        day += timedelta(days=1)
    if not days:
        return {'status': '기준 종가 대기'}
    start = days[0]
    due = (date.fromisoformat(start) + timedelta(days=horizon)).isoformat()
    result = {'start': start, 'due': due, 'status': '평가일 대기'}
    ends = [d for d in days if d >= due]
    # Missing ticker data is not permission to move the entry or exit date.
    if start not in stock or start not in benchmark:
        return {**result, 'status': '기준일 종목 자료 부족'}
    if not ends:
        return result
    end = ends[0]
    if any(d not in stock or d not in benchmark for d in days if d <= end):
        return {**result, 'status': '공통 거래일 자료 부족'}
    gross = (stock[end]['adjusted_close'] / stock[start]['adjusted_close'] - 1) * 100
    bench = (benchmark[end]['adjusted_close'] / benchmark[start]['adjusted_close'] - 1) * 100
    return {**result, 'status': '평가', 'end': end, 'gross_pct': gross,
            'net_pct': gross - 0.20, 'benchmark_pct': bench,
            'excess_pp': gross - bench, 'net_excess_pp': gross - 0.20 - bench}


def render():
    from gen_report import table
    files = sorted((c.DATA_DIR / 'return_history').glob('*.json'))
    intro = ('\n# 주가 성과 복기\n\n최초 판단 이후 첫 정규장 종가 기준 30/90/180 달력일 평가. '
             'USD 배당·분할 조정 종가 비율, SPY 비교, 왕복 가상 비용 0.20%p. '
             '실제 매매 수익이 아니며 가설 개정은 별도 표본으로 세지 않습니다. '
             '과거 시세는 아래 조회 시점에 확보한 자료이며 당시 수집했다고 소급하지 않습니다.\n')
    if not files:
        return intro + '\n조정 시계열 자료 없음.\n'
    batch = c.read_json(files[-1], {})
    rows = []
    for cohort in cohorts():
        for horizon in (30, 90, 180):
            stock = batch['series'].get(cohort['ticker'], {})
            benchmark = batch['series'].get('SPY', {})
            r = compare(cohort, stock, benchmark, batch['retrieved_at'], horizon)
            rows.append([cohort['ticker'], horizon, r.get('start', ''), r.get('due', ''), r['status'],
                         r.get('end', ''), *[f'{r[k]:.2f}' if k in r else '' for k in
                         ['gross_pct', 'net_pct', 'benchmark_pct', 'excess_pp', 'net_excess_pp']]])
    return intro + f"\n조회 {batch['retrieved_at']} / 출처 Yahoo Finance chart.\n\n" + table(
        ['기업', '일수', '기준일', '예정일', '상태', '평가일', '수익률 %', '비용 후 %', 'SPY %', '차이 %p', '비용 후 차이 %p'], rows)


def main():
    targets = cohorts()
    if not targets:
        c.record_run('returns', 'empty')
        return 0
    now = datetime.now(timezone.utc)
    start = min(journal.instant(x['captured_at']) for x in targets) - timedelta(days=7)
    batch = {'retrieved_at': now.isoformat(), 'series': {}, 'sources': {}, 'failures': []}
    for ticker in sorted({'SPY', *[x['ticker'] for x in targets]}):
        url = (f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={int(start.timestamp())}'
               f'&period2={int(now.timestamp())}&interval=1d&events=div%2Csplits&includeAdjustedClose=true')
        try:
            with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=25) as response:
                payload = json.load(response)
            batch['series'][ticker] = parse(payload, ticker, now.isoformat())
            batch['sources'][ticker] = {'url': url, 'payload': payload}
        except (OSError, ValueError, KeyError, TypeError, IndexError, OverflowError) as error:
            batch['failures'].append({'ticker': ticker, 'error_type': type(error).__name__})
    c.atomic_json(c.DATA_DIR / 'return_history' / (now.strftime('%Y%m%dT%H%M%S%f') + '.json'), batch)
    c.record_run('returns', 'degraded' if batch['failures'] else 'success',
                 targets=len(targets)+1, failures=batch['failures'])
    from gen_report import save
    print(save('returns', render()))
    return 1 if batch['failures'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
