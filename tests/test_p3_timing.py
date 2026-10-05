"""P3: fixed first-discovery records, retrospective/prospective, latency and outcome states."""
import json
import pathlib
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common as c  # noqa: E402
import candidate_alerts as a  # noqa: E402
import discovery_timing as t  # noqa: E402
import research_returns  # noqa: E402
from test_candidates import row  # noqa: E402
from test_p2_material import BOOT_DAY, MaterialFixture  # noqa: E402

KEY = "NASDAQ:AAA|eps-revision-review:v1"


def closes(start: str, days: int, value=10.0, step=0.1) -> dict:
    """Adjusted closes on regular sessions from start for 'days' calendar days."""
    import market_calendar
    out, day, price = {}, datetime.fromisoformat(start).date(), value
    for _ in range(days):
        close = market_calendar.close_time(day)
        if close:
            out[day.isoformat()] = {"adjusted_close": round(price, 4), "closed_at": close.isoformat()}
            price += step
        day += timedelta(days=1)
    return out


class TimingTest(MaterialFixture):
    def setUp(self):
        super().setUp()
        c.atomic_json(a.ledger_path(), {"events": {}, "bootstrap": None})

    def update(self, when):
        return t.update(datetime.fromisoformat(when))

    def records(self):
        return json.loads(t.store_path().read_text(encoding="utf-8"))["records"]

    def test_first_values_never_move(self):
        self.write_snapshot("2026-10-01", [row("AAA", eps_now=1.0)])
        self.update("2026-10-01T10:00:00+00:00")
        first = self.records()[KEY]["first_pass"]
        self.update("2026-10-01T11:00:00+00:00")  # a re-run or re-render adds nothing
        self.assertEqual(self.records()[KEY]["passes"], 1)
        self.write_snapshot("2026-10-02", [row("AAA", eps_now=1.5, by_yield=False, by_growth=False)], top=["ZZZ"])
        self.update("2026-10-02T10:00:00+00:00")
        rec = self.records()[KEY]
        self.assertEqual(rec["first_pass"], first)
        self.assertEqual(rec["first_pass"]["eps"]["eps_now"], 1.0)  # never the later value
        self.assertEqual((rec["last_pass"]["eps"]["eps_now"], rec["last_pass"]["state"], rec["passes"]), (1.5, "outside", 2))
        self.assertEqual(t.own_eps_change(rec)["pct"], 50.0)

    def test_archive_rebuild_is_retrospective_and_later_records_prospective(self):
        self.write_snapshot("2026-09-30", [row("AAA")])
        self.update("2026-10-01T00:00:00+00:00")
        self.write_snapshot("2026-10-02", [row("AAA"), row("BBB")])
        self.update("2026-10-02T10:00:00+00:00")
        recs = self.records()
        self.assertEqual(recs[KEY]["mode"], "retrospective")
        self.assertEqual(recs["NASDAQ:BBB|eps-revision-review:v1"]["mode"], "prospective")

    def test_departed_and_outside_companies_stay_in_the_population(self):
        self.write_snapshot("2026-10-01", [row("AAA"), row("BBB")], top=["AAA"])
        self.update("2026-10-01T10:00:00+00:00")
        self.write_snapshot("2026-10-02", [row("BBB")], top=["BBB"])
        self.update("2026-10-02T10:00:00+00:00")
        recs = self.records()
        self.assertIn(KEY, recs)
        bbb = recs["NASDAQ:BBB|eps-revision-review:v1"]
        self.assertEqual((bbb["first_pass"]["state"], bbb["first_card"]["observed_at"][:10]), ("outside", "2026-10-02"))
        self.assertAlmostEqual(t.latencies(bbb)["pass_to_card_h"], 24.0)

    def test_failed_screen_or_snapshot_without_time_is_not_an_observation(self):
        self.write_snapshot("2026-10-01", [row("AAA")])
        path = sorted((self.data / "revision_screen").glob("*.json.gz"))[-1]
        import gzip
        snap = json.loads(gzip.decompress(path.read_bytes()))
        snap["run"]["status"] = "failed"
        path.write_bytes(gzip.compress(json.dumps(snap).encode("utf-8")))
        self.update("2026-10-01T10:00:00+00:00")
        self.assertEqual(self.records(), {})

    def test_alert_receipt_bootstrap_and_evidence_slots(self):
        self.write_snapshot("2026-10-01", [row("AAA"), row("BBB")])
        ledger = {"events": {a.logical_key("NASDAQ:AAA", "t", a.NEW): {
            "channel": "screen", "event": a.NEW, "entity_id": "NASDAQ:AAA", "status": "sent", "day": "2026-10-01",
            "attempts": [{"at": "2026-10-01T03:00:00+00:00", "status": "sent", "message_id": 7}]}},
            "bootstrap": {"date": BOOT_DAY, "keys": ["NASDAQ:BBB|t|new_discovery"]}}
        c.atomic_json(a.ledger_path(), ledger)
        self.update("2026-10-01T10:00:00+00:00")
        recs = self.records()
        self.assertEqual(recs[KEY]["first_alert"]["message_id"], 7)
        self.assertAlmostEqual(t.latencies(recs[KEY])["card_to_alert_h"], 3 - (1 + 23 / 60 + 2 / 3600), places=3)
        self.assertEqual(recs["NASDAQ:BBB|eps-revision-review:v1"]["bootstrap"]["date"], BOOT_DAY)
        self.assertIsNone(recs[KEY]["first_evidence"])  # unknown stays null

    def test_outcome_uses_the_existing_return_definition_from_the_first_card(self):
        self.write_snapshot("2026-10-01", [row("AAA")])
        self.update("2026-10-01T10:00:00+00:00")
        rec = self.records()[KEY]
        batch = {"retrieved_at": "2027-05-01T00:00:00+00:00",
                 "series": {"AAA": closes("2026-09-20", 220), "SPY": closes("2026-09-20", 220, 100.0, 0.05)}}
        result = t.outcomes(rec, batch)
        expected = research_returns.compare({"ticker": "AAA", "captured_at": rec["first_card"]["observed_at"]},
                                            batch["series"]["AAA"], batch["series"]["SPY"], batch["retrieved_at"], 30)
        self.assertEqual({k: v for k, v in result[30].items() if k != "outcome_definition"}, expected)
        self.assertEqual(result[30]["start"], "2026-10-01")  # first close after 01:23Z, never an earlier one
        self.assertEqual(result[30]["status"], "평가")
        self.assertAlmostEqual(result[30]["net_pct"], result[30]["gross_pct"] - 0.20)

    def test_missing_price_pending_horizon_and_missing_start_are_different_states(self):
        self.write_snapshot("2026-10-01", [row("AAA")])
        self.update("2026-10-01T10:00:00+00:00")
        rec = self.records()[KEY]
        self.assertEqual(t.outcomes(rec, {"retrieved_at": "2026-10-10T00:00:00+00:00", "series": {}})[30]["status"],
                         t.PRICE_MISSING)
        self.assertEqual(t.outcomes(rec, None)[90]["status"], t.PRICE_MISSING)
        early = {"retrieved_at": "2026-10-10T00:00:00+00:00",
                 "series": {"AAA": closes("2026-09-28", 12), "SPY": closes("2026-09-28", 12)}}
        self.assertEqual(t.outcomes(rec, early)[30]["status"], "평가일 대기")
        gap = {"retrieved_at": "2026-10-10T00:00:00+00:00",
               "series": {"AAA": closes("2026-10-05", 5), "SPY": closes("2026-09-28", 12)}}
        self.assertEqual(t.outcomes(rec, gap)[30]["status"], "기준일 종목 자료 부족")

    def test_report_shows_counts_and_no_hit_rate(self):
        self.write_snapshot("2026-10-01", [row("AAA")])
        self.update("2026-10-01T10:00:00+00:00")
        text = t.render()
        self.assertIn("기업 1곳 (사후 1, 전향 0", text)
        self.assertIn("시세 미수집 1", text)
        self.assertNotIn("적중률:", text)

    def test_broken_store_is_not_replaced_by_an_empty_one(self):
        t.store_path().write_text(json.dumps({"records": []}), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.update("2026-10-01T10:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
