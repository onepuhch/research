"""Observe identified quarterly consensus independently of annual EPS collection."""
import json
import uuid
from datetime import date
from urllib.request import Request, urlopen
import common as c
import metrics
import add_entry
import collect_eps
import collect_yahoo


def parse(page, target, observed):
    parser = collect_yahoo.Scripts()
    parser.feed(page)
    found = {}
    raw = []
    for part in parser.parts:
        try:
            payload = json.loads(part)
            if isinstance(payload, dict) and isinstance(payload.get('body'), str):
                payload = json.loads(payload['body'])
        except (ValueError, TypeError):
            continue
        results = payload.get('quoteSummary', {}).get('result', []) if isinstance(payload, dict) else []
        for result in results or []:
            if result.get('price', {}).get('symbol') != target['ticker']:
                continue
            for row in result.get('earningsTrendNonGaap', {}).get('trend', []):
                if row.get('period') not in {'0q', '+1q'}:
                    continue
                period = row.get('endDate', '')
                date.fromisoformat(period)
                # Keep provider's current quarter even just after fiscal end, until
                # it rolls forward; period end is not the announcement date.
                raw.append(row)
                for field, name, unit, basis, scale, currency_field in [
                    ('earningsEstimate', 'Quarterly EPS consensus', 'per share', 'non-GAAP', 1, 'earningsCurrency'),
                    ('revenueEstimate', 'Quarterly revenue consensus', 'million', 'not-applicable', 1000000, 'revenueCurrency')]:
                    estimate = row.get(field, {})
                    value = metrics.number(estimate.get('avg', {}).get('raw'))
                    analysts = metrics.number(estimate.get('numberOfAnalysts', {}).get('raw'))
                    if value is None or analysts is None or analysts < 1:
                        raise ValueError('quarter estimate or analyst count missing')
                    if estimate.get(currency_field) != target['currency']:
                        raise ValueError('quarter currency mismatch')
                    key = (period, name)
                    data = {'종목/업종': target['ticker'], 'entity_id': target['entity_id'], 'idea_id': target.get('idea_id', ''),
                            '지표명': name, 'as_of': observed, 'period_end': period, 'fiscal_period': 'quarterly',
                            'metric_kind': 'consensus', '현재값': format(value/scale, '.12g'), '단위': unit,
                            '통화': target['currency'], '회계기준': basis, '출처': 'Yahoo Finance non-GAAP',
                            '출처URL': f"https://finance.yahoo.com/quote/{target['ticker']}/analysis/",
                            '메모': f"Analysts: {int(analysts)}. Provider period label; actual retrieval timestamp. Revenue is not labeled non-GAAP. Historical revision fields are not imported.",
                            'data_quality': 'live'}
                    if key in found and found[key]['현재값'] != data['현재값']:
                        raise ValueError('conflicting quarter estimates')
                    found[key] = data
    if len(found) != 4:
        raise ValueError('two identified quarters with EPS and revenue required')
    return [{'target_table': 'metric_log', 'data': found[k]} for k in sorted(found)], raw


def main():
    targets = collect_eps.load_targets()
    failures, processed = [], 0
    for target in targets:
        try:
            url = f"https://finance.yahoo.com/quote/{target['ticker']}/analysis/"
            with urlopen(Request(url, headers={'User-Agent': 'investment-research-system/2.0'}), timeout=20) as response:
                page = response.read(5_000_001)
            if len(page) > 5_000_000:
                raise ValueError('analysis page exceeds size limit')
            observed = c.utc_now()
            observations, raw = parse(page.decode('utf-8'), target, observed)
            c.atomic_json(c.DATA_DIR / 'consensus_history' / (uuid.uuid4().hex + '.json'),
                          {'ticker': target['ticker'], 'retrieved_at': observed, 'url': url,
                           'module': 'earningsTrendNonGaap', 'quarters': raw})
            for item in observations:
                add_entry.process(item)
                processed += 1
        except (OSError, ValueError, TimeoutError) as error:
            failures.append({'ticker': target['ticker'], 'error_type': type(error).__name__})
    c.record_run('quarterly', 'degraded' if failures else 'success' if targets else 'empty',
                 targets=len(targets), observations=processed, failures=failures)
    print(f"[quarterly] observations={processed}, failed={len(failures)}")
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
