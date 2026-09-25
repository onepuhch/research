import sys
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from datetime import date, timedelta
import research_returns as r
import collect


class ReturnTests(unittest.TestCase):
    def data(self):
        rows = {}
        d = date(2026, 9, 14)
        while d <= date(2026, 10, 14):
            close = r.close_time(d)
            if close:
                rows[d.isoformat()] = {'adjusted_close': 100, 'closed_at': close.isoformat()}
            d += timedelta(days=1)
        return rows

    def test_horizon_costs_and_no_early_scoring(self):
        stock, bench = self.data(), self.data()
        stock['2026-10-14']['adjusted_close'] = 110
        bench['2026-10-14']['adjusted_close'] = 105
        cohort = {'captured_at': '2026-09-14T13:59:00Z'}
        self.assertEqual(r.compare(cohort, stock, bench, '2026-09-24T21:01:00Z', 30)['status'], '평가일 대기')
        result = r.compare(cohort, stock, bench, '2026-10-14T21:01:00Z', 30)
        self.assertAlmostEqual(result['net_excess_pp'], 4.8)
        self.assertEqual(result['start'], '2026-09-14')

    def test_missing_start_does_not_shift_baseline(self):
        stock, bench = self.data(), self.data()
        del bench['2026-09-14']
        result = r.compare({'captured_at': '2026-09-14T13:59:00Z'}, stock, bench, '2026-10-14T21:01:00Z', 30)
        self.assertNotIn('gross_pct', result)

    def test_calendar_and_post_close_capture(self):
        self.assertEqual(r.close_time(date(2026, 11, 27)).hour, 18)
        self.assertIsNone(r.close_time(date(2026, 12, 25)))
        data = self.data()
        result = r.compare({'captured_at': '2026-09-14T20:01:00Z'}, data, data, '2026-09-24T21:01:00Z', 30)
        self.assertEqual(result['start'], '2026-09-15')

    def test_raw_close_never_substitutes_for_adjusted_close(self):
        payload = {'chart': {'result': [{'meta': {'symbol': 'SPY', 'currency': 'USD'},
                   'timestamp': [1789392600], 'indicators': {'quote': [{'close': [100]}]}}]}}
        with self.assertRaises(KeyError):
            r.parse(payload, 'SPY', '2026-09-24T21:01:00Z')

    def chart(self, closes):
        # Bars open 13:30 UTC on 2026-09-21..24 (Mon-Thu, EDT).
        stamps = [1789997400 + 86400 * i for i in range(len(closes))]
        return {'chart': {'result': [{'meta': {'symbol': 'SPY', 'currency': 'USD'}, 'timestamp': stamps,
                                      'indicators': {'adjclose': [{'adjclose': closes}]}}]}}

    def test_unpublished_latest_close_is_left_out_not_filled(self):
        # 2026-09-25 00:20 UTC: four hours after the 2026-09-24 close, Yahoo still had a blank bar.
        series = r.parse(self.chart([773.5, 773.38, 767.81, None]), 'SPY', '2026-09-25T00:20:00Z')
        self.assertEqual(sorted(series), ['2026-09-21', '2026-09-22', '2026-09-23'])

    def test_blank_close_still_fails_when_not_latest_or_stale(self):
        with self.assertRaises(ValueError):
            r.parse(self.chart([773.5, None, 767.81, 770.0]), 'SPY', '2026-09-25T00:20:00Z')
        with self.assertRaises(ValueError):
            r.parse(self.chart([773.5, 773.38, 767.81, None]), 'SPY', '2026-09-27T00:20:00Z')

    def test_collection_retries_transient_server_failure(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.headers.get_content_charset.return_value = 'utf-8'
        response.read.return_value = b'ok'
        with patch.object(collect, 'urlopen', side_effect=[HTTPError('https://example.com', 500, '', {}, None), response]) as call, patch.object(collect.time, 'sleep'):
            self.assertEqual(collect.fetch_text('https://example.com'), 'ok')
            self.assertEqual(call.call_count, 2)

    def test_collection_does_not_retry_access_denial(self):
        with patch.object(collect, 'urlopen', side_effect=HTTPError('https://example.com', 403, '', {}, None)) as call:
            with self.assertRaises(HTTPError):
                collect.fetch_text('https://example.com')
            self.assertEqual(call.call_count, 1)
