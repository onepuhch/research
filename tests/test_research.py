import copy
import contextlib
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import common as c
import add_entry as add
import metrics
import migrate_v2
import extract
import collect
import collect_eps
import promote
import notify
import telegram_cmd as commands
import gen_report
import review
import evaluate
import persist_state
import subprocess


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.data = self.root / "processed"
        self.data.mkdir()
        self.patcher = patch.object(c, "DATA_DIR", self.data)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)
        self.now = date.fromisoformat(c.today())

    def metric(self, value="5", days=0, **fields):
        row = {"종목/업종": "EXM", "entity_id": "CIK:0000000001", "지표명": "EPS consensus",
               "as_of": (self.now - timedelta(days=days)).isoformat(), "period_end": "2027-12-31",
               "fiscal_period": "annual", "metric_kind": "consensus", "출처": "Vendor A",
               "통화": "USD", "단위": "per share", "회계기준": "provider-defined",
               "출처URL": "https://example.org/estimate", "현재값": value, "data_quality": "live"}
        row.update(fields)
        return row

    def put_metric(self, **fields):
        return add.process({"target_table": "metric_log", "data": self.metric(**fields)})

    def signal(self, **fields):
        row = {"signal_id": "SIG-TEST", "날짜": c.today(), "published_at": c.today(), "종목/티커": "EXM",
               "entity_id": "CIK:0000000001", "테마": "AI interconnect", "단계 추정": "초기",
               "출처URL": "https://example.org/filing", "신호유형": "수주/백로그", "특이값 요약": "Verified orders",
               "티어": "B", "upside_score": "6", "data_quality": "live", "evidence_quote": "Record backlog grew by 30 percent.",
               "event_state": "realized", "source_role": "candidate", "signal_direction": "positive"}
        row.update(fields)
        return row

    def item(self, **fields):
        row = {"source_type": "edgar", "source_id": "accession-test", "title": "Example (EXM)",
               "published_at": c.today(), "raw_text": "Record backlog grew by 30 percent.",
               "url": "https://example.org/filing"}
        row.update(fields)
        return row

    def run_extract(self, items, model=None):
        payload = {"collected_at": datetime.now(timezone.utc).isoformat(), "items": items}
        with patch.object(extract, "load_payload", return_value=payload), patch.object(extract, "load_seen_sources", return_value=set()), \
             patch.object(extract, "load_edgar_extract_config", return_value=(40, [])), \
             patch.object(c, "load_dotenv_value", return_value="fake"), patch.object(extract, "GEMINI_SLEEP", 0):
            if model is None:
                return extract.main(["extract"])
            with patch.object(extract, "build_signal", side_effect=model):
                return extract.main(["extract"])

    def test_recovered_journal_deletion_is_staged(self):
        journal = "processed/pending_tables.json"
        seen = []
        def fake_run(args, **kwargs):
            seen.append(args)
            return subprocess.CompletedProcess(args, 0, journal + "\0" if args[1] == "ls-files" else "")
        with patch.object(c, "ROOT", self.root), patch.object(persist_state.subprocess, "run", side_effect=fake_run):
            persist_state.main()
        self.assertIn(journal, next(args for args in seen if args[1] == "add"))

    def test_bad_notification_dates_and_corrupt_state_fail_closed(self):
        for value in ["", "nonsense", "2026-02-30"]:
            self.assertFalse(notify.within_lookback(value, self.now, 14))
        path = self.data / "notify_state.json"
        path.write_text("broken", encoding="utf-8")
        with patch.object(notify, "STATE_PATH", path):
            self.assertEqual(notify.main(["notify", "--dry-run"]), 1)

    def test_oversized_signal_chunk_preserves_limit(self):
        row = self.signal(**{"특이값 요약": "<&" * 10000, "용어 해설": "x" * 10000})
        chunks = notify.build_chunks([row])
        self.assertTrue(chunks)
        self.assertTrue(all(len(message) <= notify.MESSAGE_LIMIT for message, _ in chunks))
        self.assertIn(row["signal_id"], chunks[0][1])

    def test_sec_search_failures_remain_visible(self):
        errors = []
        with patch.object(collect, "fetch_text", side_effect=HTTPError("safe", 403, "blocked", {}, None)):
            self.assertEqual(collect.collect_edgar({"max_pages": 1}, errors), [])
        self.assertEqual(errors, ["EDGAR search: HTTPError"])

    def test_cik_registry_joins_existing_crdo_identity(self):
        self.assertEqual(c.resolve_entity("CIK:0001807794"), ("NASDAQ:CRDO", "CRDO"))
        with self.assertRaises(ValueError):
            c.resolve_entity("CIK:0001807794", "WRONG")

    def test_invalid_observation_timestamp_rejected(self):
        for stamp in [c.today() + "garbage", c.today() + "T01:00:00"]:
            with self.assertRaises(ValueError):
                self.put_metric(as_of=stamp)

    def test_daily_notification_limit_persists_across_runs(self):
        c.write_rows("signal_log", [self.signal(signal_id=f"SIG-{i:04d}") for i in range(5)])
        with patch.object(notify, "STATE_PATH", self.data / "notify_state.json"), \
             patch.object(c, "load_dotenv_value", return_value="fake"), \
             patch.object(notify, "send_message", return_value=True) as send:
            self.assertEqual(notify.main(["notify"]), 0)
            self.assertEqual(notify.main(["notify"]), 0)
            self.assertEqual(send.call_count, 1)
            self.assertEqual(len(notify.load_state()["pushed"]), 3)

    def test_loan_prepayment_rejected_customer_deposit_retained(self):
        bad = self.item(raw_text="Borrowers may make prepayment of outstanding loan principal.")
        self.assertTrue(extract.non_signal_reason(bad))
        self.assertIsNone(extract.build_signal(bad, ""))
        self.assertFalse(extract.non_signal_reason(self.item(raw_text="Customer prepayments doubled under a long-term supply agreement.")))

    def test_model_failure_never_falls_back(self):
        with patch.object(extract, "build_gemini_signal", side_effect=HTTPError("safe", 429, "quota", {}, None)):
            with self.assertRaises(HTTPError):
                extract.build_signal(self.item(), "fake")
        with self.assertRaises(ValueError):
            extract.build_signal(self.item(), "")

    def test_rejections_cached_across_runs(self):
        calls = []
        def reject(*args):
            calls.append(1)
            return None
        self.assertEqual(self.run_extract([self.item()], reject), 0)
        self.assertEqual(self.run_extract([self.item()], reject), 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(c.read_json(self.data / "source_state.json", {})["accession-test"]["status"], "rejected")

    def test_retry_retains_input_and_is_not_signal(self):
        def fail(*args):
            raise HTTPError("safe", 429, "quota", {}, None)
        self.assertEqual(self.run_extract([self.item()], fail), 1)
        self.assertEqual(c.read_rows("signal_log"), [])
        record = c.read_json(self.data / "source_state.json", {})["accession-test"]
        self.assertEqual(record["status"], "retry")
        self.assertIn("raw_text", record["item"])

    def test_duplicate_source_recovery_after_append(self):
        signal = self.signal(source_id="stable-source")
        signal.pop("signal_id")
        first = extract.append_signal(signal)
        second = extract.append_signal(signal)
        self.assertEqual(first, second)
        self.assertEqual(len(c.read_rows("signal_log")), 1)

    def test_grounding_and_stage_ceiling(self):
        quote = self.item()["raw_text"]
        response = {"is_signal": True, "subject": "EXM", "signal_type": "수주/백로그", "stage": "중기",
                    "evidence_quote": quote, "event_state": "realized", "signal_direction": "positive",
                    "upside_axes": {k: 2 for k, _ in extract.AXES}, "axes_evidence": {k: quote for k, _ in extract.AXES}}
        with patch.object(extract, "call_gemini", return_value=response):
            row = extract.build_gemini_signal(self.item(), "fake")
            self.assertEqual(row["단계 추정"], "초기")
            self.assertEqual(int(row["upside_score"]), 8)
        response["evidence_quote"] = "This text does not appear in the source document."
        with patch.object(extract, "call_gemini", return_value=response), self.assertRaises(ValueError):
            extract.build_gemini_signal(self.item(), "fake")

    def test_missing_axis_quote_scores_zero(self):
        response = {"is_signal": True, "subject": "EXM", "signal_type": "CAPEX", "evidence_quote": self.item()["raw_text"],
                    "upside_axes": {k: 2 for k, _ in extract.AXES}, "event_state": "planned"}
        with patch.object(extract, "call_gemini", return_value=response):
            row = extract.build_gemini_signal(self.item(), "fake")
        self.assertEqual(row["upside_score"], "0")
        self.assertEqual(row["티어"], "관망")

    def test_large_customer_is_collected_as_evidence(self):
        hit = {"_id": "0000000001-26-000001:release.htm", "_source": {"adsh": "0000000001-26-000001", "ciks": ["1"],
               "display_names": ["Microsoft (MSFT)"], "file_date": c.today(), "file_type": "8-K"}}
        with patch.object(collect, "fetch_text", side_effect=[json.dumps({"hits": {"hits": [hit]}}), "<p>Capacity expansion increased by 30 percent.</p>"]), patch.object(collect.time, "sleep"):
            rows = collect.collect_edgar({"query": '"capacity expansion"', "search_limit": 100, "max_pages": 1})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_role"], "demand_evidence")
        self.assertTrue(rows[0]["document_url"].endswith("release.htm"))

    def test_migration_preserves_and_excludes_examples(self):
        demo = {"metric_id": "MET-0001", "날짜": "2026-06-03", "종목/업종": "메모리 반도체", "지표명": "2027F EPS", "현재값": "100"}
        c.write_rows("metric_log", [demo])
        original = c.csv_path("metric_log").read_bytes()
        migrate_v2.migrate()
        self.assertEqual((self.root / "archive/pre_v2/metric_log.csv").read_bytes(), original)
        self.assertEqual(c.read_live_rows("metric_log"), [])
        once = c.csv_path("metric_log").read_bytes()
        migrate_v2.migrate()
        self.assertEqual(c.csv_path("metric_log").read_bytes(), once)

    def test_promote_idempotent_and_derives_watchlist(self):
        first = promote.promote_signal(self.signal())
        self.assertEqual(promote.promote_signal(self.signal()), first)
        self.assertEqual(len(c.active_ideas()), 1)
        self.assertEqual(len(c.read_rows("review_history")), 1)
        self.assertIn("SIG-TEST", c.active_ideas()[0]["origin_signal_ids"])
        self.assertIn("EXM", collect_eps.load_watchlist())
        self.assertEqual(c.active_ideas()[0]["최근 점검일"], "")

    def test_same_company_distinct_hypotheses(self):
        a = promote.promote_signal(self.signal(), thesis_key="copper")
        b = promote.promote_signal(self.signal(signal_id="SIG-TWO"), thesis_key="optics")
        self.assertNotEqual(a, b)

    def test_same_thesis_links_new_signal(self):
        a = promote.promote_signal(self.signal())
        b = promote.promote_signal(self.signal(signal_id="SIG-TWO"))
        self.assertEqual(a, b)
        self.assertEqual(len(json.loads(c.active_ideas()[0]["origin_signal_ids"])), 2)

    def test_metric_baseline_is_same_provider_and_earlier_date(self):
        self.put_metric(value="5", days=10)
        self.put_metric(value="99", days=5, 출처="Vendor B")
        self.put_metric(value="6", days=0)
        latest = c.read_rows("metric_log")[-1]
        self.assertEqual(latest["이전값"], "5")
        self.put_metric(value="4", days=20)
        backfill = c.read_rows("metric_log")[-1]
        self.assertEqual(backfill["이전값"], "")

    def test_metric_period_basis_and_currency_separate(self):
        self.put_metric(value="5", days=5)
        for key, value in [("period_end", "2028-12-31"), ("회계기준", "GAAP"), ("통화", "EUR")]:
            self.put_metric(**{key: value})
            self.assertEqual(c.read_rows("metric_log")[-1]["이전값"], "")

    def test_metric_repeat_is_idempotent_but_conflict_rejected(self):
        first = self.put_metric()
        self.assertEqual(first, self.put_metric(value="5.0"))
        with self.assertRaises(ValueError):
            self.put_metric(value="6")

    def test_unchanged_observation_preserves_up_events(self):
        rows = [self.metric("5", 3), self.metric("6", 2), self.metric("7", 1), self.metric("7", 0)]
        stats = metrics.revision_stats(rows)
        self.assertEqual(stats["up_events"], 2)
        self.assertEqual(stats["up_months"], 0)
        self.assertEqual(stats["observations"], 4)

    def test_same_day_observations_not_multiple_up_events(self):
        rows = [self.metric("5"), self.metric("6"), self.metric("7")]
        self.assertEqual(metrics.revision_stats(rows)["up_events"], 0)

    def test_fmp_uses_nearest_two_periods_and_no_cross_fy_baseline(self):
        target = {"ticker": "EXM", "entity_id": "CIK:1", "currency": "USD"}
        records = [{"date": d, "epsAvg": v} for d, v in [("2030-12-31", 9), ("2028-12-31", 7), ("2027-12-31", 5), ("2020-12-31", 1)]]
        rows = collect_eps.build_metrics(target, records)
        self.assertEqual([r["data"]["period_end"] for r in rows], ["2027-12-31", "2028-12-31"])
        self.assertNotIn("이전값", rows[0]["data"])

    def test_valuation_refuses_missing_baseline_and_negative_eps(self):
        self.assertIn("baseline", metrics.aligned_valuation([self.metric()], [])["status"])
        prices = [self.metric("100", 90, metric_kind="price", 단위="split-aligned price"), self.metric("110", 0, metric_kind="price", 단위="split-aligned price")]
        result = metrics.aligned_valuation([self.metric("5", 90), self.metric("6", 0)], prices)
        self.assertAlmostEqual(result["pe_change_pct"], -8.333333333)
        self.assertIn("양의", metrics.aligned_valuation([self.metric("-1", 90), self.metric("1", 0)], prices)["status"])

    def test_future_observation_and_incomplete_definition_rejected(self):
        with self.assertRaises(ValueError):
            self.put_metric(days=-1)
        with self.assertRaises(ValueError):
            self.put_metric(회계기준="")

    def test_mid_stage_requires_time_series(self):
        idea = promote.promote_signal(self.signal())
        with self.assertRaises(ValueError):
            add.process({"target_table": "investment_review_log", "data": {"idea_id": idea, "현재 단계": "중기", "변경 사유": "one article"}})
        self.assertEqual(c.active_ideas()[0]["현재 단계"], "관찰")

    def test_atomic_csv_failure_preserves_previous_file(self):
        c.write_rows("signal_log", [self.signal()])
        before = c.csv_path("signal_log").read_bytes()
        with patch.object(os, "replace", side_effect=OSError("disk error")), self.assertRaises(OSError):
            c.write_rows("signal_log", [])
        self.assertEqual(c.csv_path("signal_log").read_bytes(), before)

    def test_journal_recovers_multi_table_write(self):
        c.atomic_json(self.data / "pending_tables.json", {"signal_log": [self.signal()], "review_history": []})
        self.assertEqual(len(c.read_rows("signal_log")), 1)
        self.assertFalse((self.data / "pending_tables.json").exists())

    def test_track_finds_previous_day_signal(self):
        c.write_rows("signal_log", [self.signal(signal_id="SIG-0001", 날짜=(self.now-timedelta(days=1)).isoformat())])
        self.assertEqual(commands.find_signal("EXM")["signal_id"], "SIG-0001")

    def test_command_reply_failure_retries_without_duplicate_idea(self):
        c.write_rows("signal_log", [self.signal(signal_id="SIG-0001")])
        update = {"update_id": 1, "message": {"chat": {"id": "allowed"}, "text": "/track SIG-0001"}}
        with patch.object(commands, "OFFSET_PATH", self.data / "offset.json"), patch.object(commands, "send_reply", side_effect=OSError("offline")):
            with self.assertRaises(RuntimeError):
                commands.process_updates("fake", "allowed", [update])
        self.assertEqual(len(c.active_ideas()), 1)
        with patch.object(commands, "OFFSET_PATH", self.data / "offset.json"), patch.object(commands, "send_reply"):
            commands.process_updates("fake", "allowed", [])
        self.assertEqual(len(c.active_ideas()), 1)
        self.assertEqual(c.read_json(self.data / "command_queue.json", {})["1"]["status"], "done")

    def test_notification_quarantine_top_limit_and_risk_exception(self):
        promote.promote_signal(self.signal())
        rows = [self.signal(signal_id=f"SIG-{i}") for i in range(8)]
        rows += [self.signal(signal_id="risk", 티어="관망", signal_direction="negative"), self.signal(signal_id="demo", data_quality="example")]
        chosen = notify.select_signals(rows, set(), "B", False)
        self.assertEqual(len(chosen), 4)
        self.assertIn("risk", [r["signal_id"] for r in chosen])
        self.assertNotIn("demo", [r["signal_id"] for r in chosen])

    def test_rule_hit_and_missing_consensus_are_visible(self):
        idea_id = promote.promote_signal(self.signal())
        self.put_metric(value="4")
        idea = c.active_ideas()[0]
        idea["추적 지표 정의"] = json.dumps({"metrics": [{"name": "Backlog", "kind": "indicator"}], "rules": [{"label": "EPS floor", "selector": {"지표명": "EPS consensus"}, "operator": "lt", "threshold": 5}]})
        check = review.inspect_idea(idea)
        self.assertEqual(check["rules"][0][1], "발동")
        self.assertEqual(check["missing"], ["Backlog"])

    def test_reports_exclude_examples_and_surface_missing_data(self):
        c.write_rows("metric_log", [self.metric(data_quality="example")])
        self.assertNotIn("EXM", gen_report.render_metric_board())
        promote.promote_signal(self.signal())
        self.assertIn("EPS consensus", gen_report.render_board())
        self.assertIn("미확인", gen_report.render_health())


if __name__ == "__main__":
    unittest.main()
