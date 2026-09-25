import contextlib
import io
import json
import pathlib
import socket
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common as c  # noqa: E402
import candidates as k  # noqa: E402
import candidate_alerts as a  # noqa: E402
import notify  # noqa: E402
from test_candidates import REF, build, row, snapshot  # noqa: E402

ODD = "2026-09-26"   # date ordinal odd: screen channel first
EVEN = "2026-09-27"  # the next day, news channel first
assert date.fromisoformat(EVEN).toordinal() % 2 == 0 and date.fromisoformat(ODD).toordinal() % 2 == 1


def signal(i, **fields):
    base = {"signal_id": f"SIG-{i:04d}", "날짜": c.today(), "published_at": c.today(), "종목/티커": f"N{i}",
            "entity_id": f"CIK:{i:010d}", "테마": "AI interconnect", "단계 추정": "초기",
            "출처URL": "https://example.org/filing", "신호유형": "수주/백로그", "특이값 요약": "Verified orders",
            "티어": "B", "upside_score": str(9 - i), "data_quality": "live", "evidence_quote": "Backlog grew.",
            "event_state": "realized", "source_role": "candidate", "signal_direction": "positive"}
    base.update(fields)
    return base


def screen_rows(*tickers):
    return [row(t) for t in tickers]


class AlertTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data = pathlib.Path(tmp.name)
        for patch in (mock.patch.object(c, "DATA_DIR", self.data),
                      mock.patch.object(notify, "STATE_PATH", self.data / "notify_state.json"),
                      mock.patch.object(c, "load_dotenv_value", return_value="fake"),
                      contextlib.redirect_stdout(io.StringIO())):
            patch.__enter__()
            self.addCleanup(patch.__exit__, None, None, None)
        self.sent = []
        self.outcomes = []
        self.day = ODD
        self.patch_day()

    def patch_day(self):
        patch = mock.patch.object(c, "today", side_effect=lambda: self.day)
        patch.start()
        self.addCleanup(patch.stop)

    def fake_deliver(self, token, chat, text):
        status = self.outcomes.pop(0) if self.outcomes else "sent"
        if status == "sent":
            self.sent.append(text)
        return notify.Delivery(status, 100 + len(self.sent) if status == "sent" else None,
                               None if status == "sent" else "x")

    def index(self, tickers=("AAA", "BBB", "CCC", "DDD"), **snap):
        rows = screen_rows(*tickers)
        cands = build(snapshot(rows=rows, top_yield=list(tickers), top_growth=[], **snap))
        index = {"observed_at": "2026-09-25T01:23:02+00:00", "run_status": snap.get("status", "success"),
                 "stale": [], "source_snapshot": REF, "candidates": cands}
        c.atomic_json(k.index_path(), index)
        return index

    def news(self, count):
        c.write_rows("signal_log", [signal(i) for i in range(count)])

    def send_alerts(self, dry=False):
        with mock.patch.object(notify, "deliver", side_effect=self.fake_deliver) as deliver:
            code = a.main(["--dry-run"] if dry else [])
        return code, deliver.call_count

    def ledger(self):
        return json.loads((self.data / "candidate_alerts.json").read_text(encoding="utf-8"))


class BudgetAndOrderTest(AlertTest):
    def test_news_and_screen_share_three_per_day_and_the_first_channel_alternates(self):
        self.ledger_seed()
        self.index()
        self.news(3)
        self.assertEqual(self.send_alerts(), (0, 3))
        channels = [e["channel"] for e in sorted(self.ledger()["events"].values(), key=lambda e: e["attempts"][0]["at"])]
        self.assertEqual(channels, ["screen", "news", "screen"])  # odd day: screen first
        self.assertEqual(self.send_alerts(), (0, 0))  # budget used
        self.day = EVEN
        self.assertEqual(self.send_alerts()[1], 3)
        today = [e["channel"] for e in self.ledger()["events"].values() if e["day"] == EVEN]
        self.assertEqual(today, ["news", "screen", "news"])

    def ledger_seed(self):
        # Skip the bootstrap limit: an earlier run already stored the (empty) initial set.
        c.atomic_json(a.ledger_path(), {"events": {}, "bootstrap": {"date": "2026-09-01", "keys": []}})

    def test_empty_channel_leaves_its_slots_to_the_other(self):
        self.ledger_seed()
        self.index()
        self.assertEqual(self.send_alerts()[1], 3)
        self.assertTrue(all(e["channel"] == "screen" for e in self.ledger()["events"].values()))

    def test_legacy_news_sent_today_counts_against_the_budget(self):
        self.ledger_seed()
        self.index()
        c.atomic_json(notify.STATE_PATH, {"pushed": ["SIG-9"], "sent": {"SIG-9": {"date": ODD, "kind": "candidate"},
                                                                       "SIG-8": {"date": ODD, "kind": "risk"}}})
        self.assertEqual(self.send_alerts()[1], 2)

    def test_same_company_is_alerted_once_a_day_across_channels(self):
        self.ledger_seed()
        self.index(tickers=("AAA",))
        c.write_rows("signal_log", [signal(0, entity_id="NASDAQ:AAA", **{"종목/티커": "AAA"})])
        self.assertEqual(self.send_alerts()[1], 1)

    def test_recommended_goes_first_and_once_per_approved_version(self):
        self.ledger_seed()
        idx = self.index(tickers=("AAA", "BBB"))
        rec = idx["candidates"][1]
        rec.update(classification="recommended", approval={"candidate_version": rec["candidate_version"]})
        c.atomic_json(k.index_path(), idx)
        self.news(3)
        self.send_alerts()
        first = min(self.ledger()["events"].values(), key=lambda e: e["attempts"][0]["at"])
        self.assertEqual((first["event"], first["candidate_id"]), ("recommendation", rec["candidate_id"]))
        self.day = EVEN
        self.send_alerts()
        recs = [e for e in self.ledger()["events"].values() if e["event"] == "recommendation"]
        self.assertEqual(len(recs), 1)

    def test_rank_or_version_change_does_not_realert(self):
        self.ledger_seed()
        self.index(tickers=("AAA",))
        self.send_alerts()
        self.day = EVEN
        rows = [row("AAA", eps_now=3.0, eps_target_period="2028-12-31")]
        cands = build(snapshot(rows=rows, top_yield=["AAA"], top_growth=[]))
        c.atomic_json(k.index_path(), {"run_status": "success", "stale": [], "candidates": cands})
        self.assertEqual(self.send_alerts()[1], 0)

    def test_stale_partial_or_incomplete_candidates_are_not_alerted(self):
        self.ledger_seed()
        idx = self.index(tickers=("AAA",))
        for change in ({"stale": ["latest_attempt_failed"]}, {"run_status": "degraded"}):
            c.atomic_json(k.index_path(), {**idx, **change})
            self.assertEqual(self.send_alerts()[1], 0)
        cands = build(snapshot(rows=[row("AAA", price_status="unavailable", price_note="no_prices")],
                               top_yield=["AAA"], top_growth=[]))
        c.atomic_json(k.index_path(), {**idx, "candidates": cands})
        self.assertEqual(self.send_alerts()[1], 0)


class BootstrapTest(AlertTest):
    def test_first_run_sends_at_most_bootstrap_max_and_remembers_the_rest(self):
        self.index()
        self.assertEqual(self.send_alerts()[1], 1)
        ledger = self.ledger()
        self.assertEqual(len(ledger["bootstrap"]["keys"]), 3)
        self.day = EVEN
        self.assertEqual(self.send_alerts()[1], 0)  # the initial list is not "new" tomorrow
        self.index(tickers=("AAA", "BBB", "CCC", "DDD", "EEE"))
        self.assertEqual(self.send_alerts()[1], 1)
        self.assertIn("EEE", self.sent[-1])


class DeliveryLedgerTest(AlertTest):
    def setUp(self):
        super().setUp()
        c.atomic_json(a.ledger_path(), {"events": {}, "bootstrap": {"date": "2026-09-01", "keys": []}})
        self.index(tickers=("AAA",))

    def event(self):
        return next(iter(self.ledger()["events"].values()))

    def test_confirmed_failure_is_retried_as_the_same_event(self):
        self.outcomes = ["failed"]
        self.assertEqual(self.send_alerts(), (1, 1))
        self.assertEqual(self.event()["status"], "failed")
        self.assertEqual(self.send_alerts(), (0, 1))
        event = self.event()
        self.assertEqual((event["status"], len(self.ledger()["events"]), len(event["attempts"])), ("sent", 1, 2))
        self.assertEqual(event["message_id"], 101)

    def test_uncertain_is_never_resent_and_counts_toward_the_day(self):
        self.outcomes = ["uncertain"]
        self.assertEqual(self.send_alerts(), (0, 1))
        self.day = EVEN
        self.assertEqual(self.send_alerts()[1], 0)
        self.assertEqual(a.used_today(self.ledger(), notify.load_state(), ODD), 1)

    def test_crash_after_reserving_is_not_resent(self):
        with mock.patch.object(notify, "deliver", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                a.main([])
        self.assertEqual(self.event()["status"], "reserved")
        self.assertEqual(self.send_alerts()[1], 0)

    def test_dry_run_sends_and_writes_nothing(self):
        before = (self.data / "candidate_alerts.json").read_bytes()
        files = sorted(p.name for p in self.data.rglob("*"))
        self.assertEqual(self.send_alerts(dry=True), (0, 0))
        self.assertEqual((self.data / "candidate_alerts.json").read_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.data.rglob("*")), files)

    def test_message_wording_and_commands(self):
        self.send_alerts()
        text = self.sent[0]
        for word in ("매수", "목표가", "상승 확률", "저평가"):
            self.assertNotIn(word, text)
        cid = self.event()["candidate_id"]
        self.assertIn(f"/candidate {cid}", text)
        self.assertIn(f"/track {cid}", text)
        self.assertIn("핵심 미확인", text)


class DeliverClassificationTest(unittest.TestCase):
    def outcome(self, effect=None, body=None):
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = body or b""
        with mock.patch.object(notify, "urlopen", side_effect=effect, return_value=response), \
                mock.patch.object(c, "record_run"):
            return notify.deliver("t", "c", "m")

    def test_statuses(self):
        self.assertEqual(self.outcome(HTTPError("u", 400, "bad", {}, None)).status, "failed")
        self.assertEqual(self.outcome(HTTPError("u", 502, "bad", {}, None)).status, "uncertain")
        self.assertEqual(self.outcome(URLError(socket.timeout("t"))).status, "uncertain")
        self.assertEqual(self.outcome(URLError(ConnectionRefusedError())).status, "failed")
        self.assertEqual(self.outcome(TimeoutError()).status, "uncertain")
        self.assertEqual(self.outcome(body=b"not json").status, "uncertain")
        self.assertEqual(self.outcome(body=b'{"ok": false, "description": "chat not found"}').status, "failed")
        sent = self.outcome(body=b'{"ok": true, "result": {"message_id": 42}}')
        self.assertEqual((sent.status, sent.message_id), ("sent", 42))


class RiskIndependenceTest(AlertTest):
    def test_risk_alerts_still_go_when_candidate_alerts_cannot_run(self):
        (self.data / "candidate_alerts.json").write_text("broken", encoding="utf-8")
        self.assertEqual(a.main([]), 1)
        import promote
        c.write_rows("signal_log", [signal(0)])
        promote.promote_signal(signal(0))
        c.write_rows("signal_log", [signal(1, entity_id="CIK:0000000000", signal_direction="negative", 티어="관망")])
        with mock.patch.object(notify, "deliver", side_effect=self.fake_deliver):
            self.assertEqual(notify.main(["notify"]), 0)
        self.assertEqual(len(self.sent), 1)


if __name__ == "__main__":
    unittest.main()
