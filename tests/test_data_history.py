import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import common as c
import data_history as history
import collect_quarterly as quarterly
import telegram_cmd


class HistoryTests(unittest.TestCase):
    def metric(self, day, value='5', **fields):
        return {'entity_id': 'NASDAQ:CRDO', '종목/업종': 'CRDO', '지표명': 'EPS consensus',
                'metric_kind': 'consensus', 'fiscal_period': 'annual', 'period_end': '2027-04-30',
                '출처': 'Yahoo Finance non-GAAP', '통화': 'USD', '단위': 'per share', '회계기준': 'non-GAAP',
                'as_of': day, '현재값': value, 'data_quality': 'live', **fields}

    def test_definitions_and_unchanged_dates_preserved_without_filling_gap(self):
        rows = [self.metric('2026-09-20'), self.metric('2026-09-22'),
                self.metric('2026-09-22', '9', period_end='2028-04-30'),
                self.metric('2026-09-21', '8', data_quality='example')]
        with patch.object(c, 'read_rows', return_value=rows):
            groups = history.groups('CRDO')
            self.assertEqual(len(groups), 2)
            s = history.describe(groups[0])
            self.assertEqual((s['days'], s['changed_days'], s['calendar_gaps']), (2, 0, ['2026-09-21']))
            self.assertEqual(len(s['daily']), 2)

    def test_latest_daily_value_and_html_payload_safe(self):
        rows = [self.metric('2026-09-20T10:00:00+09:00'), self.metric('2026-09-20T11:00:00+09:00', '6', **{'메모': '</script><script>alert(1)</script>'})]
        with patch.object(c, 'read_rows', return_value=rows):
            s = history.describe(rows)
            self.assertEqual((s['rows'], s['days'], s['last_value']), (2, 1, '6'))
            self.assertNotIn('</script><script>alert(1)', history.render_html())
            self.assertTrue(all(len(x)<4096 for x in history.telegram('CRDO')))

    def test_run_failure_survives_following_success(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(c, 'DATA_DIR', pathlib.Path(tmp)):
            c.record_run('eps', 'failed', error_type='TimeoutError')
            c.record_run('eps', 'success', observations=6)
            events = [json.loads(p.read_text()) for p in (pathlib.Path(tmp)/'run_history').glob('*.json')]
            self.assertEqual({e['status'] for e in events}, {'failed', 'success'})
            self.assertEqual(c.read_json(pathlib.Path(tmp)/'run_status.json', {})['eps']['status'], 'success')

    def page(self, symbol='CRDO', currency='USD', module='earningsTrendNonGaap', conflict=False):
        rows = []
        for label, end in [('0q', '2026-10-31'), ('+1q', '2027-01-31')]:
            rows.append({'period': label, 'endDate': end,
                         'earningsEstimate': {'avg': {'raw': 1.25}, 'numberOfAnalysts': {'raw': 5}, 'earningsCurrency': currency},
                         'revenueEstimate': {'avg': {'raw': 530000000}, 'numberOfAnalysts': {'raw': 4}, 'revenueCurrency': currency}})
        if conflict:
            rows.append({**rows[0], 'earningsEstimate': {**rows[0]['earningsEstimate'], 'avg': {'raw': 99}}})
        return '<script>'+json.dumps({'quoteSummary': {'result': [{'price': {'symbol': symbol}, module: {'trend': rows}}]}})+'</script>'

    def test_quarterly_period_units_and_accounting_basis(self):
        target = {'ticker': 'CRDO', 'currency': 'USD', 'entity_id': 'NASDAQ:CRDO'}
        rows, raw = quarterly.parse(self.page(), target, '2026-09-24T15:00:00+00:00')
        self.assertEqual(len(rows), 4)
        revenue = [r['data'] for r in rows if r['data']['지표명']=='Quarterly revenue consensus']
        self.assertTrue(all(r['현재값']=='530' and r['회계기준']=='not-applicable' and r['단위']=='million' for r in revenue))
        self.assertEqual(len(raw), 2)
        for page in [self.page(symbol='OTHER'), self.page(currency='EUR'), self.page(module='earningsTrend'), self.page(conflict=True)]:
            with self.assertRaises(ValueError):
                quarterly.parse(page, target, c.utc_now())

    def test_history_command_is_persisted_safely_and_routed(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(c, 'DATA_DIR', pathlib.Path(tmp)), \
             patch.object(telegram_cmd, 'OFFSET_PATH', pathlib.Path(tmp)/'offset.json'), \
             patch.object(telegram_cmd, 'send_reply') as reply, patch.object(history, 'telegram', return_value=['history']):
            telegram_cmd.process_updates('unused', '123', [{'update_id': 1, 'message': {'chat': {'id': '123'}, 'text': '/history CRDO'}}])
            reply.assert_called_once_with('unused', '123', 'history')
            queue=c.read_json(pathlib.Path(tmp)/'command_queue.json', {})
            self.assertEqual(queue['1']['status'], 'done')
            self.assertNotIn('text', queue['1'])


if __name__ == '__main__':
    unittest.main()
