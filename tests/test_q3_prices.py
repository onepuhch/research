"""Q3: fixed outcome starts per definition, and the budgeted candidate price queue. Fake Yahoo only."""
import io
import json
import pathlib
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest import mock
from urllib.error import HTTPError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common as c  # noqa: E402
import candidate_alerts as a  # noqa: E402
import discovery_timing as t  # noqa: E402
import market_calendar  # noqa: E402
from test_candidates import row  # noqa: E402
from test_p2_material import MaterialFixture  # noqa: E402
from test_p3_timing import closes  # noqa: E402


def chart(symbol, start, end, value=10.0, currency="USD"):
    """A Yahoo chart payload with one bar per regular session from start to end (session-open stamps)."""
    stamps, adj, day = [], [], date.fromisoformat(start)
    while day <= date.fromisoformat(end):
        close = market_calendar.close_time(day)
        if close:
            hour = 13 if close.hour in (17, 20) else 14
            stamps.append(int(datetime(day.year, day.month, day.day, hour, 30, tzinfo=timezone.utc).timestamp()))
            adj.append(value)
            value += 0.1
        day += timedelta(days=1)
    return {"chart": {"result": [{"meta": {"symbol": symbol, "currency": currency}, "timestamp": stamps,
                                  "indicators": {"adjclose": [{"adjclose": adj}]}}]}}


class OutcomeDefinitionTest(unittest.TestCase):
    def test_population_start_stays_and_card_and_alert_have_their_own(self):
        rec = {"ticker": "AAA", "first_pass": {"observed_at": "2026-09-25T01:00:00+00:00"}, "first_card": None,
               "first_alert": None}
        batch = {"retrieved_at": "2027-05-01T00:00:00+00:00",
                 "series": {"AAA": closes("2026-09-20", 220), "SPY": closes("2026-09-20", 220)}}
        before = t.outcomes(rec, batch)[30]
        self.assertEqual(t.outcomes(rec, batch, "card")[30]["status"], "대표 카드 없음")
        rec["first_card"] = {"observed_at": "2026-10-05T01:00:00+00:00"}  # a later card entry
        rec["first_alert"] = {"at": "2026-10-06T06:00:00+00:00", "status": "uncertain"}
        self.assertEqual(t.outcomes(rec, batch)[30], before)  # population start fixed at 9/25
        self.assertEqual(t.outcomes(rec, batch, "card")[30]["start"], "2026-10-05")
        self.assertEqual(t.outcomes(rec, batch, "alert")[30]["status"], "알림 영수증 없음")  # uncertain is no receipt
        rec["first_alert"]["status"] = "sent"
        self.assertEqual(t.outcomes(rec, batch, "alert")[30]["start"], "2026-10-06")

    def test_each_ticker_reads_its_latest_whole_batch_with_spy(self):
        one = {"retrieved_at": "2026-10-06T00:00:00+00:00", "series": {"AAA": {"x": 1}, "SPY": {"x": 1}}}
        two = {"retrieved_at": "2026-10-07T00:00:00+00:00", "series": {"BBB": {"x": 1}, "SPY": {"x": 1}}}
        three = {"retrieved_at": "2026-10-08T00:00:00+00:00", "series": {"AAA": {"x": 2}}, "failures": [{"ticker": "SPY"}]}
        batches = [one, two, three]
        self.assertIs(t.batch_for("AAA", batches), one)  # the newer one has no SPY: never mixed
        self.assertIs(t.batch_for("BBB", batches), two)
        self.assertIsNone(t.batch_for("CCC", batches))


class PriceQueueTest(MaterialFixture):
    def setUp(self):
        super().setUp()
        c.atomic_json(a.ledger_path(), {"events": {}, "bootstrap": None})
        self.calls = []
        self.answers = {}

    def fetch(self, url, timeout):
        symbol = url.split("/chart/")[1].split("?")[0]
        self.calls.append(symbol)
        answer = self.answers.get(symbol, "ok")
        if isinstance(answer, int):
            raise HTTPError(url, answer, "x", {}, io.BytesIO(b""))
        if answer == "other":
            return chart("OTHER", "2026-09-01", "2026-10-09")
        return chart(symbol, "2026-09-01", "2026-10-09")

    def collect(self, when="2026-10-10T03:00:00+00:00", clock=None):
        return t.collect_prices(datetime.fromisoformat(when), fetch=self.fetch, sleep=lambda s: None,
                                clock=clock or (lambda: 0.0))

    def build(self, n=25):
        tickers = [f"T{i:02d}" for i in range(n)]
        self.write_snapshot("2026-10-01", [row(x) for x in tickers], top=tickers[:3])  # 3 cards, the rest outside
        t.update(datetime.fromisoformat("2026-10-01T10:00:00+00:00"))
        return tickers

    def test_twenty_requests_a_day_spy_included_card_companies_first(self):
        tickers = self.build()
        report = self.collect()
        self.assertEqual((report["requests"], report["stopped"]), (20, "daily_requests"))
        self.assertEqual(self.calls[0], "SPY")
        self.assertEqual(self.calls[1:4], tickers[:3])  # card experience first
        self.assertEqual(self.collect()["stopped"], "daily_requests")  # a rerun the same day sends nothing
        self.assertEqual(len(self.calls), 20)
        self.collect("2026-10-11T03:00:00+00:00")
        self.assertEqual(self.calls[20], "SPY")
        self.assertEqual(self.calls[21:27], tickers[19:25])  # the rest the next day, in order
        summary = t.price_summary(t.load(), t.price_batches())
        self.assertEqual((summary["targets"], summary["held"]), (25, 25))

    def test_429_and_two_server_errors_stop_the_day(self):
        self.build(5)
        self.answers = {"T00": 429}
        self.assertEqual(self.collect()["stopped"], "rate_limited")
        self.assertEqual(self.calls, ["SPY", "T00"])
        self.calls.clear()
        self.answers = {"T00": 503, "T01": 502}
        self.assertEqual(self.collect("2026-10-11T03:00:00+00:00")["stopped"], "server_errors")
        self.assertEqual(self.calls, ["SPY", "T00", "T01"])

    def test_time_budget_and_identity_mismatch(self):
        self.build(5)
        ticks = iter([0, 0, 0, 50, 100, 200, 300])
        report = self.collect(clock=lambda: next(ticks))
        self.assertEqual(report["stopped"], "time_budget")
        self.calls.clear()
        self.answers = {"T03": "other"}  # T00..T02 were collected before the time ran out
        self.collect("2026-10-11T03:00:00+00:00")
        self.assertEqual(self.calls, ["SPY", "T03", "T04"])
        batch = t.price_batches()[-1]
        self.assertNotIn("T03", batch["series"])
        self.assertIn({"ticker": "T03", "error_type": "ValueError"}, batch["failures"])

    def test_new_entrants_queue_behind_and_departed_stay(self):
        self.build(3)
        self.write_snapshot("2026-10-02", [row("NEW")], top=["NEW"])
        t.update(datetime.fromisoformat("2026-10-02T10:00:00+00:00"))
        queue = t.price_queue(t.load(), c.read_json(t.queue_path(), {"order": []}))
        self.assertEqual(queue, ["T00", "T01", "T02", "NEW"])
        self.collect()
        self.assertEqual(self.calls, ["SPY", "T00", "T01", "T02", "NEW"])  # T00..T02 left the list but stay

    def test_collected_tickers_wait_until_an_evaluation_end_is_confirmed(self):
        self.build(2)
        self.collect()
        self.calls.clear()
        self.assertEqual(self.collect("2026-10-12T03:00:00+00:00")["stopped"], "nothing_due")
        self.assertEqual(self.calls, [])
        self.collect("2026-11-04T03:00:00+00:00")  # the 30-day end (11/2 session) closed since the last batch
        self.assertEqual(self.calls, ["SPY", "T00", "T01"])


if __name__ == "__main__":
    unittest.main()
