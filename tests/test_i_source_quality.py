"""I2: per-company official-source quality on the card, kept apart from the screen's data quality."""
import gzip
import json
import pathlib
import sys
import unittest
from datetime import timedelta
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))
import candidate_context  # noqa: E402
import candidates as k  # noqa: E402
import common as c  # noqa: E402
import telegram_cmd  # noqa: E402
from test_candidates import NOW, CandidateFixture, ContextCardTest, snapshot  # noqa: E402

PARTIAL = "공식 원문 일부 미확보 — 확보된 자료 기준"
FAILED = "최근 원문 확인 실패"


class SourceQualityTest(CandidateFixture):
    add_context = ContextCardTest.add_context
    card = ContextCardTest.card
    write_evidence = ContextCardTest.write_evidence

    def set_research(self, **fields):
        state = candidate_context.load_state()
        state["candidates"][self.aaa["candidate_id"]].update(fields)
        c.atomic_json(candidate_context.state_path(), state)
        return self.card()

    def rendered(self, card, stale=None):
        index = {**k.load_index(), "candidates": [card], "stale": stale or []}
        return [k.telegram_card(card, stale), k.markdown_card(card, stale), k.render_html(index)]

    def test_normal_partial_failed_recovered(self):
        self.add_context()
        normal = self.set_research(quality="complete", failures=0, attempted_at="2026-09-25T02:00:00+00:00")
        self.assertEqual(normal["source_quality"], "complete")
        for text in self.rendered(normal):
            self.assertNotIn(PARTIAL, text)
            self.assertNotIn(FAILED, text)

        partial = self.set_research(quality="partial", failures=1, attempted_at="2026-09-26T02:00:00+00:00",
                                    notes=["0000000001-26-000011 index URLError"])
        self.assertEqual((partial["source_quality"], partial["source_failures"]), ("partial", 1))
        self.assertEqual(partial["source_failure_reasons"], ["0000000001-26-000011 index URLError"])
        self.assertIsNotNone(partial["context"])  # what was secured is still shown
        for text in self.rendered(partial):
            self.assertIn(PARTIAL, text)
        lines = k.card_lines(partial)
        at = lines.index(("section", "공식 발표에서 확인한 변화 (자동 정리·미검토)"))
        self.assertTrue(lines[at - 1][0] == "warn" and PARTIAL in lines[at - 1][1])  # right above the section

        failed = self.set_research(status="failed", quality="unknown", failures=3,
                                   attempted_at="2026-09-27T02:00:00+00:00")
        self.assertEqual(failed["source_quality"], "unavailable")
        # The last valid draft stays under a dated warning, so the card version does not change.
        self.assertEqual(failed["candidate_version"], normal["candidate_version"])
        for text in self.rendered(failed):
            self.assertIn(f"{FAILED}(2026-09-27). 아래는 마지막 유효 근거 2026-09-25 기준(현재 확인 결과 아님)", text)
            self.assertNotIn("관련 원문을 확인하지 못했습니다", text)  # access failure is not 'nothing relevant'

        recovered = self.set_research(status="success", quality="complete", failures=0,
                                      attempted_at="2026-09-28T02:00:00+00:00")
        self.assertEqual(recovered["source_quality"], "complete")
        self.assertIsNotNone(recovered["context"])
        for text in self.rendered(recovered):
            self.assertNotIn(PARTIAL, text)
            self.assertNotIn(FAILED, text)

        # Each source attempt is its own observation, and earlier ones keep what they showed.
        ids = [x["observation_id"] for x in (normal, partial, failed, recovered)]
        self.assertEqual(len(set(ids)), 4)
        version, obs = k.load_observation(partial["observation_id"])
        then = k.telegram_card(k.assemble(version, obs, []))
        self.assertIn(PARTIAL, then)
        self.assertEqual(obs["source_quality"], "partial")
        version, obs = k.load_observation(normal["observation_id"])
        self.assertNotIn(PARTIAL, k.telegram_card(k.assemble(version, obs, [])))

    def test_nothing_relevant_after_a_draft_drops_it(self):
        self.add_context()
        card = self.set_research(status="no_relevant_document", failures=0)
        self.assertIsNone(card["context"])
        self.assertNotIn(FAILED, k.telegram_card(card))

    def test_source_failure_keeps_a_human_approval_and_shows_the_limit(self):
        from test_candidates import sourced_evidence
        self.add_context()
        self.write_evidence(sourced_evidence())
        self.card()
        version = k.approve(self.aaa["candidate_id"], "user")
        card = self.set_research(status="failed", failures=2, attempted_at="2026-09-27T02:00:00+00:00")
        self.assertEqual((card["candidate_version"], card["classification"]), (version, "recommended"))
        self.assertIsNone(card["review_note"])
        for text in self.rendered(card):
            self.assertIn(FAILED, text)

    def test_failed_without_earlier_evidence_says_so(self):
        c.atomic_json(candidate_context.state_path(), {"candidates": {self.aaa["candidate_id"]: {
            "status": "failed", "failures": 2, "attempted_at": "2026-09-26T02:00:00+00:00"}},
            "days": {}, "documents_by_source": {}})
        text = k.telegram_card(self.card())
        self.assertIn(f"{FAILED}(2026-09-26). 이전에 확보한 유효 근거 없음", text)
        self.assertIn("원문 접근 실패", text)

    def test_nothing_relevant_is_complete_access_without_a_warning(self):
        c.atomic_json(candidate_context.state_path(), {"candidates": {self.aaa["candidate_id"]: {
            "status": "no_relevant_document", "failures": 0}}, "days": {}, "documents_by_source": {}})
        card = self.card()
        self.assertEqual(card["source_quality"], "complete")
        text = k.telegram_card(card)
        self.assertNotIn(FAILED, text)
        self.assertIn("원문에서 확인 못 함", text)

    def test_not_researched_is_unknown(self):
        self.assertEqual(self.card()["source_quality"], "unknown")

    def test_stale_screen_and_partial_source_are_both_shown(self):
        self.add_context()
        self.set_research(quality="partial", failures=1, attempted_at="2026-09-26T02:00:00+00:00")
        state = c.read_json(c.DATA_DIR / "daily_runs.json", {"days": {}})
        state["days"].setdefault("2026-09-25", {"runs": [], "steps": {}})["steps"]["screen"] = {
            "execution_status": "started", "run_id": "9-1"}
        c.atomic_json(c.DATA_DIR / "daily_runs.json", state)
        card = self.card()
        index = k.load_index()
        self.assertEqual(index["stale"], ["latest_screen_started"])
        for text in self.rendered(card, index["stale"]):
            self.assertIn("마지막 유효 관측", text)
            self.assertIn(PARTIAL, text)

    def test_draft_for_another_fiscal_year_is_not_attached(self):
        self.add_context()
        path = candidate_context.history_dir() / "CTX-0000000000000001.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["eps_target_period"] = "2026-12-31"
        path.write_text(json.dumps(record), encoding="utf-8")
        card = self.set_research(eps_target_period="2026-12-31", quality="complete")
        self.assertEqual(card["eps"]["eps_target_period"], "2027-12-31")
        self.assertIsNone(card["context"])
        self.assertNotIn("40% 늘었다", k.telegram_card(card))
        # The same fiscal year attaches.
        record["eps_target_period"] = "2027-12-31"
        path.write_text(json.dumps(record), encoding="utf-8")
        self.assertIsNotNone(self.set_research(eps_target_period="2027-12-31")["context"])

    def test_observation_recorded_before_v4_shows_unknown_and_no_warning(self):
        self.add_context()
        partial = self.set_research(quality="partial", failures=1)
        path = k.observations_dir() / f"{partial['observation_id']}.json"
        old = json.loads(path.read_text(encoding="utf-8"))
        for key in ("source_quality", "source_failures", "source_failure_reasons", "source_attempt_at",
                    "source_status", "last_valid_context"):
            old.pop(key)
        path.write_text(json.dumps(old), encoding="utf-8")
        version, obs = k.load_observation(partial["observation_id"])
        card = k.assemble(version, obs, [])
        self.assertEqual(card["source_quality"], "unknown")
        self.assertNotIn(PARTIAL, k.telegram_card(card))

    def test_track_keeps_its_meaning_with_a_partial_source(self):
        self.add_context()
        card = self.set_research(quality="partial", failures=1)
        self.assertEqual(card["classification"], "found")  # source quality never promotes or demotes
        sent = []
        with mock.patch.object(telegram_cmd, "send_reply", lambda token, chat, message: sent.append(message)):
            telegram_cmd.process_updates("t", "allowed", [self.update(1, f"/track {card['candidate_id']}")])
        rows = c.read_live_rows("investment_review_log")
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["검토 상태"], rows[0]["근거 수준"]), ("추적", "가설"))
        self.assertIn("추적 등록 완료", sent[0])
        self.assertIn("매수 추천이 아닙니다", sent[0])


if __name__ == "__main__":
    unittest.main()
