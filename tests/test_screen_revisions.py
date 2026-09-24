import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import screen_revisions as sr  # noqa: E402

CFG = dict(sr.DEFAULTS)


def trend(current, d7, d30, d60, d90, up30=5, down30=0, analysts=8):
    return {"+1y": {"end": "2027-12-31", "analysts": analysts, "current": current, "d7": d7, "d30": d30,
                    "d60": d60, "d90": d90, "currency": "USD", "up30": up30, "down30": down30}}


class ScoreTest(unittest.TestCase):
    def test_zero_past_estimate_is_missing_history(self):
        self.assertIsNone(sr.score(trend(33.78, 33.0, 0.0, 0.0, 0.0), 100, CFG))
        self.assertIsNone(sr.score(trend(2.0, 2.0, 1.9, 1.0, 0.0), 30, CFG))

    def test_shrinking_loss_is_not_a_candidate(self):
        result = sr.score(trend(-1.06, -1.1, -1.2, -1.5, -1.65), 3.0, CFG)
        self.assertGreater(result["yield_change_90_pp"], 1)
        self.assertFalse(result["candidate"])

    def test_cyclical_ranks_by_yield(self):
        result = sr.score(trend(47.13, 46, 40, 30, 23.93), 200, CFG)
        self.assertTrue(result["by_yield"])
        self.assertTrue(result["steady"])
        self.assertAlmostEqual(result["yield_change_90_pp"], 11.6, places=1)

    def test_expensive_grower_ranks_by_growth(self):
        result = sr.score(trend(6.39, 6.3, 6.0, 5.0, 4.21), 360, CFG)
        self.assertFalse(result["by_yield"])
        self.assertTrue(result["by_growth"])
        self.assertAlmostEqual(result["pct_90"], 51.8, places=1)

    def test_tiny_base_growth_is_ignored(self):
        result = sr.score(trend(0.40, 0.4, 0.3, 0.2, 0.10), 100, CFG)
        self.assertFalse(result["by_growth"])

    def test_requires_more_upgrades_than_downgrades_and_recent_rise(self):
        self.assertFalse(sr.score(trend(6.39, 6.3, 6.0, 5.0, 4.21, up30=2, down30=2), 360, CFG)["candidate"])
        self.assertFalse(sr.score(trend(5.9, 6.0, 6.0, 5.0, 4.21), 360, CFG)["candidate"])

    def test_requires_analyst_coverage(self):
        self.assertIsNone(sr.score(trend(6.39, 6.3, 6.0, 5.0, 4.21, analysts=2), 360, CFG))


class HelpersTest(unittest.TestCase):
    def test_market_follow(self):
        follow = sr.market_follow(eps_now=2.0, eps_90d=1.0, price_now=110, price_90d=100)
        self.assertEqual(follow["price_pct_90"], 10.0)
        self.assertEqual(follow["pe_change_pct"], -45.0)
        self.assertIsNone(sr.market_follow(2.0, -1.0, 110, 100)["pe_change_pct"])
        self.assertIsNone(sr.market_follow(2.0, 1.0, 110, None)["price_pct_90"])

    def test_industry_clusters_need_three(self):
        rows = [{"ticker": t, "industry": i} for t, i in
                [("MPC", "Refining"), ("VLO", "Refining"), ("PSX", "Refining"), ("NUE", "Steel"), ("CLF", "Steel")]]
        self.assertEqual(sr.industry_clusters(rows), [{"industry": "Refining", "count": 3, "tickers": ["MPC", "VLO", "PSX"]}])

    def test_render_doc(self):
        row = {"ticker": "MPC", "industry": "Refining", "market_cap": 1.1e11, "eps_90d": 23.93, "eps_now": 47.13,
               "pct_90": 97.0, "yield_change_90_pp": 5.87, "up30": 12, "down30": 0, "price_pct_90": 56.0,
               "pe_change_pct": -21.0, "steady": True}
        meta = {"generated_kst": "2026-09-25 09:30", "screened": 3000, "min_cap": 3e8, "min_analysts": 3,
                "candidates": 90, "failed": 1, "date": "2026-09-25"}
        doc = sr.render_doc(meta, [row], [], [{"industry": "Refining", "count": 3, "tickers": ["MPC", "VLO", "PSX"]}])
        self.assertIn("|1|MPC|Refining|$110.0B|$23.93 → $47.13|+97%|+5.87%p|12/0|+56%|-21%|예|", doc)
        self.assertIn("**Refining** 3곳", doc)


if __name__ == "__main__":
    unittest.main()
