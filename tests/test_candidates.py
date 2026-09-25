import contextlib
import copy
import gzip
import hashlib
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import common as c  # noqa: E402
import candidates as k  # noqa: E402
import screen_revisions  # noqa: E402
import telegram_cmd  # noqa: E402

NOW = datetime(2026, 9, 25, 3, 0, tzinfo=timezone.utc)
REF = {"path": "data/processed/revision_screen/x.json.gz", "sha256": "0" * 64, "run_id": "1-1",
       "finished_at": "2026-09-25T01:23:02+00:00"}
REGISTRY = {"CRDO": {"entity_id": "NASDAQ:CRDO", "currency": "USD", "exchange": "NASDAQ"}}


def row(ticker, **fields):
    base = {"ticker": ticker, "symbol": ticker, "name": f"{ticker} Inc.", "exchange": "Nasdaq",
            "market_cap": 1e9, "eps_target_period": "2027-12-31", "eps_currency": "USD",
            "eps_basis": "provider-unspecified", "eps_retrieved_at": "2026-09-25T01:15:00+00:00",
            "analysts": 5, "eps_now": 2.0, "eps_30d": 1.5, "eps_90d": 1.0, "pct_90": 100.0,
            "yield_change_90_pp": 2.0, "yield_change_30_pp": 1.0, "turnaround": False, "up30": 4, "down30": 0,
            "steady": True, "by_yield": True, "by_growth": True, "candidate": True, "industry": "Semiconductors",
            "sector": "Technology", "summary": "Makes chips for data centers.",
            "price_status": "success", "price_note": "", "price_basis": "close", "price_start_target": "2026-06-27",
            "price_start_date": "2026-06-26", "price_end_expected": "2026-09-24", "price_end_date": "2026-09-24",
            "close_start": 10.0, "close_end": 11.0, "price_pct_90": 10.0, "adj_return_pct_90": 10.0,
            "pe_change_pct": -45.0}
    base.update(fields)
    return base


def snapshot(rows=None, top_yield=("AAA", "CRDO"), top_growth=("BBB", "AAA"), status="success",
             finished="2026-09-25T01:23:02+00:00", run_id="1-1"):
    rows = rows if rows is not None else [row("AAA"), row("BBB", by_yield=False), row("CRDO", by_growth=False)]
    return {"run": {"run_id": run_id, "status": status, "finished_at": finished, "universe_size": 100},
            "stages": {"earnings": {"requested": 90, "success": 80}},
            "derived": {"rows": rows, "top_yield": list(top_yield), "top_growth": list(top_growth)}}


def build(snap=None, evidence=None, translations=None, ideas=None, ref=REF):
    return k.build(snap or snapshot(), ref, REGISTRY, evidence or {}, translations or {}, ideas or [], "pol")


def sourced_evidence(extra_sources=None):
    statement = [{"text": "Q2 guidance raised on AI demand", "kind": "guidance", "source_ids": ["ir"]}]
    return {"explanations": {field: statement for field in k.EXPLANATIONS},
            "sources": [{"id": "ir", "title": "Q2 release", "provider": "Company", "url": "https://ir.example.com/q2",
                         "published_at": "2026-08-01", "observed_at": "2026-09-25",
                         "quote": "raising full-year guidance on AI demand"}] + (extra_sources or [])}


class IdentityAndVersionTest(unittest.TestCase):
    def test_same_input_same_id_and_version(self):
        first, second = build(), build()
        self.assertEqual([(x["candidate_id"], x["candidate_version"]) for x in first],
                         [(x["candidate_id"], x["candidate_version"]) for x in second])
        self.assertTrue(all(k.CAN_PATTERN.fullmatch(x["candidate_id"]) for x in first))

    def test_display_order_alternates_lists_once_per_company(self):
        self.assertEqual([x["identity"]["ticker"] for x in build()], ["AAA", "BBB", "CRDO"])
        aaa = build()[0]
        self.assertEqual(aaa["memberships"], [{"list": "A", "rank": 1}, {"list": "B", "rank": 2}])

    def test_registry_identity_is_used_and_cik_never_guessed(self):
        crdo = next(x for x in build() if x["identity"]["ticker"] == "CRDO")
        self.assertEqual(crdo["identity"]["entity_id"], "NASDAQ:CRDO")
        self.assertEqual(crdo["candidate_id"], k.candidate_id("NASDAQ:CRDO"))
        new = build()[0]
        self.assertEqual((new["identity"]["entity_id"], new["identity"]["source"]),
                         ("NASDAQ:AAA", "SEC company_tickers_exchange"))

    def test_unknown_exchange_gets_no_id_and_no_track_command(self):
        snap = snapshot(rows=[row("AAA", exchange=None)], top_yield=["AAA"], top_growth=[])
        cand = build(snap)[0]
        self.assertIsNone(cand["candidate_id"])
        self.assertEqual(cand["classification"], "needs_evidence")
        self.assertFalse(any(kind == "command" for kind, _ in k.card_lines(cand)))

    def test_collection_time_rank_and_price_window_do_not_make_a_new_version(self):
        base = build()[0]
        later = snapshot(rows=[row("AAA", eps_retrieved_at="2026-09-26T01:15:00+00:00", price_pct_90=25.0,
                                   price_end_date="2026-09-25"), row("BBB", by_yield=False),
                               row("CRDO", by_growth=False)],
                         top_yield=("CRDO", "AAA"), top_growth=("BBB", "AAA"), finished="2026-09-26T01:23:02+00:00")
        moved = next(x for x in build(later, ref={**REF, "run_id": "2-1"}) if x["identity"]["ticker"] == "AAA")
        self.assertEqual(moved["candidate_version"], base["candidate_version"])
        self.assertNotEqual(moved["display_rank"], base["display_rank"])

    def test_estimate_change_or_fiscal_year_roll_is_a_new_version_same_id(self):
        base = build()[0]
        for change in ({"eps_now": 2.1}, {"eps_target_period": "2028-12-31"}):
            snap = snapshot(rows=[row("AAA", **change), row("BBB", by_yield=False), row("CRDO", by_growth=False)])
            cand = build(snap)[0]
            self.assertEqual(cand["candidate_id"], base["candidate_id"])
            self.assertNotEqual(cand["candidate_version"], base["candidate_version"])

    def test_versions_are_stored_once_and_collisions_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(c, "DATA_DIR", pathlib.Path(tmp)):
            cands = build()
            self.assertEqual(k.store_versions(cands), 3)
            self.assertEqual(k.store_versions(cands), 0)
            path = k.history_dir() / f"{cands[0]['candidate_version']}.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            record["candidate_id"] = "CAN-FFFFFFFFFFFFFFFF"
            path.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaises(ValueError):
                k.store_versions(cands)


class ClassificationTest(unittest.TestCase):
    def test_screen_only_is_found_and_missing_data_has_reasons(self):
        self.assertEqual(build()[0]["classification"], "found")
        snap = snapshot(rows=[row("AAA", price_status="unavailable", price_note="window_not_covered", industry=None)],
                        top_yield=["AAA"], top_growth=[])
        cand = build(snap)[0]
        self.assertEqual(cand["classification"], "needs_evidence")
        self.assertEqual({m["field"] for m in cand["missing"]}, {"price_comparison", "industry"})
        text = k.telegram_card(cand)
        self.assertIn("90일 전 종가 없음", text)
        self.assertIn("회사 설명 확인 중", text)

    def test_recommended_needs_sourced_evidence_and_approval_of_this_version(self):
        cid = build()[0]["candidate_id"]
        unsourced = sourced_evidence()
        unsourced["explanations"]["falsification"] = [{"text": "x", "kind": "interpretation", "source_ids": ["nope"]}]
        cand = build(evidence={cid: unsourced})[0]
        self.assertIn("falsification_unsourced", cand["evidence_problems"])
        evidence = sourced_evidence()
        version = build(evidence={cid: evidence})[0]["candidate_version"]
        evidence["approval"] = {"approved_by": "user", "approved_at": "2026-09-25T00:00:00+00:00",
                                "candidate_version": version}
        approved = build(evidence={cid: evidence})[0]
        self.assertEqual(approved["classification"], "recommended")
        self.assertTrue(k.telegram_card(approved).startswith("<b>추적 추천"))
        # Evidence approved, then the numbers moved: the old approval does not carry over.
        moved = snapshot(rows=[row("AAA", eps_now=2.4), row("BBB", by_yield=False), row("CRDO", by_growth=False)])
        cand = build(moved, evidence={cid: evidence})[0]
        self.assertEqual(cand["classification"], "found")
        self.assertIn("재검토", cand["review_note"])

    def test_unsafe_source_urls_do_not_count_or_render(self):
        cid = build()[0]["candidate_id"]
        evidence = sourced_evidence()
        evidence["sources"][0]["url"] = "javascript:alert(1)"
        cand = build(evidence={cid: evidence})[0]
        self.assertIn("earnings_path_unsourced", cand["evidence_problems"])
        self.assertNotIn("javascript:", k.telegram_card(cand))

    def test_tracking_state_is_separate_from_classification(self):
        same = [{"idea_id": "IDEA-0001", "entity_id": "NASDAQ:CRDO", "thesis_key": k.THESIS_KEY,
                 "현재 단계": "관찰", "검토 상태": "추적"}]
        crdo = next(x for x in build(ideas=same) if x["identity"]["ticker"] == "CRDO")
        self.assertEqual((crdo["tracking"]["status"], crdo["classification"]), ("tracked", "found"))
        self.assertIn("이 가설 추적 중", k.tracking_label(crdo))
        self.assertEqual([t for kind, t in k.card_lines(crdo) if kind == "command"], ["/history CRDO"])

    def test_company_tracked_under_another_thesis_offers_both_commands(self):
        other = [{"idea_id": "IDEA-0002", "entity_id": "NASDAQ:CRDO", "thesis_key": "bottleneck:serdes",
                  "현재 단계": "관찰", "검토 상태": "추적"}]
        crdo = next(x for x in build(ideas=other) if x["identity"]["ticker"] == "CRDO")
        self.assertEqual(crdo["tracking"]["status"], "entity_tracked")
        self.assertIn("기업은 추적 중·이 가설 미등록", k.tracking_label(crdo))
        self.assertEqual([t for kind, t in k.card_lines(crdo) if kind == "command"],
                         ["/history CRDO", f"/track {crdo['candidate_id']}"])

    def test_partial_run_shows_scope_warning(self):
        cand = build(snapshot(status="degraded"))[0]
        self.assertEqual(cand["run_quality"], "partial")
        self.assertIn("확보 범위 내 순위", k.telegram_card(cand))

    def test_card_escapes_html(self):
        snap = snapshot(rows=[row("AAA", name="<b>Evil</b> & Co", industry="A<B")], top_yield=["AAA"], top_growth=[])
        text = k.telegram_card(build(snap)[0])
        self.assertIn("&lt;b&gt;Evil&lt;/b&gt; &amp; Co", text)
        self.assertNotIn("<b>Evil", text)


class SnapshotChoiceTest(unittest.TestCase):
    def write(self, directory, stamp, run_id, status):
        path = directory / f"{stamp}_{run_id}.json.gz"
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(snapshot(status=status, run_id=run_id,
                               finished=datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(
                                   tzinfo=timezone.utc).isoformat()), handle)
        return path

    def test_failed_latest_attempt_keeps_previous_valid_as_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp)
            good = self.write(d, "20260924T010000Z", "1-1", "success")
            self.write(d, "20260925T010000Z", "2-1", "failed")
            choice = k.choose_snapshot(list(d.glob("*.json.gz")), NOW, 36)
            self.assertEqual(choice["valid"]["path"], good)
            self.assertEqual(choice["stale"], ["latest_attempt_failed"])

    def test_old_valid_result_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp)
            self.write(d, "20260923T010000Z", "1-1", "degraded")
            self.assertEqual(k.choose_snapshot(list(d.glob("*.json.gz")), NOW, 36)["stale"], ["old_observation"])
            self.assertEqual(k.choose_snapshot([], NOW, 36)["stale"], ["no_valid_screen"])


class ScreenAttemptTest(unittest.TestCase):
    """F5: a screen attempt that left no snapshot still marks the cards stale."""

    def state(self, status, run_id="2-1", planned_by=None, day="2026-09-25"):
        entry = {"execution_status": status, "run_id": run_id, "quality_status": "unknown"}
        if planned_by:
            entry["planned_by"] = planned_by
        return {"days": {"2026-09-24": {"steps": {"screen": {"execution_status": "success", "run_id": "1-1"}}},
                         day: {"steps": {"screen": entry}}}}

    def test_timeout_or_kill_without_snapshot_is_stale(self):
        self.assertEqual(k.screen_attempt_stale(self.state("started"), "1-1"), ["latest_screen_started"])
        self.assertEqual(k.screen_attempt_stale(self.state("failed"), "1-1"), ["latest_screen_failed"])
        self.assertEqual(k.screen_attempt_stale(self.state("blocked"), "1-1"), ["latest_screen_blocked"])

    def test_plan_that_stopped_before_screen_is_stale(self):
        self.assertEqual(k.screen_attempt_stale(self.state("pending", run_id="1-1", planned_by="3-1"), "1-1"),
                         ["latest_screen_pending"])

    def test_later_success_in_use_clears_it(self):
        self.assertEqual(k.screen_attempt_stale(self.state("success", run_id="4-1"), "4-1"), [])
        self.assertEqual(k.screen_attempt_stale(self.state("success", run_id="4-1"), "1-1"),
                         ["latest_screen_result_missing"])

    def test_schema_1_success_with_unknown_quality_is_not_a_failure(self):
        old = {"days": {"2026-09-24": {"steps": {"screen": {"status": "success", "run_id": "1-1"}}}}}
        self.assertEqual(k.screen_attempt_stale(old, "1-1"), [])
        self.assertEqual(k.screen_attempt_stale({}, "1-1"), [])


class TranslationTest(unittest.TestCase):
    def test_invented_numbers_or_non_korean_text_are_rejected(self):
        source = "Makes chips for data centers."
        self.assertTrue(k.valid_translation("데이터센터용 반도체를 만들어 판다.", source))
        self.assertFalse(k.valid_translation("데이터센터 매출 30% 성장 반도체 회사", source))
        self.assertFalse(k.valid_translation("Makes chips for data centers.", source))

    def test_budget_cache_and_batches(self):
        rows = [row(t, summary=f"Company {t} sells pumps.") for t in ("AAA", "BBB", "CCC")]
        calls = []

        def fake(prompt):
            calls.append(prompt)
            return {"AAA": "펌프를 파는 회사다.", "BBB": "펌프 30대를 판다", "CCC": "펌프를 판매하는 기업이다."}

        cfg = {"translation_batch": 2, "translation_max_calls": 5}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(c, "DATA_DIR", pathlib.Path(tmp)):
            cache = {}
            report = k.translate(rows, cache, "key", cfg, fake)
            self.assertEqual((report["calls"], report["translated"], report["rejected"]), (2, 2, 1))
            k.translate(rows[:1], cache, "key", cfg, fake)
            self.assertEqual(len(calls), 2)  # cached: no new call
            with mock.patch.object(c, "model_calls_today", return_value=c.policy()["max_model_calls"]):
                report = k.translate(rows, cache, "key", cfg, fake)
            self.assertEqual((report["calls"], report.get("budget_exhausted")), (0, True))
            self.assertEqual(k.translate(rows, cache, "", cfg, fake)["calls"], 0)  # no credential

    def test_card_uses_cached_translation_by_source_hash(self):
        text = row("AAA")["summary"]
        cache = {k.translation_key(text): {"text_ko": "데이터센터용 반도체를 만든다.", "model": "m"}}
        cand = build(translations=cache)[0]
        self.assertEqual(cand["explanations"]["company_description_ko"]["text"], "데이터센터용 반도체를 만든다.")


def isolate_ci_environment(test):
    """Tests must not see the CI job's run ID or mode (they would join 'this run')."""
    env = mock.patch.dict("os.environ")
    env.start()
    test.addCleanup(env.stop)
    for key in ("DAILY_MODE", "DAILY_DAY", "DAILY_RUN_ID", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_ACTIONS"):
        os.environ.pop(key, None)


class CandidateFixture(unittest.TestCase):
    """A temporary data directory with one generated screener snapshot (no tests of its own)."""

    def setUp(self):
        isolate_ci_environment(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        data = pathlib.Path(self.tmp.name) / "processed"
        (data / "revision_screen").mkdir(parents=True)
        for patch in (mock.patch.object(c, "DATA_DIR", data),
                      mock.patch.object(screen_revisions, "SCREEN_DIR", data / "revision_screen"),
                      mock.patch.object(telegram_cmd, "OFFSET_PATH", data / "telegram_offset.json"),
                      mock.patch.object(c, "ROOT", pathlib.Path(self.tmp.name)),
                      # The fixture observations are from 2026-09-25; freshness must not depend on the run date.
                      mock.patch.object(c, "today", return_value="2026-09-25"),
                      mock.patch.object(k, "now_utc", return_value=NOW),
                      contextlib.redirect_stdout(io.StringIO())):
            patch.__enter__()
            self.addCleanup(patch.__exit__, None, None, None)
        (pathlib.Path(self.tmp.name) / "config").mkdir()
        real = pathlib.Path(__file__).resolve().parents[1]
        for name in ("research_policy.json", "entities.json"):
            (pathlib.Path(self.tmp.name) / "config" / name).write_bytes((real / "config" / name).read_bytes())
        (pathlib.Path(self.tmp.name) / "templates").mkdir()
        (pathlib.Path(self.tmp.name) / "templates" / "candidates.html").write_bytes(
            (real / "templates" / "candidates.html").read_bytes())
        (pathlib.Path(self.tmp.name) / "docs").mkdir()
        with gzip.open(data / "revision_screen" / "20260925T010000Z_1-1.json.gz", "wt", encoding="utf-8") as h:
            json.dump(snapshot(), h)
        k.generate(now=NOW, translate_now=False)
        self.aaa = k.load_index()["candidates"][0]

    def update(self, update_id, text, chat="allowed"):
        return {"update_id": update_id, "message": {"chat": {"id": chat}, "text": text}}


class StaleWithoutSnapshotTest(CandidateFixture):
    def record_screen(self, status, run_id, day="2026-09-25"):
        state = c.read_json(c.DATA_DIR / "daily_runs.json", {"days": {}})
        state["days"].setdefault(day, {"runs": [], "steps": {}})["steps"]["screen"] = {
            "execution_status": status, "run_id": run_id}
        c.atomic_json(c.DATA_DIR / "daily_runs.json", state)

    def test_killed_screen_marks_cards_stale_and_blocks_alerts_until_a_new_success(self):
        self.record_screen("started", "9-1")  # the only gz is the earlier success 1-1
        k.generate(now=NOW, translate_now=False)
        self.assertEqual(k.load_index()["stale"], ["latest_screen_started"])
        self.assertIn("마지막 유효 관측", telegram_cmd.handle_command("/screen")[0])
        import candidate_alerts
        self.assertEqual(candidate_alerts.screen_items(k.load_index()), ([], []))
        # Re-rendering later with the same data does not make it fresh.
        k.generate(now=NOW + timedelta(hours=1), translate_now=False)
        self.assertEqual(k.load_index()["stale"], ["latest_screen_started"])
        # A new successful screen whose snapshot is in use clears it.
        with gzip.open(c.DATA_DIR / "revision_screen" / "20260925T030000Z_9-2.json.gz", "wt", encoding="utf-8") as h:
            json.dump(snapshot(run_id="9-2", finished="2026-09-25T03:10:00+00:00"), h)
        self.record_screen("success", "9-2")
        k.generate(now=NOW + timedelta(hours=2), translate_now=False)
        self.assertEqual(k.load_index()["stale"], [])


class CommandTest(CandidateFixture):
    """Direct and queued /screen and /candidate against a generated index."""

    def test_screen_and_candidate_replies(self):
        screen = telegram_cmd.handle_command("/screen")[0]
        self.assertIn(f"/candidate {self.aaa['candidate_id']}", screen)
        self.assertIn("실시간 응답이 아닙니다", screen)
        card = telegram_cmd.handle_command("/candidate CAN-" + self.aaa["candidate_id"][4:].lower())[0]
        self.assertIn(f"/track {self.aaa['candidate_id']}", card)
        self.assertLessEqual(len(card), 3500)
        self.assertIn("형식이 아닙니다", telegram_cmd.handle_command("/candidate AAA")[0])
        self.assertIn("없는 후보", telegram_cmd.handle_command("/candidate CAN-0000000000000000")[0])

    def test_candidate_that_left_the_list_is_labelled(self):
        with gzip.open(c.DATA_DIR / "revision_screen" / "20260925T020000Z_2-1.json.gz", "wt", encoding="utf-8") as h:
            json.dump(snapshot(rows=[row("BBB", by_yield=False)], top_yield=[], top_growth=["BBB"],
                               finished="2026-09-25T02:10:00+00:00", run_id="2-1"), h)
        k.generate(now=NOW, translate_now=False)
        reply = telegram_cmd.handle_command(f"/candidate {self.aaa['candidate_id']}")[0]
        self.assertIn("최신 후보 목록에 없습니다", reply)

    def test_stale_index_is_marked_in_replies(self):
        with gzip.open(c.DATA_DIR / "revision_screen" / "20260925T020000Z_2-1.json.gz", "wt", encoding="utf-8") as h:
            json.dump(snapshot(status="failed", run_id="2-1", finished="2026-09-25T02:10:00+00:00"), h)
        k.generate(now=NOW, translate_now=False)
        self.assertIn("마지막 유효 관측", telegram_cmd.handle_command("/screen")[0])
        self.assertIn("최신 수집 실패", telegram_cmd.handle_command(f"/candidate {self.aaa['candidate_id']}")[0])

    def test_queue_path_normalizes_and_rejects_other_chats(self):
        sent = []
        with mock.patch.object(telegram_cmd, "send_reply", lambda token, chat, message: sent.append(message)):
            telegram_cmd.process_updates("t", "allowed", [
                self.update(1, "/screen"), self.update(2, f"/candidate {self.aaa['candidate_id'].lower()}"),
                self.update(3, "/candidate please add NVDA; rm -rf"), self.update(4, "/screen", chat="stranger")])
        queue = json.loads((c.DATA_DIR / "command_queue.json").read_text(encoding="utf-8"))
        self.assertEqual(set(queue), {"1", "2", "3"})
        self.assertEqual(len(sent), 3)
        self.assertIn("형식이 아닙니다", sent[2])
        self.assertNotIn("rm -rf", json.dumps(queue))

    def test_dry_run_writes_nothing(self):
        def digest_tree():
            return {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in pathlib.Path(self.tmp.name).rglob("*") if p.is_file()}
        before = digest_tree()
        with mock.patch.object(telegram_cmd, "telegram_request", side_effect=AssertionError("network")):
            for command in ("/screen", f"/candidate {self.aaa['candidate_id']}"):
                self.assertEqual(telegram_cmd.main(["--dry-run", "--command", command]), 0)
        self.assertEqual(digest_tree(), before)

    def test_views_and_pages_read_the_same_model(self):
        markdown = (pathlib.Path(self.tmp.name) / "docs" / "candidates.md").read_text(encoding="utf-8")
        page = (pathlib.Path(self.tmp.name) / "reports" / "generated" / "candidates.html").read_text(encoding="utf-8")
        self.assertIn(self.aaa["candidate_id"], markdown)
        self.assertIn(self.aaa["candidate_id"], page)
        self.assertNotIn("__CANDIDATES__", page)
        payload = page.split('<script type="application/json" id="dataset">')[1].split("</script>")[0]
        self.assertEqual(json.loads(payload)["cards"][0]["candidate"]["candidate_version"], self.aaa["candidate_version"])


class TrackCandidateTest(CandidateFixture):
    """D2: the user's /track CAN choice becomes one ledger idea and a collection target."""

    def track(self, update_id, cid=None, sent=None):
        sent = sent if sent is not None else []
        with mock.patch.object(telegram_cmd, "send_reply", lambda token, chat, message: sent.append(message)):
            telegram_cmd.process_updates("t", "allowed", [self.update(update_id, f"/track {cid or self.aaa['candidate_id']}")])
        return sent

    def ideas(self):
        return c.read_live_rows("investment_review_log")

    def test_track_registers_once_and_repeats_return_the_same_idea(self):
        replies = self.track(1) + self.track(2)
        rows = self.ideas()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row["entity_id"], row["ticker"], row["thesis_key"], row["검토 상태"], row["근거 수준"],
                          row["사업 단계"], row["현재 단계"], row["아이디어 유형"]),
                         ("NASDAQ:AAA", "AAA", k.THESIS_KEY, "추적", "가설", "미확인", "관찰", "사이클 리비전형"))
        self.assertEqual(json.loads(row["origin_candidate_ids"]), [self.aaa["candidate_id"]])
        self.assertEqual(row["origin_signal_ids"], "[]")  # no invented news signal
        self.assertIn(self.aaa["candidate_version"], row["당시 판단"])
        self.assertIn("검증 승격 아님", row["변경 사유"])
        self.assertEqual(len(c.read_rows("review_history")), 1)
        self.assertIn("추적 등록 완료", replies[0])
        self.assertIn("다음 auto 일간 실행", replies[0])
        self.assertIn(row["idea_id"], replies[1])

    def test_tracked_company_becomes_a_collection_target_with_verified_currency(self):
        import collect_eps
        self.track(1)
        targets = {t["ticker"]: t for t in collect_eps.load_targets()}
        self.assertEqual((targets["AAA"]["entity_id"], targets["AAA"]["currency"]), ("NASDAQ:AAA", "USD"))
        import daily_run_state
        before = daily_run_state.tracking_revision()
        self.track(2)  # a repeat changes nothing
        self.assertEqual(daily_run_state.tracking_revision(), before)

    def test_capacity_and_stale_candidates_write_nothing(self):
        with mock.patch.object(c, "active_ideas", return_value=[{}] * c.policy()["max_active_ideas"]):
            reply = self.track(1)[0]
        self.assertIn("가득 찼습니다", reply)
        self.assertEqual(self.ideas(), [])
        import promote
        with self.assertRaises(ValueError):
            promote.promote_candidate(self.aaa, now_day="2026-10-30")
        self.assertEqual(self.ideas(), [])
        self.assertIn("없는 후보", self.track(3, "CAN-0000000000000000")[0])

    def test_interrupted_write_recovers_without_duplicates(self):
        real = c.write_rows
        calls = {"n": 0}

        def flaky(table, rows):
            calls["n"] += 1
            if table == "review_history" and calls["n"] < 50:
                calls["n"] = 50
                raise OSError("disk hiccup")
            return real(table, rows)

        with mock.patch.object(c, "write_rows", flaky), self.assertRaises(RuntimeError):
            self.track(1)  # the command run reports that commands were retained for retry
        queue = json.loads((c.DATA_DIR / "command_queue.json").read_text(encoding="utf-8"))
        self.assertNotEqual(queue["1"]["status"], "done")  # kept for retry, not answered as an input error
        sent = []
        with mock.patch.object(telegram_cmd, "send_reply", lambda token, chat, message: sent.append(message)):
            telegram_cmd.process_updates("t", "allowed", [])
        self.assertEqual(len(self.ideas()), 1)
        self.assertEqual(len(c.read_rows("review_history")), 1)
        self.assertIn("추적 등록 완료", sent[0])

    def test_existing_tracked_ideas_are_not_touched(self):
        existing = {"target_table": "investment_review_log", "data": {
            "종목/업종": "CRDO", "entity_id": "NASDAQ:CRDO", "ticker": "CRDO", "thesis_key": "bottleneck:serdes",
            "현재 단계": "관찰", "사업 단계": "미확인", "근거 수준": "가설", "검토 상태": "재검토",
            "변경 사유": "seed", "data_quality": "live"}}
        import add_entry
        idea = add_entry.process(existing)
        before = [dict(r) for r in self.ideas()]
        self.track(1)
        after = {r["idea_id"]: r for r in self.ideas()}
        self.assertEqual(after[idea], before[0])
        crdo = next(x for x in k.load_index()["candidates"] if x["identity"]["ticker"] == "CRDO")
        self.assertEqual(crdo["tracking"]["status"], "untracked")  # index predates the seed until regenerated
        k.generate(now=NOW, translate_now=False)
        crdo = next(x for x in k.load_index()["candidates"] if x["identity"]["ticker"] == "CRDO")
        # Another thesis of the same company: shown as the company being tracked, never merged.
        self.assertEqual((crdo["tracking"]["status"], crdo["tracking"]["idea_ids"]), ("entity_tracked", [idea]))

    def test_track_dry_run_writes_nothing(self):
        before = sorted(p.name for p in c.DATA_DIR.rglob("*"))
        self.assertIn("등록 예정", telegram_cmd.handle_command(f"/track {self.aaa['candidate_id']}", dry_run=True)[0])
        self.assertEqual(sorted(p.name for p in c.DATA_DIR.rglob("*")), before)

    def test_signal_and_ticker_track_paths_are_unchanged(self):
        self.assertIn("SIG를 찾을 수 없습니다", telegram_cmd.handle_command("/track SIG-0001")[0])
        self.assertIn("SIG를 찾을 수 없습니다", telegram_cmd.handle_command("/track CAN")[0])  # ticker CAN, not an ID


class ObservationHistoryTest(CandidateFixture):
    """F1: content versions and real observations are kept apart."""

    def observe(self, day, rows=None, top=("AAA", "CRDO"), growth=("BBB", "AAA")):
        """A screener run on a later day, then card generation at that time."""
        stamp = datetime.fromisoformat(f"{day}T01:15:00+00:00")
        rows = rows if rows is not None else [row("AAA"), row("BBB", by_yield=False), row("CRDO", by_growth=False)]
        rows = [{**r, "eps_retrieved_at": stamp.isoformat()} for r in rows]
        run_id = f"{day.replace('-', '')}-1"
        with gzip.open(c.DATA_DIR / "revision_screen" / f"{stamp.strftime('%Y%m%dT%H%M%SZ')}_{run_id}.json.gz",
                       "wt", encoding="utf-8") as h:
            json.dump(snapshot(rows=rows, top_yield=list(top), top_growth=list(growth), run_id=run_id,
                               finished=(stamp + timedelta(minutes=8)).isoformat()), h)
        k.generate(now=stamp + timedelta(hours=2), translate_now=False)
        return k.load_index()

    def aaa_known(self):
        return k.load_index()["known"][self.aaa["candidate_id"]]

    def test_same_version_seen_16_days_later_then_leaving_keeps_the_real_last_observation(self):
        self.observe("2026-10-11")
        known = self.aaa_known()
        self.assertEqual(len(known["timeline"]), 1)  # same claim, one version
        self.assertEqual((known["first_seen_at"][:10], known["last_seen_at"][:10]), ("2026-09-25", "2026-10-11"))
        self.observe("2026-10-12", rows=[row("AAA", candidate=False), row("BBB", by_yield=False)],
                     top=(), growth=("BBB",))
        cand, state = k.find(self.aaa["candidate_id"])
        self.assertEqual((state, cand["observed_at"][:10]), ("not_current", "2026-10-11"))
        self.assertEqual(cand["departure"]["reason"], "screen_condition_not_met")
        reply = telegram_cmd.handle_command(f"/candidate {self.aaa['candidate_id']}")[0]
        self.assertIn("스크린 조건 미충족", reply)
        self.assertIn("2026-10-11", reply)
        import promote
        # Fresh by the real last observation (10/11), not the first (9/25).
        self.assertTrue(promote.promote_candidate(cand, now_day="2026-10-20").startswith("IDEA-"))

    def test_rank_outside_is_not_called_a_failed_condition(self):
        self.observe("2026-09-26", top=("CRDO",), growth=("BBB",))
        cand, _ = k.find(self.aaa["candidate_id"])
        self.assertEqual(cand["departure"]["reason"], "rank_outside")

    def test_a_b_a_is_rebuilt_in_time_order(self):
        self.observe("2026-09-26", rows=[row("AAA", eps_now=2.2), row("BBB", by_yield=False), row("CRDO", by_growth=False)])
        self.observe("2026-09-27")
        timeline = self.aaa_known()["timeline"]
        versions = [t["version"] for t in timeline]
        self.assertEqual(len(versions), 3)
        self.assertEqual(versions[0], versions[2])
        self.assertNotEqual(versions[0], versions[1])
        self.assertEqual(self.aaa_known()["latest_version"], versions[0])

    def test_price_only_change_is_a_new_observation_of_the_same_version(self):
        self.observe("2026-09-26", rows=[row("AAA", price_pct_90=30.0, yield_change_90_pp=1.4),
                                         row("BBB", by_yield=False), row("CRDO", by_growth=False)])
        known = self.aaa_known()
        self.assertEqual(len(known["timeline"]), 1)
        first = k.load_observation(self.aaa["observation_id"])[1]
        latest = k.load_observation(known["latest_observation"])[1]
        self.assertEqual((first["price"]["price_pct_90"], latest["price"]["price_pct_90"]), (10.0, 30.0))
        self.assertEqual(latest["eps"]["yield_change_90_pp"], 1.4)
        self.assertNotIn("yield_change_90_pp", k.load_observation(known["latest_observation"])[0]["eps"])

    def test_rerendering_the_same_input_writes_no_new_observation(self):
        before = sorted(p.name for p in k.observations_dir().glob("*.json"))
        k.generate(now=NOW, translate_now=False)
        self.assertEqual(sorted(p.name for p in k.observations_dir().glob("*.json")), before)

    def test_registration_keeps_the_observation_it_was_made_from(self):
        import promote
        idea_id = promote.promote_candidate(self.aaa)
        row_ = next(r for r in c.read_live_rows("investment_review_log") if r["idea_id"] == idea_id)
        self.assertEqual(k.registered_observation(row_), self.aaa["observation_id"])
        self.observe("2026-09-26", rows=[row("AAA", price_pct_90=55.0), row("BBB", by_yield=False),
                                         row("CRDO", by_growth=False)])
        version, obs = k.load_observation(k.registered_observation(row_))
        then = k.telegram_card(k.assemble(version, obs, []))
        self.assertIn("+10.0%", then)  # the price shown at registration, not today's
        self.assertNotIn("+55.0%", then)

    def test_future_observation_is_refused_and_stale_repeat_writes_nothing(self):
        import promote
        future = {**self.aaa, "observed_at": "2026-12-01T01:00:00+00:00"}
        with self.assertRaises(ValueError):
            promote.promote_candidate(future, now_day="2026-09-25")
        idea_id = promote.promote_candidate(self.aaa, now_day="2026-09-25")
        ledger = c.csv_path("investment_review_log").read_bytes()
        history = c.csv_path("review_history").read_bytes()
        # Long after the observation: the linked active idea is returned, nothing is written.
        self.assertEqual(promote.promote_candidate(self.aaa, now_day="2027-03-01"), idea_id)
        self.assertEqual((c.csv_path("investment_review_log").read_bytes(), c.csv_path("review_history").read_bytes()),
                         (ledger, history))

    def write_observation(self, observation_id, observed_at, currency="USD", exchange="NASDAQ"):
        record = dict(self.base_observation)
        record.update(observation_id=observation_id, observed_at=observed_at,
                      identity={**record["identity"], "exchange": exchange}, eps={**record["eps"], "eps_currency": currency})
        c.atomic_json(k.observations_dir() / f"{observation_id}.json", record)

    def test_verified_target_uses_time_not_hash_name_and_holds_conflicts(self):
        self.base_observation = c.read_json(k.observations_dir() / f"{self.aaa['observation_id']}.json", {})
        for path in k.observations_dir().glob("*.json"):
            path.unlink()
        self.write_observation("OB-FFFFFFFFFFFFFFFF", "2026-09-20T01:00:00+00:00")
        self.write_observation("OB-0000000000000000", "2026-09-24T01:00:00+00:00")
        target = k.verified_target("NASDAQ:AAA", "AAA")
        self.assertEqual(target["observation_id"], "OB-0000000000000000")  # latest in time, first by name
        self.assertEqual(k.verified_target("NASDAQ:AAA", "AAA", "OB-FFFFFFFFFFFFFFFF")["observation_id"],
                         "OB-FFFFFFFFFFFFFFFF")
        self.write_observation("OB-1111111111111111", "2026-09-26T01:00:00+00:00", currency="EUR")
        self.assertIn("conflict", k.verified_target("NASDAQ:AAA", "AAA"))

    def test_legacy_versions_move_their_first_observation_only_and_stay_unchanged(self):
        legacy = {"candidate_id": "CAN-1234567890ABCDEF", "candidate_version": "CV-00000000000000AA",
                  "identity": {"entity_id": "NYSE:OLD", "ticker": "OLD", "exchange": "NYSE", "verified": True,
                               "source": "SEC company_tickers_exchange"},
                  "thesis_key": k.THESIS_KEY,
                  "eps": {**{key: row("OLD")[key] for key in k.VERSION_EPS_KEYS}, "yield_change_90_pp": 2.0,
                          "yield_change_30_pp": 1.0},
                  "eps_provider": "Yahoo Finance earningsTrend (+1y)", "name": "Old Co", "industry": "Steel",
                  "lists": ["A"], "missing": [], "base_classification": "found", "explanations": {}, "sources": [],
                  "generator_version": "cards-v1", "observed_at": "2026-09-25T01:00:00+00:00",
                  "source_snapshot": {"path": "x", "sha256": "s"}, "policy_version": "p"}
        path = k.history_dir() / "CV-00000000000000AA.json"
        c.atomic_json(path, legacy)
        before = path.read_bytes()
        k.generate(now=NOW, translate_now=False)
        k.generate(now=NOW, translate_now=False)
        moved = [c.read_json(p, {}) for p in k.observations_dir().glob("*.json")
                 if c.read_json(p, {}).get("candidate_id") == "CAN-1234567890ABCDEF"]
        self.assertEqual(len(moved), 1)
        self.assertEqual(moved[0]["price"]["price_note"], "legacy_version_only")
        self.assertIn("cards-v1", moved[0]["migrated"]["note"])
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(k.observation_order({**moved[0], "observation_id": "OB-Z"})[1], 0)  # migrated sorts first
        cand, state = k.find("CAN-1234567890ABCDEF")
        self.assertEqual(state, "not_current")
        self.assertIn("과거 기록에 주가 비교 없음", k.telegram_card(cand))

    def test_observations_are_persisted(self):
        import persist_state
        seen = []

        def fake_run(args, **kwargs):
            seen.append(args)
            return mock.Mock(returncode=0, stdout="")

        with mock.patch.object(persist_state.subprocess, "run", side_effect=fake_run):
            persist_state.main()
        added = next(a for a in seen if a[1] == "add")
        self.assertTrue(any(f"candidate_observations/{self.aaa['observation_id']}.json" in x for x in added))

    def test_records_follow_the_schema_contract(self):
        with self.assertRaises(ValueError):
            c.validate_record("candidate_observation", {"observation_id": "x"})


class ApprovalTest(CandidateFixture):
    """F6: approval re-checks the current inputs; a person's 'needs evidence' mark blocks it."""

    def write_evidence(self, entry):
        c.atomic_json(k.evidence_path(), {self.aaa["candidate_id"]: entry})

    def regenerate(self):
        k.generate(now=NOW, translate_now=False)
        return next(x for x in k.load_index()["candidates"] if x["candidate_id"] == self.aaa["candidate_id"])

    def test_incomplete_sources_are_refused(self):
        with self.assertRaises(ValueError):
            k.approve(self.aaa["candidate_id"], "user")  # no evidence at all
        entry = sourced_evidence()
        del entry["sources"][0]["quote"]
        self.write_evidence(entry)
        self.regenerate()
        with self.assertRaisesRegex(ValueError, "source_ir_incomplete"):
            k.approve(self.aaa["candidate_id"], "user")
        entry = sourced_evidence()
        del entry["sources"][0]["published_at"]  # unknown must be stated as null
        self.write_evidence(entry)
        self.regenerate()
        with self.assertRaises(ValueError):
            k.approve(self.aaa["candidate_id"], "user")

    def test_approval_records_its_basis_and_makes_the_card_recommended_without_sending(self):
        self.write_evidence(sourced_evidence())
        shown = self.regenerate()
        with mock.patch("notify.deliver", side_effect=AssertionError("sent")):
            version = k.approve(self.aaa["candidate_id"], "user")
        approval = c.read_json(k.evidence_path(), {})[self.aaa["candidate_id"]]["approval"]
        self.assertEqual((approval["candidate_version"], approval["observation_id"]), (version, shown["observation_id"]))
        self.assertEqual(approval["evidence_sha256"], k.evidence_hash(c.read_json(k.evidence_path(), {})[self.aaa["candidate_id"]]))
        self.assertEqual(self.regenerate()["classification"], "recommended")
        # Edit the evidence afterwards: the old approval does not carry over.
        entry = c.read_json(k.evidence_path(), {})[self.aaa["candidate_id"]]
        entry["explanations"]["next_check"] = [{"text": "Q3 call", "kind": "interpretation", "source_ids": ["ir"]}]
        self.write_evidence(entry)
        card = self.regenerate()
        self.assertEqual(card["classification"], "found")
        self.assertIn("재검토", card["review_note"])

    def test_cards_built_before_the_evidence_changed_are_not_approved(self):
        self.write_evidence(sourced_evidence())
        self.regenerate()
        entry = sourced_evidence()
        entry["explanations"]["earnings_path"][0]["text"] = "changed after the cards were built"
        self.write_evidence(entry)  # no regeneration
        with self.assertRaisesRegex(ValueError, "inputs changed"):
            k.approve(self.aaa["candidate_id"], "user")

    def test_stale_cards_are_not_approved(self):
        self.write_evidence(sourced_evidence())
        self.regenerate()
        index = k.load_index()
        index["stale"] = ["latest_screen_failed"]
        c.atomic_json(k.index_path(), index)
        with self.assertRaisesRegex(ValueError, "stale"):
            k.approve(self.aaa["candidate_id"], "user")

    def assert_refused_now(self, reason):
        import candidate_alerts
        before = k.evidence_path().read_bytes()
        with self.assertRaisesRegex(ValueError, reason):
            k.approve(self.aaa["candidate_id"], "user")
        self.assertEqual(k.evidence_path().read_bytes(), before)
        self.assertEqual(candidate_alerts.screen_items(k.load_index()), ([], []))

    def test_freshness_is_rechecked_when_acting_not_when_rendered(self):
        self.write_evidence(sourced_evidence())
        self.regenerate()
        self.assertEqual(k.load_index()["stale"], [])
        self.assertEqual(k.current_freshness(k.load_index()), [])
        # 1. Only the clock moves: the source data is now 37+ hours old.
        with mock.patch.object(k, "now_utc", return_value=NOW + timedelta(hours=37)):
            self.assert_refused_now("old_observation")
        # 2. A screen attempt failed after the cards were generated.
        c.atomic_json(c.DATA_DIR / "daily_runs.json", {"days": {"2026-09-25": {"steps": {
            "screen": {"execution_status": "failed", "run_id": "9-1"}}}}})
        self.assert_refused_now("latest_screen_failed")
        (c.DATA_DIR / "daily_runs.json").unlink()
        # 3. A newer usable snapshot exists that the cards were not rebuilt from.
        with gzip.open(c.DATA_DIR / "revision_screen" / "20260925T020000Z_2-1.json.gz", "wt", encoding="utf-8") as h:
            json.dump(snapshot(run_id="2-1", finished="2026-09-25T02:10:00+00:00"), h)
        self.assert_refused_now("newer_snapshot_not_in_cards")
        # 4. Rebuilt from the current inputs: approval goes through.
        self.regenerate()
        self.assertTrue(k.approve(self.aaa["candidate_id"], "user").startswith("CV-"))

    def test_needs_evidence_mark_blocks_approval_and_keeps_the_screen_fact(self):
        entry = {**sourced_evidence(), "review_status": "needs_evidence", "review_reason": "고객 집중도 원문 필요"}
        self.write_evidence(entry)
        card = self.regenerate()
        self.assertEqual((card["classification"], k.headline(card)), ("needs_evidence", "발굴 후보 · 근거 보강 필요"))
        self.assertEqual(card["lists"], self.aaa["lists"])  # the numeric screen result is unchanged
        self.assertIn("고객 집중도 원문 필요", k.telegram_card(card))
        with self.assertRaisesRegex(ValueError, "marked_needs_evidence"):
            k.approve(self.aaa["candidate_id"], "user")

    def test_departed_candidates_are_listed(self):
        with gzip.open(c.DATA_DIR / "revision_screen" / "20260925T020000Z_2-1.json.gz", "wt", encoding="utf-8") as h:
            json.dump(snapshot(rows=[row("BBB", by_yield=False), row("AAA", candidate=False)], top_yield=[],
                               top_growth=["BBB"], finished="2026-09-25T02:10:00+00:00", run_id="2-1"), h)
        k.generate(now=NOW, translate_now=False)
        markdown = (pathlib.Path(self.tmp.name) / "docs" / "candidates.md").read_text(encoding="utf-8")
        self.assertIn("최근 목록에서 빠진 후보", markdown)
        self.assertIn("|AAA|", markdown)
        self.assertIn("스크린 조건 미충족", markdown)
        page = (pathlib.Path(self.tmp.name) / "reports" / "generated" / "candidates.html").read_text(encoding="utf-8")
        payload = json.loads(page.split('<script type="application/json" id="dataset">')[1].split("</script>")[0])
        self.assertIn("AAA", [d["ticker"] for d in payload["departed"]])

    def test_translation_rejections_keep_the_reason_and_retry(self):
        rejects = {}
        rows = [row("AAA", summary="Sells pumps.")]
        with mock.patch.object(c, "model_calls_today", return_value=0):
            k.translate(rows, {}, "key", {"translation_batch": 5, "translation_max_calls": 3},
                        lambda prompt: {"AAA": "펌프 30대를 판다"}, rejects)
            self.assertEqual(next(iter(rejects.values()))["reason"], "numbers_not_in_source")
            cache = {}
            k.translate(rows, cache, "key", {"translation_batch": 5, "translation_max_calls": 3},
                        lambda prompt: {"AAA": "펌프를 만들어 판매하는 회사다."}, rejects)
        self.assertEqual(len(cache), 1)  # tried again and accepted
        card = build(snapshot(rows=[row("AAA", summary="Sells pumps.")], top_yield=["AAA"], top_growth=[]))[0]
        self.assertIn(("source_text", "Sells pumps."), k.card_lines(card))
        self.assertNotIn("Sells pumps.", k.telegram_card(card))


class ColumnMigrationTest(unittest.TestCase):
    def test_new_column_is_added_after_keeping_the_old_file(self):
        import migrate_v2
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            data = pathlib.Path(tmp) / "processed"
            data.mkdir()
            with mock.patch.object(c, "DATA_DIR", data):
                old_columns = [x for x in c.table_def("investment_review_log")["columns"] if x != "origin_candidate_ids"]
                path = c.csv_path("investment_review_log")
                path.write_text(",".join(old_columns) + "\nIDEA-0001" + "," * (len(old_columns) - 2) + ",live\n",
                                encoding="utf-8-sig")
                original = path.read_bytes()
                migrate_v2.migrate()
                rows = c.read_rows("investment_review_log")
                self.assertEqual(rows[0]["idea_id"], "IDEA-0001")
                self.assertEqual(rows[0]["origin_candidate_ids"], "")
                kept = list((pathlib.Path(tmp) / "archive" / "pre_columns").glob("investment_review_log_*.csv"))
                self.assertEqual([p.read_bytes() for p in kept], [original])
                migrate_v2.migrate()  # idempotent: no second backup, no change
                self.assertEqual(len(list((pathlib.Path(tmp) / "archive" / "pre_columns").glob("*"))), 1)


if __name__ == "__main__":
    unittest.main()
