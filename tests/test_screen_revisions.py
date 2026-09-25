import gzip
import json
import math
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import screen_revisions as sr  # noqa: E402

CFG = {**sr.DEFAULTS, "workers": 1, "min_interval_s": 0.0, "max_interval_s": 1.0,
       "retry_waits_s": [2, 8], "retry_cooldown_s": 30, "time_budget_s": 10_000}
NOW = datetime(2026, 9, 25, 0, 0, tzinfo=timezone.utc).timestamp()


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, seconds):
        if seconds > 0:
            self.t += seconds


def earnings_payload(symbol, cur=6.39, d30=6.0, d90=4.21, analysts=8, currency="USD", end="2027-12-31",
                     price=360.0, price_symbol=None):
    return {"quoteSummary": {"error": None, "result": [{
        "price": {"symbol": price_symbol or symbol, "currency": "USD", "regularMarketPrice": {"raw": price},
                  "regularMarketTime": {"raw": int(NOW)}},
        "earningsTrend": {"trend": [{
            "period": "+1y", "endDate": end,
            "earningsEstimate": {"numberOfAnalysts": {"raw": analysts}, "earningsCurrency": currency},
            "epsTrend": {"current": {"raw": cur}, "7daysAgo": {"raw": cur}, "30daysAgo": {"raw": d30},
                         "60daysAgo": {"raw": (d30 + d90) / 2}, "90daysAgo": {"raw": d90},
                         "epsTrendCurrency": currency},
            "epsRevisions": {"upLast30days": {"raw": 5}, "downLast30days": {"raw": 0}}}]}}]}}


def chart_payload(symbol, start_close=100.0, end_close=110.0, split=False, as_of=NOW):
    day = 86400
    stamps = [int(as_of - 120 * day), int(as_of - 95 * day), int(as_of - 30 * day), int(as_of - day)]
    closes = [start_close, start_close, (start_close + end_close) / 2, end_close]
    events = {"splits": {str(stamps[2]): {"date": stamps[2], "numerator": 2, "denominator": 1}}} if split else {}
    return {"chart": {"error": None, "result": [{
        "meta": {"symbol": symbol, "currency": "USD"}, "timestamp": stamps, "events": events,
        "indicators": {"quote": [{"close": closes}], "adjclose": [{"adjclose": [c * 0.99 for c in closes]}]}}]}}


class FakeTransport:
    """Routes Yahoo URLs; a route returns (status, dict|bytes, headers) or a list consumed per call."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, url, headers):
        self.calls.append(url)
        if "fc.yahoo.com" in url:
            return 404, b"", {}
        if "getcrumb" in url:
            return 200, b"crumb123", {}
        for key, route in self.routes.items():
            if key in url:
                response = route.pop(0) if isinstance(route, list) else route
                if callable(response):
                    response = response(url)
                status, body, hdrs = response
                if isinstance(body, dict):
                    body = json.dumps(body).encode()
                return status, body, hdrs
        return 404, json.dumps({"quoteSummary": {"result": None, "error": {"code": "Not Found"}}}).encode(), {}

    def count(self, fragment):
        return sum(1 for u in self.calls if fragment in u)


def make_yahoo(routes, cfg=None):
    clock = FakeClock()
    transport = FakeTransport(routes)
    return sr.Yahoo(cfg or CFG, clock=clock, transport=transport, jitter=lambda: 0.0), transport, clock


def source_for(symbol, **kw):
    payload = earnings_payload(symbol, **kw)
    return sr.extract_source(payload["quoteSummary"]["result"][0], "2026-09-25T00:00:00+00:00")


class HttpLayerTest(unittest.TestCase):
    def test_429_then_success_retries_and_slows_pacing(self):
        y, t, clock = make_yahoo({"quoteSummary/AAA": [(429, b"", {"Retry-After": "5"}),
                                                       (200, earnings_payload("AAA"), {})]})
        result = sr.run_stage(["AAA"], lambda s: y.summary(s, "earningsTrend,price"), 1, y, 30)
        self.assertEqual(result["AAA"]["status"], "success")
        self.assertEqual(result["AAA"]["attempts"], 2)
        self.assertGreater(y.pacer.interval, CFG["min_interval_s"])
        self.assertGreaterEqual(clock.t, 5)

    def test_persistent_403_refreshes_once_then_blocks_the_stage(self):
        y, t, _ = make_yahoo({"quoteSummary/": (403, b"", {})})
        result = sr.run_stage(["AAA", "BBB", "CCC"], lambda s: y.summary(s, "assetProfile"), 1, y, 30)
        self.assertEqual(result["AAA"]["status"], "failed")
        self.assertEqual(result["AAA"]["http_status"], 403)
        self.assertEqual([result[s]["status"] for s in ("BBB", "CCC")], ["not_attempted"] * 2)
        self.assertEqual(result["BBB"]["reason"], "stage_blocked")
        self.assertEqual(t.count("getcrumb"), 2)  # initial session + one refresh

    def test_time_budget_marks_rest_not_attempted(self):
        cfg = {**CFG, "time_budget_s": 5, "min_interval_s": 3.0}
        y, _, _ = make_yahoo({"quoteSummary/": (200, earnings_payload("X"), {})}, cfg)
        result = sr.run_stage(["A1", "A2", "A3", "A4"], lambda s: y.summary(s, "earningsTrend"), 1, y, 30)
        stats = sr.stage_stats(result)
        self.assertGreater(stats["not_attempted"], 0)
        self.assertEqual(stats["requested"], sum(stats[k] for k in sr.OUTCOMES))

    def test_http_200_api_error_is_failed_and_not_found_is_unavailable(self):
        api_error = {"quoteSummary": {"result": None, "error": {"code": "Internal", "description": "x"}}}
        y, _, _ = make_yahoo({"quoteSummary/BAD": (200, api_error, {})})
        result = sr.run_stage(["BAD", "GONE"], lambda s: y.summary(s, "earningsTrend"), 1, y, 0)
        self.assertEqual((result["BAD"]["status"], result["BAD"]["reason"]), ("failed", "api_error"))
        self.assertEqual((result["GONE"]["status"], result["GONE"]["reason"]), ("unavailable", "not_found"))

    def test_only_failed_items_are_retried_after_cooldown(self):
        fails = [(503, b"", {})] * 3 + [(200, earnings_payload("BAD"), {})]
        y, t, _ = make_yahoo({"quoteSummary/OK": (200, earnings_payload("OK"), {}), "quoteSummary/BAD": fails})
        result = sr.run_stage(["OK", "BAD"], lambda s: y.summary(s, "earningsTrend,price"), 1, y, 30)
        self.assertEqual(result["BAD"]["status"], "success")
        self.assertEqual(result["BAD"]["attempts"], 4)
        self.assertEqual(t.count("quoteSummary/OK"), 1)

    def test_network_error_is_retried_then_reported_without_url(self):
        def boom(url, headers):
            raise TimeoutError("timed out: https://secret?crumb=crumb123")
        y, _, _ = make_yahoo({})
        y.transport = boom
        result = sr.run_stage(["AAA"], lambda s: y.summary(s, "earningsTrend"), 1, y, 0)
        self.assertEqual(result["AAA"]["status"], "failed")
        self.assertEqual(result["AAA"]["reason"], "TimeoutError")
        # max_attempts in the main pass, then once more as a failed item after the cooldown.
        self.assertEqual(result["AAA"]["attempts"], 2 * CFG["max_attempts"])
        self.assertNotIn("crumb", json.dumps(result))


class ScreenStageTest(unittest.TestCase):
    def quotes_route(self, symbols):
        def respond(url):
            return 200, {"quoteResponse": {"error": None, "result": [
                {"symbol": s, "quoteType": "EQUITY", "currency": "USD", "marketCap": 5e9, "epsForward": 1.0,
                 "regularMarketPrice": 360.0, "longName": s + " Inc"} for s in symbols]}}, {}
        return respond

    def test_profile_block_does_not_stop_price_comparison_and_is_degraded(self):
        universe = [{"ticker": "GRW", "symbol": "GRW", "name": "Grower"}]
        y, t, _ = make_yahoo({
            "/v7/finance/quote": self.quotes_route(["GRW"]),
            "modules=earningsTrend,price": (200, earnings_payload("GRW"), {}),
            "modules=assetProfile": (403, b"", {}),
            "/v8/finance/chart/GRW": (200, chart_payload("GRW"), {}),
        })
        with mock.patch.object(sr, "datetime", wraps=datetime) as dt:
            dt.now.return_value = datetime.fromtimestamp(NOW, timezone.utc)
            parts = sr.screen(CFG, universe, y)
        row = parts["derived"]["rows"][0]
        self.assertTrue(row["candidate"])
        self.assertIsNone(row.get("industry"))
        self.assertEqual(row["price_pct_90"], 10.0)
        self.assertEqual(parts["stages"]["profile"]["failed"], 1)
        stages = {"universe": {"success": 1}, "session": {"success": 1}, **parts["stages"]}
        self.assertEqual(sr.run_status(stages), "degraded")

    def test_analysts_below_minimum_is_unavailable_not_failed(self):
        universe = [{"ticker": "THIN", "symbol": "THIN", "name": "Thin"}]
        y, _, _ = make_yahoo({"/v7/finance/quote": self.quotes_route(["THIN"]),
                              "modules=earningsTrend,price": (200, earnings_payload("THIN", analysts=2), {})})
        parts = sr.screen(CFG, universe, y)
        self.assertEqual(parts["stages"]["earnings"]["unavailable"], 1)
        self.assertEqual(parts["stages"]["earnings"]["failed"], 0)
        self.assertEqual(parts["exclusions"], {"analysts_below_min": 1})

    def test_missing_symbol_in_quote_batch_is_unavailable(self):
        universe = [{"ticker": t, "symbol": t, "name": t} for t in ("AAA", "DEAD")]
        y, _, _ = make_yahoo({"/v7/finance/quote": self.quotes_route(["AAA"]),
                              "modules=earningsTrend,price": (200, earnings_payload("AAA"), {})})
        parts = sr.screen(CFG, universe, y)
        self.assertEqual(parts["stages"]["quotes"]["unavailable"], 1)
        self.assertEqual(parts["stages"]["quotes"]["success"], 1)

    def test_run_status_rules(self):
        ok = {"requested": 1, "success": 1, "unavailable": 0, "failed": 0, "not_attempted": 0}
        base = {"universe": ok, "session": ok, "quotes": ok, "earnings": ok, "profile": ok, "price": ok}
        self.assertEqual(sr.run_status(base), "success")
        self.assertEqual(sr.run_status({**base, "profile": {**ok, "success": 0, "failed": 1}}), "degraded")
        self.assertEqual(sr.run_status({**base, "earnings": {**ok, "success": 0, "failed": 1}}), "failed")
        self.assertEqual(sr.run_status({"universe": {**ok, "success": 0}}), "failed")
        unavailable_only = {**base, "earnings": {**ok, "success": 1, "unavailable": 5}}
        self.assertEqual(sr.run_status(unavailable_only), "success")


class EvaluateTest(unittest.TestCase):
    def test_expensive_grower_ranks_by_growth(self):
        row, reason = sr.evaluate("GRW", source_for("GRW"), CFG)
        self.assertEqual(reason, "")
        self.assertFalse(row["by_yield"])
        self.assertTrue(row["by_growth"])
        self.assertAlmostEqual(row["pct_90"], 51.8, places=1)
        self.assertEqual(row["eps_target_period"], "2027-12-31")
        self.assertEqual(row["eps_basis"], "provider-unspecified")

    def test_cyclical_ranks_by_yield(self):
        row, _ = sr.evaluate("CYC", source_for("CYC", cur=47.13, d30=40, d90=23.93, price=200), CFG)
        self.assertTrue(row["by_yield"])
        self.assertAlmostEqual(row["yield_change_90_pp"], 11.6, places=1)

    def test_definition_checks(self):
        cases = {
            "ticker_mismatch": source_for("AAA", price_symbol="BBB"),
            "eps_currency_missing": source_for("AAA", currency=None),
            "eps_currency_mismatch": source_for("AAA", currency="EUR"),
            "period_missing": source_for("AAA", end=None),
            "estimate_not_finite": source_for("AAA", cur=math.nan),
            "past_estimate_zero": source_for("AAA", d90=0.0),
            "analysts_below_min": source_for("AAA", analysts=2),
            "price_invalid": source_for("AAA", price=math.inf),
        }
        for expected, source in cases.items():
            with self.subTest(expected):
                symbol = "AAA"
                self.assertEqual(sr.evaluate(symbol, source, CFG), (None, expected))

    def test_threshold_uses_unrounded_value(self):
        # (cur - d90) / price * 100 = 0.99996: rounds to 1.000 but is below the 1.0 threshold.
        row, _ = sr.evaluate("EDGE", source_for("EDGE", cur=10.99996, d30=10.5, d90=10.0, price=100.0), CFG)
        self.assertEqual(row["yield_change_90_pp"], 1.0)
        self.assertFalse(row["by_yield"])

    def test_turnaround_uses_label_not_growth_rate(self):
        row, _ = sr.evaluate("TRN", source_for("TRN", cur=1.66, d30=1.0, d90=-0.04, price=20), CFG)
        self.assertIsNone(row["pct_90"])
        self.assertTrue(row["turnaround"])
        self.assertEqual(sr.change_label(row), "적자→흑자")

    def test_shrinking_loss_is_not_a_candidate(self):
        row, _ = sr.evaluate("BIO", source_for("BIO", cur=-1.06, d30=-1.2, d90=-1.65, price=3.0), CFG)
        self.assertFalse(row["candidate"])

    def test_tiny_base_growth_is_ignored(self):
        row, _ = sr.evaluate("TNY", source_for("TNY", cur=0.40, d30=0.3, d90=0.10, price=100), CFG)
        self.assertFalse(row["by_growth"])
        self.assertEqual(sr.change_label(row), "+300%")

    def test_requires_more_upgrades_than_downgrades_and_recent_rise(self):
        payload = earnings_payload("MIX")
        payload["quoteSummary"]["result"][0]["earningsTrend"]["trend"][0]["epsRevisions"] = {
            "upLast30days": {"raw": 2}, "downLast30days": {"raw": 2}}
        source = sr.extract_source(payload["quoteSummary"]["result"][0], "2026-09-25T00:00:00+00:00")
        self.assertFalse(sr.evaluate("MIX", source, CFG)[0]["candidate"])
        self.assertFalse(sr.evaluate("FLAT", source_for("FLAT", cur=5.9, d30=6.0), CFG)[0]["candidate"])

    def test_snapshot_payload_rescoring_matches(self):
        source = source_for("GRW")
        row, _ = sr.evaluate("GRW", source, CFG)
        stored = json.loads(json.dumps({"source": source, "row": row, "config": CFG}))
        again, _ = sr.evaluate("GRW", stored["source"], stored["config"])
        self.assertEqual(again, stored["row"])


class PriceComparisonTest(unittest.TestCase):
    def test_same_basis_closes_and_dates(self):
        chart = chart_payload("GRW")["chart"]["result"][0]
        result = sr.price_comparison(chart, "GRW", eps_now=2.0, eps_90d=1.0, as_of=NOW)
        self.assertEqual(result["price_pct_90"], 10.0)
        self.assertEqual(result["pe_change_pct"], -45.0)
        self.assertEqual(result["adj_return_pct_90"], 10.0)
        self.assertEqual(result["price_basis"], sr.PRICE_BASIS)
        self.assertLess(result["price_start_date"], result["price_end_date"])

    def test_split_in_window_leaves_pe_uncomputed(self):
        chart = chart_payload("SPL", split=True)["chart"]["result"][0]
        result = sr.price_comparison(chart, "SPL", 2.0, 1.0, NOW)
        self.assertIsNone(result["pe_change_pct"])
        self.assertEqual(result["price_note"], "split_in_window")
        self.assertEqual(result["price_pct_90"], 10.0)

    def test_mismatched_chart_and_loss_base(self):
        chart = chart_payload("OTHER")["chart"]["result"][0]
        self.assertEqual(sr.price_comparison(chart, "GRW", 2.0, 1.0, NOW)["price_note"], "chart_mismatch")
        chart = chart_payload("GRW")["chart"]["result"][0]
        self.assertIsNone(sr.price_comparison(chart, "GRW", 2.0, -1.0, NOW)["pe_change_pct"])


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [mock.patch.object(sr, "SCREEN_DIR", root / "revision_screen"),
                        mock.patch.object(sr, "DOC_PATH", root / "revision_screen.md")]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def snap(self, status, kst, rows=True):
        row = {"ticker": "GRW", "symbol": "GRW", "market_cap": 5e9, "eps_90d": 4.21, "eps_now": 6.39,
               "pct_90": 51.8, "yield_change_90_pp": 0.6, "up30": 5, "down30": 0, "steady": True,
               "by_yield": False, "by_growth": True, "candidate": True}
        return {"schema_version": 2, "run": {"status": status, "started_kst": kst},
                "stages": {"earnings": {"requested": 1, "success": 1 if rows else 0, "unavailable": 0,
                                        "failed": 0 if rows else 1, "not_attempted": 0}},
                "derived": {"rows": [row] if rows else [], "top_yield": [], "top_growth": ["GRW"] if rows else [],
                            "clusters": []}}

    def test_two_runs_same_day_keep_both_files_and_legacy_reads(self):
        legacy = sr.SCREEN_DIR / "2026-09-25.json.gz"
        sr.write_gz(legacy, {"meta": {"generated_kst": "2026-09-25 01:44"}, "rows": [], "top_yield": [],
                             "top_growth": [], "clusters": []})
        first = sr.SCREEN_DIR / "20260925T010000Z_1-1.json.gz"
        second = sr.SCREEN_DIR / "20260925T020000Z_2-1.json.gz"
        sr.write_gz(first, self.snap("success", "2026-09-25 10:00"))
        sr.write_gz(second, self.snap("degraded", "2026-09-25 11:00"))
        self.assertEqual([p.name for p in sr.snapshots()], [legacy.name, first.name, second.name])
        self.assertEqual(sr.load_snapshot(legacy)["run"]["status"], "legacy")

    def test_failed_latest_shows_previous_result_labeled_as_older(self):
        good = sr.SCREEN_DIR / "20260925T010000Z_1-1.json.gz"
        sr.write_gz(good, self.snap("success", "2026-09-25 10:00"))
        failed = self.snap("failed", "2026-09-26 10:00", rows=False)
        path = sr.SCREEN_DIR / "20260926T010000Z_2-1.json.gz"
        sr.write_gz(path, failed)
        sr.publish(failed, path)
        doc = sr.DOC_PATH.read_text(encoding="utf-8")
        self.assertIn("최신 시도: 2026-09-26 10:00 KST · 상태 **실패**", doc)
        self.assertIn("아래는 2026-09-25 10:00 KST 시도(정상)의 결과이며 오늘의 정상 결과가 아니다", doc)
        self.assertIn("|1|GRW|", doc)
        self.assertIn(good.name, doc)

    def test_degraded_doc_warns_and_marks_unknowns(self):
        snap = self.snap("degraded", "2026-09-25 10:00")
        snap["stages"]["profile"] = {"requested": 1, "success": 0, "unavailable": 0, "failed": 1, "not_attempted": 0}
        path = sr.SCREEN_DIR / "20260925T010000Z_1-1.json.gz"
        sr.write_gz(path, snap)
        sr.publish(snap, path)
        doc = sr.DOC_PATH.read_text(encoding="utf-8")
        self.assertIn("상태 **일부 누락**", doc)
        self.assertIn("업종 확인 0/1곳", doc)
        self.assertIn("|1|GRW|미확인|", doc)
        self.assertIn("완전 정상 결과 없음", doc)


class HelpersTest(unittest.TestCase):
    def test_industry_clusters_need_three(self):
        rows = [{"ticker": t, "industry": i} for t, i in
                [("MPC", "Refining"), ("VLO", "Refining"), ("PSX", "Refining"), ("NUE", "Steel"), ("CLF", "Steel")]]
        self.assertEqual(sr.industry_clusters(rows), [{"industry": "Refining", "count": 3, "tickers": ["MPC", "VLO", "PSX"]}])

    def test_probe_never_saves(self):
        with mock.patch.object(sr, "Yahoo", side_effect=sr.FetchError("blocked", "session_crumb_unavailable")), \
                mock.patch.object(sr, "write_gz") as write, mock.patch.object(sr.c, "record_run") as record, \
                mock.patch("builtins.print"):
            code = sr.main(["--tickers", "AAA"])
        self.assertEqual(code, 1)
        write.assert_not_called()
        record.assert_not_called()


if __name__ == "__main__":
    unittest.main()
