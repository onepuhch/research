import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_prices
import expectations


class ExpectationsTests(unittest.TestCase):
    def quote(self, **changes):
        meta = {"symbol": "CRDO", "currency": "USD", "regularMarketPrice": 100,
                "regularMarketTime": 1789156801, "preMarketPrice": 999}
        meta.update(changes)
        return collect_prices.parse_quote({"chart": {"result": [{"meta": meta}]}},
            {"ticker": "CRDO", "entity_id": "NASDAQ:CRDO", "currency": "USD"}, "2026-09-14T13:00:00+00:00")["data"]

    def eps(self):
        return {"종목/업종": "CRDO", "entity_id": "NASDAQ:CRDO", "지표명": "EPS consensus", "metric_kind": "consensus",
                "fiscal_period": "annual", "period_end": "2027-04-30", "통화": "USD", "단위": "per share", "회계기준": "non-GAAP",
                "출처": "Yahoo Finance non-GAAP", "출처URL": "https://example.com/eps", "as_of": "2026-09-14", "현재값": "5", "data_quality": "live"}

    def test_market_time_and_session_are_preserved(self):
        quote = self.quote()
        self.assertEqual(quote["현재값"], "100.0")
        result = expectations.compare([self.eps()], [quote], "2026-09-14")
        self.assertEqual(result["pe"], 20)
        self.assertTrue(result["market_time"].startswith("2026-09-11"))

    def test_wrong_identity_and_future_or_stale_quote_rejected(self):
        for changes in [{"symbol": "ALAB"}, {"currency": "EUR"}, {"regularMarketTime": 1},
                        {"regularMarketTime": 9999999999}, {"regularMarketPrice": 0}]:
            with self.assertRaises(ValueError):
                self.quote(**changes)

    def test_mixed_years_stale_and_negative_eps_do_not_produce_pe(self):
        eps, quote = self.eps(), self.quote()
        mixed = [eps, {**eps, "period_end": "2028-04-30"}]
        for rows, day in [(mixed, "2026-09-14"), ([eps], "2026-10-14"),
                          ([{**eps, "현재값": "-1"}], "2026-09-14")]:
            self.assertNotIn("pe", expectations.compare(rows, [quote], day))


if __name__ == "__main__":
    unittest.main()
