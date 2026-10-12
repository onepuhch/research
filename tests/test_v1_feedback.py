"""V1: fixed-word replies to candidate alerts become reactions (no model, no real sends)."""
import contextlib
import copy
import hashlib
import io
import json
import pathlib
import sys
import unittest
from datetime import datetime
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common as c  # noqa: E402
import candidate_feedback as fb  # noqa: E402
import candidates as k  # noqa: E402
import telegram_cmd  # noqa: E402
from test_candidates import CandidateFixture  # noqa: E402

SENT_AT = "2026-09-25T03:00:00+00:00"
SENT_UNIX = int(datetime.fromisoformat(SENT_AT).timestamp())


class ReplyFixture(CandidateFixture):
    def setUp(self):
        super().setUp()
        self.bbb = next(x for x in k.load_index()["candidates"] if x["identity"]["ticker"] == "BBB")
        self.crdo = next(x for x in k.load_index()["candidates"] if x["identity"]["ticker"] == "CRDO")

        def event(cand, message_id, status="sent", **extra):
            return {"channel": "screen", "event": "new_discovery", "entity_id": cand["identity"]["entity_id"],
                    "thesis_key": cand["thesis_key"], "candidate_id": cand["candidate_id"],
                    "candidate_version": cand["candidate_version"], "observation_id": None, "signal_id": None,
                    "day": "2026-09-25", "status": status, "message_id": message_id if status == "sent" else None,
                    "attempts": [{"at": SENT_AT, "status": status, "message_id": message_id, "error": None}], **extra}

        self.key_a = f"NASDAQ:AAA|{k.THESIS_KEY}|new_discovery"
        self.key_b = f"NASDAQ:BBB|{k.THESIS_KEY}|new_discovery"
        ledger = {"bootstrap": None, "events": {
            self.key_a: event(self.aaa, 501),
            self.key_b: event(self.bbb, 502),
            "CIK:0000000001|ai power|new_discovery": {
                "channel": "news", "event": "new_discovery", "entity_id": "CIK:0000000001", "thesis_key": "ai power",
                "candidate_id": None, "candidate_version": None, "signal_id": "SIG-0001", "day": "2026-09-25",
                "status": "sent", "message_id": 503,
                "attempts": [{"at": SENT_AT, "status": "sent", "message_id": 503, "error": None}]},
            f"NASDAQ:CRDO|{k.THESIS_KEY}|new_discovery": event(self.crdo, 504, status="uncertain")}}
        c.atomic_json(c.DATA_DIR / "candidate_alerts.json", ledger)
        c.atomic_json(c.DATA_DIR / "provider_inconsistencies.json", {"version": 1, "entries": [
            {"id": "PI-TEST", "affected_alerts": [{"key": self.key_b, "message_id": 502}]}]})
        self.sent = []

    MISSING = object()

    def reply(self, update_id, text, to=501, date=SENT_UNIX, from_bot=True, sent=SENT_UNIX + 3600):
        message = {"chat": {"id": "allowed"}, "date": sent, "text": text}
        if to is not None:
            replied = {"message_id": to, "date": date, "from": {"is_bot": from_bot}, "text": "ALERT BODY TEXT"}
            if date is self.MISSING:
                del replied["date"]
            if from_bot is self.MISSING:
                del replied["from"]
            message["reply_to_message"] = replied
        return {"update_id": update_id, "message": message}

    def run_updates(self, *updates, send=None):
        sender = send or (lambda token, chat, message: self.sent.append(message))
        with mock.patch.object(telegram_cmd, "send_reply", sender):
            telegram_cmd.process_updates("t", "allowed", list(updates))
        return self.sent

    def events(self, kind=None):
        store = c.read_json(fb.path(), {"events": []})
        return [e for e in store["events"] if kind is None or e["kind"] == kind]

    def ideas(self):
        return c.read_live_rows("investment_review_log")


class ReplyWordsTest(ReplyFixture):
    def test_four_words_and_their_command_forms(self):
        self.run_updates(self.reply(1, "관심없음"), self.reply(2, " 보류 "), self.reply(3, "자세히"),
                         self.reply(4, "패스"), self.reply(5, "/candidate"), self.reply(6, "추적"))
        self.assertEqual([e["action"] for e in self.events("reply")],
                         ["dismiss", "hold", "detail", "dismiss", "detail", "track"])
        self.assertIn("판단 기록: AAA · 관심없음", self.sent[0])
        self.assertIn("추적 등록과 알림 예약은 바꾸지 않습니다", self.sent[1])
        self.assertIn("알림 당시와 같은 카드 버전입니다", self.sent[2])
        self.assertIn(f"/track {self.aaa['candidate_id']}", self.sent[2])  # the existing detail card
        self.assertIn("추적 등록 완료", self.sent[-1])
        self.assertEqual(len(self.ideas()), 1)
        first = self.events("reply")[0]
        self.assertEqual((first["scope"], first["event_key"], first["candidate_id"], first["candidate_version"],
                          first["reply_to_message_id"], first["source"]),
                         (fb.SCOPE, self.key_a, self.aaa["candidate_id"], self.aaa["candidate_version"], 501,
                          "telegram_reply"))
        self.assertEqual(first["message_at"], datetime.fromtimestamp(SENT_UNIX + 3600, fb.timezone.utc)
                         .isoformat(timespec="seconds"))

    def test_no_chat_text_is_stored_anywhere(self):
        self.run_updates(self.reply(1, "관심없음"), self.reply(2, "이 회사 좋아 보이네"))
        for name in ("command_queue.json", "candidate_feedback.json"):
            text = (c.DATA_DIR / name).read_text(encoding="utf-8")
            for raw in ("관심없음", "ALERT BODY TEXT", "좋아 보이네", "allowed"):
                self.assertNotIn(raw, text, (name, raw))

    def test_words_without_a_reply_and_free_text_follow_help(self):
        self.run_updates(self.reply(1, "관심없음", to=None), self.reply(2, "관심 없음 ㅎㅎ"), self.reply(3, "/track", to=None))
        self.assertEqual(self.events(), [])
        self.assertTrue(all(m.startswith("지원 명령어") for m in self.sent))

    def test_command_with_argument_keeps_its_argument(self):
        self.run_updates(self.reply(1, f"/candidate {self.bbb['candidate_id']}"))
        self.assertEqual(self.events(), [])
        self.assertIn("BBB", self.sent[0])
        self.assertNotIn("AAA ", self.sent[0].split("\n")[0])

    def test_only_a_unique_sent_candidate_alert_is_linked(self):
        self.run_updates(self.reply(1, "관심없음", to=999),                       # not an alert (e.g. 168)
                         self.reply(2, "관심없음", to=503),                       # news alert, no candidate_id
                         self.reply(3, "추적", to=504),                           # uncertain receipt
                         self.reply(4, "관심없음", from_bot=False),               # not the bot's message
                         self.reply(5, "관심없음", date=SENT_UNIX + 7200))        # same number, other time
        self.assertEqual(self.events(), [])
        self.assertEqual(self.ideas(), [])
        self.assertIn("후보 알림에 대한 답장이 아니어서", self.sent[0])
        self.assertIn("후보 ID가 없는 알림", self.sent[1])
        self.assertIn("발송 확인이 끝나지 않은", self.sent[2])
        self.assertIn("후보 알림에 대한 답장이 아니어서", self.sent[3])
        self.assertIn("후보 알림에 대한 답장이 아니어서", self.sent[4])
        ledger = c.read_json(c.DATA_DIR / "candidate_alerts.json", {})
        self.assertEqual(ledger["events"][f"NASDAQ:CRDO|{k.THESIS_KEY}|new_discovery"]["status"], "uncertain")

    def test_missing_or_unreadable_identification_links_nothing(self):
        ledger = c.read_json(c.DATA_DIR / "candidate_alerts.json", {})
        ledger["events"][self.key_b]["attempts"][0]["at"] = "not a time"
        c.atomic_json(c.DATA_DIR / "candidate_alerts.json", ledger)
        self.run_updates(self.reply(1, "관심없음", from_bot=self.MISSING),   # no bot mark
                         self.reply(2, "추적", date=self.MISSING),           # no time of the alert
                         self.reply(3, "보류", to=502))                      # receipt time unreadable
        self.assertEqual((self.events(), self.ideas()), ([], []))
        self.assertEqual(len(self.sent), 3)
        for message in self.sent:
            self.assertIn("발신·시각 정보를 확인하지 못해", message)
        self.assertEqual(fb.resolve(501, SENT_UNIX)["state"], "unverified")  # bot mark not given
        del ledger["events"][self.key_a]["attempts"][0]["at"]
        c.atomic_json(c.DATA_DIR / "candidate_alerts.json", ledger)
        self.assertEqual(fb.resolve(501, SENT_UNIX, True)["state"], "unverified")  # receipt without time

    def test_a_reply_days_later_to_the_same_message_links(self):
        self.run_updates(self.reply(1, "보류", sent=SENT_UNIX + 5 * 86400))
        self.assertEqual([e["action"] for e in self.events("reply")], ["hold"])
        self.assertIn("판단 기록: AAA · 보류", self.sent[0])

    def test_two_events_with_one_message_id_are_ambiguous(self):
        ledger = c.read_json(c.DATA_DIR / "candidate_alerts.json", {})
        ledger["events"][self.key_b]["message_id"] = 501
        c.atomic_json(c.DATA_DIR / "candidate_alerts.json", ledger)
        self.assertEqual(fb.resolve(501, SENT_UNIX, True)["state"], "ambiguous")


class VerdictTest(ReplyFixture):
    def test_detail_never_replaces_the_judgment(self):
        self.run_updates(self.reply(1, "추적"), self.reply(2, "자세히"))
        latest = fb.latest_by_alert(fb.load())
        self.assertEqual(latest[self.key_a]["action"], "track")

    def test_dismiss_after_track_changes_the_judgment_and_keeps_tracking(self):
        self.run_updates(self.reply(1, "추적"), self.reply(2, "관심없음"))
        self.assertEqual(fb.latest_by_alert(fb.load())[self.key_a]["action"], "dismiss")
        self.assertEqual(len(self.ideas()), 1)
        self.assertEqual(self.ideas()[0]["검토 상태"], "추적")
        self.assertEqual(len(self.events("reply")), 2)  # both kept

    def test_detail_only_is_no_judgment_plus_lookup(self):
        self.run_updates(self.reply(1, "자세히"))
        s = fb.summary()
        self.assertEqual((s["normal"]["no_judgment"], s["normal"]["detail_only"], s["detail_events"]), (1, 1, 1))
        self.assertEqual(s["normal"]["latest"], {"track": 0, "dismiss": 0, "hold": 0})

    def test_detail_says_card_changed_never_that_numbers_changed(self):
        # The version also changes with description, sources or context alone; the reply says only
        # whether the card is the same.
        ledger = c.read_json(c.DATA_DIR / "candidate_alerts.json", {})
        ledger["events"][self.key_a]["candidate_version"] = "CV-OLD-DESCRIPTION"
        c.atomic_json(c.DATA_DIR / "candidate_alerts.json", ledger)
        self.run_updates(self.reply(1, "자세히"))
        note = self.sent[0].split("\n")[0]
        self.assertIn("알림 이후 카드 내용이 변경되었습니다", note)
        self.assertNotIn("숫자", note)

    def test_detail_on_the_same_version_claims_no_numbers(self):
        self.run_updates(self.reply(1, "자세히"))
        note = self.sent[0].split("\n")[0]
        self.assertIn("알림 당시와 같은 카드 버전입니다", note)
        self.assertNotIn("숫자", note)


class TrackReplyTest(ReplyFixture):
    def result(self):
        results = self.events("track_result")
        self.assertEqual(len(results), 1)
        return results[0]

    def test_success_is_the_existing_track_rule_and_no_promotion(self):
        self.run_updates(self.reply(1, "추적"))
        r = self.result()
        self.assertEqual((r["outcome"], r["reason_code"], r["processed_version"], r["candidate_state"]),
                         ("success", None, self.aaa["candidate_version"], "current"))
        row = self.ideas()[0]
        self.assertEqual((r["idea_id"], row["근거 수준"], row["사업 단계"]), (row["idea_id"], "가설", "미확인"))
        self.assertEqual(k.load_index()["candidates"][0]["classification"], self.aaa["classification"])
        self.assertFalse(k.review_events_dir().exists())  # no approval or review event

    def test_already_tracked(self):
        self.run_updates(self.update(1, f"/track {self.aaa['candidate_id']}"), self.reply(2, "추적"))
        self.assertEqual(self.result()["outcome"], "already_tracked")
        self.assertIn("이미 추적 중입니다", self.sent[-1])
        self.assertEqual(len(self.ideas()), 1)

    def test_capacity_is_a_rejection(self):
        with mock.patch.object(c, "active_ideas", return_value=[{}] * c.policy()["max_active_ideas"]):
            self.run_updates(self.reply(1, "추적"))
        self.assertEqual((self.result()["outcome"], self.result()["reason_code"]), ("rejected", "capacity"))
        self.assertIn("가득 찼습니다", self.sent[0])
        self.assertEqual(self.ideas(), [])

    def test_unreadable_observation_time_is_an_input_rejection(self):
        index = k.load_index()
        index["candidates"][0]["observed_at"] = "unknown"
        with mock.patch.object(k, "load_index", return_value=index):
            self.run_updates(self.reply(1, "추적"))
        self.assertEqual((self.result()["outcome"], self.result()["reason_code"]), ("rejected", "invalid_record"))
        self.assertIn("관측 시각이 올바르지 않아", self.sent[0])
        self.assertEqual(self.ideas(), [])

    def test_ledger_state_error_is_retried_not_rejected(self):
        import add_entry
        with mock.patch.object(add_entry, "process", side_effect=ValueError("enum validation failed")),                 self.assertRaises(RuntimeError):
            self.run_updates(self.reply(1, "추적"), self.update(2, f"/track {self.aaa['candidate_id']}"))
        queue = c.read_json(c.DATA_DIR / "command_queue.json", {})
        self.assertEqual([queue[key]["status"] for key in ("1", "2")], ["pending", "pending"])
        self.assertEqual({queue[key]["last_error_type"] for key in ("1", "2")}, {"TrackStateError"})
        self.assertEqual((self.sent, self.events("track_result"), self.ideas()), ([], [], []))
        self.assertEqual(len(self.events("reply")), 1)  # the judgment itself is kept
        self.run_updates()
        self.assertEqual(self.events("track_result")[0]["outcome"], "success")
        self.assertEqual((len(self.events("reply")), len(self.ideas())), (1, 1))
        self.assertIn("추적 등록 완료", self.sent[0])
        self.assertIn(self.ideas()[0]["idea_id"], self.sent[1])  # the /track command reached the same idea

    def test_old_candidate_is_a_rejection(self):
        with mock.patch.object(c, "today", return_value="2026-10-30"):
            self.run_updates(self.reply(1, "추적"))
        self.assertEqual(self.result()["reason_code"], "observation_too_old")
        self.assertEqual(self.ideas(), [])

    def test_disputed_alert_keeps_the_judgment_but_never_registers(self):
        self.run_updates(self.reply(1, "추적", to=502), self.reply(2, "관심없음", to=502))
        replies = self.events("reply")
        self.assertEqual([e["disputed_source"] for e in replies], [["PI-TEST"], ["PI-TEST"]])
        self.assertEqual((self.result()["outcome"], self.result()["reason_code"]), ("rejected", "disputed_source"))
        self.assertEqual(self.ideas(), [])
        self.assertIn(f"/track {self.bbb['candidate_id']}", self.sent[0])
        s = fb.summary()
        self.assertEqual((s["normal"]["alerts"], s["disputed"]["alerts"], s["disputed"]["latest"]["dismiss"]), (1, 1, 1))
        # The explicit command is still the user's way to choose it.
        self.run_updates(self.update(3, f"/track {self.bbb['candidate_id']}"))
        self.assertEqual(len(self.ideas()), 1)


class RetryTest(ReplyFixture):
    def test_same_update_twice_and_a_forced_rerun_add_nothing(self):
        self.run_updates(self.reply(1, "추적"))
        self.run_updates(self.reply(1, "추적"))  # Telegram delivers it again
        queue = c.read_json(c.DATA_DIR / "command_queue.json", {})
        queue["1"].update(status="pending", text="/reply", action="track")  # processed again from the start
        c.atomic_json(c.DATA_DIR / "command_queue.json", queue)
        self.run_updates()
        self.assertEqual((len(self.events("reply")), len(self.events("track_result")), len(self.ideas())), (1, 1, 1))

    def test_stop_after_the_queue_is_saved(self):
        with mock.patch.object(telegram_cmd, "handle_reply", side_effect=OSError("stopped")), \
                self.assertRaises(RuntimeError):
            self.run_updates(self.reply(1, "관심없음"))
        self.assertEqual(self.events(), [])
        self.assertEqual(c.read_json(c.DATA_DIR / "command_queue.json", {})["1"]["status"], "pending")
        self.run_updates()
        self.assertEqual(len(self.events("reply")), 1)

    def test_stop_after_tracking_is_saved_counts_one_success(self):
        real = fb.append_once
        stops = {"n": 0}

        def flaky(event):
            if event["kind"] == "track_result" and not stops["n"]:
                stops["n"] = 1
                raise OSError("stopped")
            return real(event)

        with mock.patch.object(fb, "append_once", flaky), self.assertRaises(RuntimeError):
            self.run_updates(self.reply(1, "추적"))
        self.assertEqual((len(self.ideas()), self.events("track_result")), (1, []))
        self.run_updates()
        self.assertEqual(len(self.ideas()), 1)
        self.assertEqual(self.events("track_result")[0]["outcome"], "success")  # tracked_before kept the truth
        self.assertIn("추적 등록 완료", self.sent[-1])

    def test_reply_failure_keeps_the_saved_judgment(self):
        def fail(token, chat, message):
            raise RuntimeError("network")

        with self.assertRaises(RuntimeError):
            self.run_updates(self.reply(1, "추적"), send=fail)
        self.assertEqual(c.read_json(c.DATA_DIR / "command_queue.json", {})["1"]["status"], "reply_pending")
        self.run_updates()
        self.assertEqual((len(self.events("reply")), len(self.events("track_result")), len(self.ideas())), (1, 1, 1))
        self.assertIn("추적 등록 완료", self.sent[0])

    def test_damaged_store_is_kept_and_the_reply_retried(self):
        fb.path().write_text("{", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            self.run_updates(self.reply(1, "관심없음"))
        self.assertEqual(fb.path().read_text(encoding="utf-8"), "{")
        self.assertEqual(c.read_json(c.DATA_DIR / "command_queue.json", {})["1"]["status"], "pending")
        self.assertEqual(self.sent, [])
        self.assertIn("기록 파일 확인 필요", k.card_lines(self.aaa)[2][1])

    def test_dry_run_writes_nothing(self):
        def digest_tree():
            return {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in pathlib.Path(self.tmp.name).rglob("*") if p.is_file()}

        before = digest_tree()
        out = io.StringIO()
        with mock.patch.object(telegram_cmd, "telegram_request", side_effect=AssertionError("network")), \
                contextlib.redirect_stdout(out):
            for word in ("추적", "관심없음", "자세히"):
                self.assertEqual(telegram_cmd.main(["--dry-run", "--command", word, "--reply-to", "501"]), 0)
            self.assertEqual(telegram_cmd.main(["--dry-run", "--command", "추적", "--reply-to", "502"]), 0)
        self.assertEqual(digest_tree(), before)
        self.assertIn("[dry-run·진단: 봇·시각 미검증 조회] AAA", out.getvalue())
        self.assertIn("PI-TEST", out.getvalue())


class ViewsTest(ReplyFixture):
    def test_card_shows_the_latest_judgment_with_its_version(self):
        self.run_updates(self.reply(1, "관심없음"))
        notes = [t for kind, t in k.card_lines(self.aaa) if t.startswith("사용자 판단")]
        self.assertEqual(len(notes), 1)
        self.assertIn("관심없음", notes[0])
        self.assertIn("이 카드와 같은 버전", notes[0])
        newer = copy.deepcopy(self.aaa)
        newer["candidate_version"] = "CV-NEWER"
        self.assertIn("이 카드와 다른 버전", [t for _, t in k.card_lines(newer) if t.startswith("사용자 판단")][0])
        self.assertFalse([t for _, t in k.card_lines(self.bbb) if t.startswith("사용자 판단")])

    def test_report_counts_alerts_companies_and_results_apart(self):
        self.run_updates(self.reply(1, "추적"), self.reply(2, "자세히"), self.reply(3, "관심없음"),
                         self.reply(4, "보류", to=502))
        s = fb.summary()
        self.assertEqual(s["normal"], {"alerts": 1, "companies": 1, "latest": {"track": 0, "dismiss": 1, "hold": 0},
                                       "no_judgment": 0, "detail_only": 0, "judged_companies": 1})
        self.assertEqual((s["detail_events"], s["track_requests"], s["track_outcomes"]), (1, 1, {"success": 1}))
        self.assertEqual(s["disputed"]["latest"]["hold"], 1)
        text = "\n".join(fb.render_lines())
        self.assertIn("사용자 반응·활용", text)
        self.assertIn("알림 1건 (기업 1곳)", text)
        self.assertIn("제공처 값 불일치 알림(별도) 1건", text)
        self.assertIn("무응답은 거절로 세지 않습니다", text)


if __name__ == "__main__":
    unittest.main()
