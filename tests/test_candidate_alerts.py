import contextlib
import io
import json
import os
import pathlib
import http.client
import socket
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from unittest import mock
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common as c  # noqa: E402
import candidates as k  # noqa: E402
import screen_revisions  # noqa: E402
import candidate_alerts as a  # noqa: E402
import notify  # noqa: E402
from test_candidates import REF, build, isolate_ci_environment, row, snapshot  # noqa: E402

REAL_PERSIST_REMOTE = a.persist_remote  # the fixtures replace the module attribute

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
        isolate_ci_environment(self)
        runs = iter(range(1, 1000))  # every alerts run is a separate CI run attempt
        patch = mock.patch.object(a, "attempt_id", side_effect=lambda: f"run-{next(runs)}")
        patch.start()
        self.addCleanup(patch.stop)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data = pathlib.Path(tmp.name)
        (self.data / "revision_screen").mkdir()
        for patch in (mock.patch.object(c, "DATA_DIR", self.data),
                      mock.patch.object(screen_revisions, "SCREEN_DIR", self.data / "revision_screen"),
                      # 'now' follows the test day, so freshness never depends on the real clock.
                      mock.patch.object(k, "now_utc", side_effect=lambda: datetime.fromisoformat(f"{self.day}T03:00:00+00:00")),
                      mock.patch.object(notify, "STATE_PATH", self.data / "notify_state.json"),
                      mock.patch.object(c, "load_dotenv_value", return_value="fake"),
                      contextlib.redirect_stdout(io.StringIO())):
            patch.__enter__()
            self.addCleanup(patch.__exit__, None, None, None)
        self.sent = []
        self.outcomes = []
        self.pushes = []        # ledger contents the (fake) remote received, in order
        self.push_results = []  # scripted push outcomes; default success
        patch = mock.patch.object(a, "persist_remote", side_effect=self.fake_persist)
        patch.start()
        self.addCleanup(patch.stop)
        self.day = ODD
        self.patch_day()

    def fake_persist(self, message):
        ok = self.push_results.pop(0) if self.push_results else True
        if ok:
            self.pushes.append((message, (self.data / "candidate_alerts.json").read_text(encoding="utf-8")))
        return ok

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
        index = {"observed_at": f"{self.day}T01:23:02+00:00", "run_status": snap.get("status", "success"),
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


class CooldownTest(AlertTest):
    """F3: dedupe before the daily cut, and a 14-day gap per company across channels."""

    def setUp(self):
        super().setUp()
        self.events = {}
        c.atomic_json(notify.STATE_PATH, {"pushed": [], "sent": {}})

    def seed(self, **extra):
        c.atomic_json(a.ledger_path(), {"events": self.events, "bootstrap": {"date": "2026-09-01", "keys": []}, **extra})

    def past(self, entity, day, channel="news", thesis="ai interconnect", event=a.NEW):
        self.events[a.logical_key(entity, thesis, event)] = {
            "channel": channel, "event": event, "entity_id": entity, "thesis_key": thesis,
            "day": day, "status": "sent", "attempts": []}

    def no_screen(self):
        c.atomic_json(k.index_path(), {"run_status": "success", "stale": [], "candidates": []})

    def test_top_three_known_events_do_not_hide_a_fourth_new_company(self):
        for i in range(3):
            self.past(f"CIK:{i:010d}", "2026-08-01")  # same company+thesis, new signal IDs today
        self.seed()
        self.no_screen()
        self.news(4)
        self.send_alerts()
        sent = [e for e in self.ledger()["events"].values() if e["day"] == ODD]
        self.assertEqual([e["entity_id"] for e in sent], ["CIK:0000000003"])

    def at(self, day, delta):
        return (date.fromisoformat(day) + timedelta(days=delta)).isoformat()

    def test_news_then_screen_waits_14_days(self):
        self.past("NASDAQ:AAA", self.at(ODD, -13))
        self.seed()
        self.index(tickers=("AAA",))
        self.assertEqual(self.send_alerts()[1], 0)  # 13 days: too soon
        self.events = {}
        self.past("NASDAQ:AAA", self.at(ODD, -14))
        self.seed()
        self.assertEqual(self.send_alerts()[1], 1)  # 14 days: another thesis may be announced

    def test_screen_then_news_waits_14_days(self):
        self.past("NASDAQ:AAA", self.at(ODD, -13), channel="screen", thesis=k.THESIS_KEY)
        self.seed()
        self.no_screen()
        c.write_rows("signal_log", [signal(0, entity_id="NASDAQ:AAA", **{"종목/티커": "AAA"})])
        self.assertEqual(self.send_alerts()[1], 0)
        self.events = {}
        self.past("NASDAQ:AAA", self.at(ODD, -14), channel="screen", thesis=k.THESIS_KEY)
        self.seed()
        self.assertEqual(self.send_alerts()[1], 1)

    def test_same_event_is_never_resent_even_after_the_gap(self):
        self.past("NASDAQ:AAA", "2026-01-01", channel="screen", thesis=k.THESIS_KEY)
        self.seed()
        self.index(tickers=("AAA",))
        self.assertEqual(self.send_alerts()[1], 0)

    def test_registry_mapping_joins_cik_and_exchange_ticker(self):
        self.past("NASDAQ:CRDO", self.at(ODD, -3), channel="screen", thesis=k.THESIS_KEY)
        self.seed()
        self.no_screen()
        c.write_rows("signal_log", [signal(0, entity_id="CIK:0001807794", **{"종목/티커": "CRDO"})])
        self.assertEqual(self.send_alerts()[1], 0)

    def test_approved_recommendation_skips_the_gap_but_not_one_per_day(self):
        self.past("NASDAQ:BBB", self.at(ODD, -3), channel="screen", thesis=k.THESIS_KEY)
        self.seed()
        idx = self.index(tickers=("AAA", "BBB"))
        rec = idx["candidates"][1]
        rec.update(classification="recommended", approval={"candidate_version": rec["candidate_version"]})
        c.atomic_json(k.index_path(), idx)
        self.send_alerts()
        today = [e for e in self.ledger()["events"].values() if e["day"] == ODD]
        self.assertEqual(sorted(e["event"] for e in today if e["entity_id"] == "NASDAQ:BBB"), ["recommendation"])
        self.events = self.ledger()["events"]
        self.past("NASDAQ:AAA", ODD, channel="news")  # AAA already alerted today by news
        aaa = idx["candidates"][0]
        aaa.update(classification="recommended", approval={"candidate_version": aaa["candidate_version"]})
        c.atomic_json(k.index_path(), idx)
        self.seed()
        self.send_alerts()
        self.assertFalse(any(e["event"] == "recommendation" and e["entity_id"] == "NASDAQ:AAA"
                             for e in self.ledger()["events"].values()))

    def test_legacy_notify_sends_count_by_company(self):
        self.seed()
        self.index(tickers=("AAA",))
        c.write_rows("signal_log", [signal(0, entity_id="NASDAQ:AAA", **{"종목/티커": "AAA"}, 티어="관망")])
        c.atomic_json(notify.STATE_PATH, {"pushed": ["SIG-0000", "SIG-9999"], "sent": {
            "SIG-0000": {"date": self.at(ODD, -5), "kind": "candidate"},
            "SIG-9999": {"date": self.at(ODD, -5), "kind": "candidate"}}})
        self.assertEqual(self.send_alerts()[1], 0)
        recent, unknown = a.recent_new_alerts(a.load_ledger(), notify.load_state(), c.read_rows("signal_log"))
        self.assertEqual((recent, unknown), ({"NASDAQ:AAA": self.at(ODD, -5)}, 1))

    def test_bootstrap_companies_are_seen_not_sent(self):
        self.seed(bootstrap={"date": "2026-09-01", "keys": [a.logical_key("NASDAQ:AAA", k.THESIS_KEY, a.NEW)]})
        self.index(tickers=("AAA",))
        self.assertEqual(self.send_alerts()[1], 0)
        recent, _ = a.recent_new_alerts(a.load_ledger(), notify.load_state(), [])
        self.assertNotIn("NASDAQ:AAA", recent)  # no invented send time


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


class RemoteReservationTest(AlertTest):
    """F4: the remote holds a reservation before any send; later runs never resend it."""

    def setUp(self):
        super().setUp()
        c.atomic_json(a.ledger_path(), {"events": {}, "bootstrap": {"date": "2026-09-01", "keys": []}})
        self.index(tickers=("AAA",))

    def event(self):
        return next(iter(self.ledger()["events"].values()))

    def restart_from_remote(self):
        """The next CI run checks out only what the remote received."""
        (self.data / "candidate_alerts.json").write_text(self.pushes[-1][1], encoding="utf-8")

    def test_reservation_push_failure_sends_nothing_and_releases(self):
        self.push_results = [False]
        self.assertEqual(self.send_alerts(), (1, 0))
        self.assertEqual(self.event()["status"], "released")
        self.assertEqual(self.event()["attempts"][-1]["error"], "reservation_not_persisted")
        self.assertEqual(self.send_alerts(), (0, 1))  # the next run sends it once
        self.assertEqual(self.event()["status"], "sent")

    def test_stop_after_the_reservation_reached_the_remote_is_not_resent(self):
        with mock.patch.object(notify, "deliver", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                a.main([])
        self.assertIn('"reserved"', self.pushes[-1][1])
        self.restart_from_remote()
        self.assertEqual(self.send_alerts(), (0, 0))
        event = self.event()
        self.assertEqual((event["status"], event["attempts"][-1]["error"]), ("uncertain", "reservation_without_receipt"))

    def test_receipt_push_failure_still_blocks_a_resend(self):
        self.push_results = [True, False]  # reservation saved, receipts not
        self.assertEqual(self.send_alerts(), (1, 1))
        self.assertEqual(self.event()["status"], "sent")  # locally known
        self.restart_from_remote()
        self.assertEqual(self.send_alerts(), (0, 0))
        self.assertEqual(self.event()["status"], "uncertain")

    def test_reservation_records_what_will_be_sent(self):
        self.send_alerts()
        reserved = json.loads(self.pushes[0][1])["events"]
        event = next(iter(reserved.values()))
        self.assertEqual(event["status"], "reserved")
        self.assertEqual(len(event["payload_sha256"]), 64)
        self.assertTrue(event["observation_id"].startswith("OB-"))
        self.assertTrue(event["reserved_by"])
        key = next(iter(reserved))
        self.assertEqual(json.loads(self.pushes[1][1])["events"][key]["status"], "sent")  # receipt pushed after

    def test_local_runs_never_push_so_never_send(self):
        with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": ""}), \
                mock.patch("persist_state.persist", side_effect=AssertionError("pushed")):
            self.assertFalse(REAL_PERSIST_REMOTE("x"))
        with mock.patch.object(a, "persist_remote", REAL_PERSIST_REMOTE), mock.patch.dict("os.environ", {"GITHUB_ACTIONS": ""}):
            self.assertEqual(self.send_alerts(), (1, 0))

    def test_dry_run_pushes_nothing(self):
        self.assertEqual(self.send_alerts(dry=True), (0, 0))
        self.assertEqual(self.pushes, [])

    def test_long_news_message_keeps_source_and_command(self):
        row = signal(0, **{"특이값 요약": "<&" * 5000})
        text = a.news_message({"row": row, "signal_id": row["signal_id"]})
        self.assertLessEqual(len(text), notify.MESSAGE_LIMIT)
        self.assertIn("/track SIG-0000", text)
        self.assertIn("요약본", text)
        self.assertIn('href="https://example.org/filing"', text)


class GitRemoteTest(unittest.TestCase):
    """persist_state.persist against a real temporary git remote."""

    def git(self, *args, cwd):
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)

    def test_push_success_and_failure_are_reported(self):
        import persist_state
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            self.git("init", "--bare", "-q", str(root / "remote.git"), cwd=root)
            self.git("clone", "-q", str(root / "remote.git"), str(root / "work"), cwd=root)
            work = root / "work"
            for key, value in (("user.name", "t"), ("user.email", "t@example.invalid"), ("commit.gpgsign", "false")):
                self.git("config", key, value, cwd=work)
            data = work / "data" / "processed"
            data.mkdir(parents=True)
            with mock.patch.object(c, "ROOT", work), mock.patch.object(c, "DATA_DIR", data), \
                    contextlib.redirect_stdout(io.StringIO()):
                c.atomic_json(data / "candidate_alerts.json", {"events": {"k": {"status": "reserved"}}})
                self.assertTrue(persist_state.persist("chore: reserve"))
                shown = self.git("--git-dir", str(root / "remote.git"), "show", "HEAD:data/processed/candidate_alerts.json",
                                 cwd=root).stdout
                self.assertIn("reserved", shown)
                self.git("remote", "set-url", "origin", str(root / "missing.git"), cwd=work)
                c.atomic_json(data / "candidate_alerts.json", {"events": {"k": {"status": "sent"}}})
                self.assertFalse(persist_state.persist("chore: receipts"))
                shown = self.git("--git-dir", str(root / "remote.git"), "show", "HEAD:data/processed/candidate_alerts.json",
                                 cwd=root).stdout
                self.assertIn("reserved", shown)  # the remote still blocks a resend
                # R1: the commit exists locally but never reached the remote. With the remote back and
                # no file change, persist must push it, not report success because the tree is clean.
                self.git("remote", "set-url", "origin", str(root / "remote.git"), cwd=work)
                self.assertTrue(persist_state.persist("chore: nothing new"))
                shown = self.git("--git-dir", str(root / "remote.git"), "show", "HEAD:data/processed/candidate_alerts.json",
                                 cwd=root).stdout
                self.assertIn("sent", shown)
                head = self.git("rev-parse", "HEAD", cwd=work).stdout
                self.assertEqual(self.git("--git-dir", str(root / "remote.git"), "rev-parse", "HEAD", cwd=root).stdout, head)

    def test_push_that_leaves_the_remote_behind_is_not_success(self):
        import persist_state

        def fake_run(args, **kwargs):
            out = {"HEAD": "aaa\n", "@{u}": "bbb\n"}.get(args[-1], "")
            return subprocess.CompletedProcess(args, 1 if args[1:3] == ["diff", "--cached"] else 0, out)

        with mock.patch.object(persist_state.subprocess, "run", side_effect=fake_run), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(persist_state.persist("x"))

    def test_clean_tree_with_an_unreachable_remote_is_not_success(self):
        import persist_state
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            self.git("init", "--bare", "-q", str(root / "remote.git"), cwd=root)
            self.git("clone", "-q", str(root / "remote.git"), str(root / "work"), cwd=root)
            work = root / "work"
            for key, value in (("user.name", "t"), ("user.email", "t@example.invalid"), ("commit.gpgsign", "false")):
                self.git("config", key, value, cwd=work)
            data = work / "data" / "processed"
            data.mkdir(parents=True)
            with mock.patch.object(c, "ROOT", work), mock.patch.object(c, "DATA_DIR", data), \
                    contextlib.redirect_stdout(io.StringIO()):
                c.atomic_json(data / "candidate_alerts.json", {"events": {}})
                self.assertTrue(persist_state.persist("chore: first"))
                self.git("remote", "set-url", "origin", str(root / "missing.git"), cwd=work)
                self.assertFalse(persist_state.persist("chore: clean tree"))


class DeliverClassificationTest(unittest.TestCase):
    def setUp(self):
        # How replies are classified is tested with sending allowed; the block has its own test.
        patch = mock.patch.dict(os.environ, {"RESEARCH_DISABLE_SEND": ""})
        patch.start()
        self.addCleanup(patch.stop)

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

    def test_success_needs_a_valid_message_id(self):
        for body in (b'{"ok": true, "result": {}}', b'{"ok": true, "result": {"message_id": "42"}}',
                     b'{"ok": true, "result": {"message_id": true}}', b'{"ok": true, "result": {"message_id": 0}}',
                     b'{"ok": true, "result": []}', b'[{"ok": true}]', b'{"result": {"message_id": 5}}'):
            self.assertEqual(self.outcome(body=body).status, "uncertain", body)

    def test_cut_connections_are_uncertain_and_only_definite_no_sends_fail(self):
        self.assertEqual(self.outcome(URLError(socket.gaierror("dns"))).status, "failed")
        self.assertEqual(self.outcome(URLError(ConnectionResetError())).status, "uncertain")
        self.assertEqual(self.outcome(URLError(http.client.RemoteDisconnected("x"))).status, "uncertain")
        self.assertEqual(self.outcome(http.client.RemoteDisconnected("x")).status, "uncertain")
        response = mock.MagicMock()
        response.__enter__.return_value.read.side_effect = http.client.IncompleteRead(b"{")
        with mock.patch.object(notify, "urlopen", return_value=response), mock.patch.object(c, "record_run"):
            self.assertEqual(notify.deliver("t", "c", "m").status, "uncertain")

    def test_errors_never_carry_the_bot_url(self):
        error = URLError(OSError("https://api.telegram.org/botSECRET/sendMessage"))
        self.assertNotIn("SECRET", str(self.outcome(error).error))


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
