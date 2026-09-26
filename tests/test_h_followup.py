"""H1-H5 regression tests: numbers/causality, deadlines and failure states, useful documents,
issuer bootstrap and send-blocked verification. No real network, model or sleep."""
import contextlib
import gzip
import io
import json
import os
import pathlib
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common as c  # noqa: E402
import candidate_context as ctx  # noqa: E402
import company_filings as cf  # noqa: E402
import extract  # noqa: E402
import notify  # noqa: E402
import screen_revisions  # noqa: E402
from test_candidate_context import (ACC, BASE, CIK, NOW, RELEASE, UNRELATED, Clock, FakeResponse, RunFixture,  # noqa: E402
                                    claim, client, default_routes, index_page, submissions)
from test_candidates import row, snapshot  # noqa: E402


def blocks_of(text, block_id="p1"):
    return [{"document_id": "DOC-A", "block_id": block_id, "text": text}]


def check(quote, blocks=None, issuer=None, **fields):
    return ctx.validate_draft({"claims": [claim(quote=quote, block_id="p1", **fields)], "link": "unconfirmed"},
                              blocks or blocks_of(quote), issuer or {"ticker": "AAA"})


# ------------------------------------------------------------------ H1 numbers, periods, causality

class NumbersAndCausalityTest(unittest.TestCase):
    def reason(self, result):
        return result["rejected"][0]["reason"] if result["rejected"] else None

    def test_codex_reproduction_is_refused_and_link_stays_unconfirmed(self):
        text = "Revenue was $5 million in 2025. The analyst consensus is presented elsewhere."
        base = dict(metric="revenue", period="2025", currency=None)
        as_written = ctx.validate_draft({"claims": [claim(quote="Revenue was $5 million in 2025.", block_id="p1",
                                                          figures=["$5 million"], note_ko="매출은 5 billion EUR입니다.", **base)],
                                         "link": "explicit_link"}, blocks_of(text))
        self.assertEqual((as_written["claims"], self.reason(as_written)), ([], "number_or_unit_in_note"))
        self.assertEqual(as_written["link"], "unconfirmed")  # a stray 'consensus' word never makes a direct link
        swapped = check("Revenue was $5 million in 2025.", blocks_of(text), figures=["5 billion EUR"], **base)
        self.assertEqual(self.reason(swapped), "figure_not_verbatim")
        ok = check("Revenue was $5 million in 2025.", blocks_of(text), figures=["$5 million"], **base)
        self.assertEqual(ok["claims"][0]["text_ko"], "매출(revenue) · 2025: $5 million — 회사가 매출 증가를 보고했습니다.")

    def test_currency_scale_sign_and_percent_cannot_change(self):
        quote = "Revenue rose 5% to $40 million in 2026."
        loss = "Net income (loss) was (5.2) million in 2026."
        base = dict(metric="revenue", period="2026")
        self.assertEqual(self.reason(check(quote, figures=["€40 million"], **base)), "figure_not_verbatim")
        self.assertEqual(self.reason(check(quote, figures=["$40 million"], currency="EUR", **base)),
                         "currency_not_in_figures")
        self.assertEqual(self.reason(check(quote, figures=["$40 billion"], **base)), "figure_not_verbatim")
        self.assertEqual(self.reason(check(quote, figures=["$40 million"], unit="billion", **base)),
                         "unit_not_in_figures")
        self.assertEqual(self.reason(check(loss, metric="net income", figures=["5.2 million"], period="2026",
                                           currency=None)), "figure_not_verbatim")  # a loss keeps its parentheses
        self.assertEqual(len(check(loss, metric="net income", figures=["(5.2) million"], period="2026",
                                   currency=None)["claims"]), 1)
        self.assertEqual(self.reason(check(quote, figures=["$5"], **base)), "figure_not_verbatim")  # 5% is not $5
        self.assertEqual(self.reason(check(quote, figures=["5%"], note_ko="매출이 오달러 늘었습니다", **base)),
                         "number_or_unit_in_note")
        self.assertEqual(check(quote, figures=["5%", "$40 million"], **base)["claims"][0]["currency"], "USD")

    def test_a_figure_cannot_move_to_another_period(self):
        quote = "Revenue was $5 million in 2025 and $7 million in 2026."
        self.assertEqual(self.reason(check(quote, figures=["$5 million"], period="2026", currency=None)),
                         "figure_from_another_period")
        self.assertEqual(len(check(quote, figures=["$5 million"], period="2025", currency=None)["claims"]), 1)
        self.assertEqual(self.reason(check(quote, figures=["$7 million"], period="unknown", currency=None)),
                         "ambiguous_period")

    def test_gaap_label_must_match_the_source(self):
        adjusted = "Adjusted EPS was $1.20 for 2026."
        base = dict(metric="eps", figures=["$1.20"], period="2026")
        self.assertEqual(self.reason(check(adjusted, gaap="GAAP", **base)), "gaap_not_as_stated")
        self.assertEqual(len(check(adjusted, gaap="non-GAAP", **base)["claims"]), 1)
        gaap = "GAAP EPS was $1.00 for 2026."
        self.assertEqual(self.reason(check(gaap, gaap="non-GAAP", metric="eps", figures=["$1.00"], period="2026")),
                         "gaap_not_as_stated")

    def test_may_the_verb_is_not_a_month(self):
        quote = "Results may vary; revenue was $5 million in 2025."
        self.assertEqual(self.reason(check(quote, figures=["$5 million"], period="may", currency=None)),
                         "period_not_a_period")
        dated = "Revenue was $5 million for the quarter ended May 31, 2026."
        self.assertEqual(len(check(dated, figures=["$5 million"], period="May 31, 2026", currency=None)["claims"]), 1)

    def test_subject_swap_parent_and_subsidiary(self):
        quote = "MPLX expects to raise distributions by 12.5% in 2026."
        issuer = {"ticker": "MPC", "name": "Marathon Petroleum Corp"}
        labeled_parent = check(quote, issuer=issuer, kind="guidance", metric="distributions", figures=["12.5%"],
                               period="2026", currency=None)
        self.assertNotEqual(labeled_parent["context_status"], "draft_ready")  # MPLX is not MPC's earnings
        as_sub = check(quote, issuer=issuer, kind="guidance", metric="distributions", figures=["12.5%"], period="2026",
                       currency=None, subject="subsidiary", subject_name="MPLX")
        self.assertEqual(as_sub["context_status"], "insufficient_earnings_context")
        parent = "Marathon Petroleum reported net income of $1.5 billion for 2026."
        core = check(parent, issuer=issuer, metric="net income", figures=["$1.5 billion"], period="2026")
        self.assertEqual(core["context_status"], "draft_ready")

    def test_limitations_follow_the_same_number_rules(self):
        quote = "A one-time tax benefit of $12 million lifted results in 2026."
        bad = ctx.validate_draft({"limitations": [claim(quote=quote, block_id="p1", metric="", figures=["$21 million"],
                                                        period="2026", note_ko="일회성 세금 이익이 포함됐습니다.")]},
                                 blocks_of(quote))
        good = ctx.validate_draft({"limitations": [claim(quote=quote, block_id="p1", metric="", figures=["$12 million"],
                                                         period="2026", note_ko="일회성 세금 이익이 포함됐습니다.")]},
                                  blocks_of(quote))
        self.assertEqual((bad["limitations"], len(good["limitations"])), ([], 1))

    def test_next_check_is_a_question_or_plan_without_numbers(self):
        result = ctx.validate_draft({"next_check": ["다음 분기 수주를 확인", "매출 40% 증가 확인", "좋은 회사"]}, [])
        self.assertEqual(result["next_check"], ["다음 분기 수주를 확인"])


# ------------------------------------------------------------------ H2 deadlines, 429, held, failures

class ModelDeadlineTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data = pathlib.Path(tmp.name)
        for patch in (mock.patch.object(c, "DATA_DIR", self.data), mock.patch.object(c, "today", return_value="2026-09-25"),
                      contextlib.redirect_stdout(io.StringIO())):
            patch.__enter__()
            self.addCleanup(patch.__exit__, None, None, None)
        self.clock = Clock()

    def answer(self, request, timeout=None):
        self.timeouts.append(timeout)
        body = json.dumps({"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}).encode()
        return FakeResponse(body, "x")

    def counts(self):
        return c.read_json(self.data / "model_budget.json", {}).get("days", {}).get("2026-09-25", {})

    def test_timeout_is_capped_by_the_remaining_time(self):
        self.timeouts = []
        with mock.patch.object(extract, "urlopen", side_effect=self.answer):
            extract.call_gemini_prompt("p", "k", "candidate_context", timeout=60, deadline=2.0, clock=self.clock)
        self.assertLessEqual(self.timeouts[0], 2.0)

    def test_no_time_left_means_no_reservation_and_no_request(self):
        with mock.patch.object(extract, "urlopen", side_effect=AssertionError("sent")):
            with self.assertRaises(c.ModelBudgetExhausted):
                extract.call_gemini_prompt("p", "k", "cards", deadline=0.5, clock=self.clock)
        self.assertEqual(self.counts(), {})

    def test_a_retry_wait_past_the_deadline_is_not_taken(self):
        calls = []

        def busy(request, timeout=None):
            calls.append(1)
            raise HTTPError("u", 503, "busy", {}, None)

        with mock.patch.object(extract, "urlopen", side_effect=busy):
            with self.assertRaises(c.ModelBudgetExhausted):
                extract.call_gemini_prompt("p", "k", "extract", deadline=4.0, clock=self.clock, sleep=self.clock.sleep)
        self.assertEqual((len(calls), self.clock()), (1, 0.0))

    def test_429_blocks_every_component_without_retry(self):
        calls = []

        def limited(request, timeout=None):
            calls.append(1)
            raise HTTPError("u", 429, "limited", {}, None)

        with mock.patch.object(extract, "urlopen", side_effect=limited):
            with self.assertRaisesRegex(c.ModelBudgetExhausted, "provider_rate_limited"):
                extract.call_gemini_prompt("p", "k", "extract", clock=self.clock, sleep=self.clock.sleep)
            for component in ("cards", "candidate_context", "extract"):
                with self.assertRaises(c.ModelBudgetExhausted):
                    extract.call_gemini_prompt("p", "k", component, clock=self.clock, sleep=self.clock.sleep)
        self.assertEqual(len(calls), 1)
        block = c.model_provider_blocked()
        self.assertEqual(block["reason"], "provider_rate_limited")
        self.assertTrue(block["until"].endswith("15:00:00+00:00"))  # next KST midnight
        later = datetime.fromisoformat(block["until"]) + timedelta(seconds=1)
        self.assertIsNone(c.model_provider_blocked(later))

    def test_retry_after_is_kept_when_the_server_gives_it(self):
        with mock.patch.object(extract, "urlopen",
                               side_effect=HTTPError("u", 429, "limited", {"Retry-After": "120"}, None)):
            with self.assertRaises(c.ModelBudgetExhausted):
                extract.call_gemini_prompt("p", "k", "extract", clock=self.clock)
        self.assertEqual(c.model_provider_blocked()["retry_after_s"], 120.0)


def write_screen(data, tickers, status="success", finished="2026-09-25T01:23:02+00:00", run_id="1-1", cik=True):
    rows = [row(t, **({"cik": f"{i + 1:010d}"} if cik else {})) for i, t in enumerate(tickers)]
    stamp = datetime.fromisoformat(finished).strftime("%Y%m%dT%H%M%SZ")
    with gzip.open(data / "revision_screen" / f"{stamp}_{run_id}.json.gz", "wt", encoding="utf-8") as h:
        json.dump(snapshot(rows=rows, top_yield=list(tickers), top_growth=[], status=status, run_id=run_id,
                           finished=finished), h)


class SourceFailureTest(RunFixture):
    def entry(self):
        return next(iter(ctx.load_state()["candidates"].values()))

    def test_all_index_and_body_requests_failing_is_failed_not_nothing_relevant(self):
        write_screen(self.data, ["AAA"])
        routes = default_routes()
        routes[cf.filing_index_url(CIK, ACC)] = [HTTPError("u", 503, "x", {}, None)]
        ctx.run_sources(NOW, client(routes)[0])
        entry = self.entry()
        self.assertEqual(entry["status"], "failed")
        self.assertEqual(entry["next_eligible_at"], (NOW + timedelta(hours=24)).isoformat(timespec="seconds"))

    def test_one_document_found_and_one_request_failing_is_partial(self):
        write_screen(self.data, ["AAA"])
        routes = default_routes()
        filings = json.loads(routes[cf.submissions_url(CIK)])
        recent = filings["filings"]["recent"]
        for key, value in (("accessionNumber", "0000000001-26-000011"), ("filingDate", "2026-09-12"), ("form", "6-K"),
                           ("reportDate", ""), ("primaryDocument", ""), ("primaryDocDescription", ""), ("items", "")):
            recent[key].insert(0, value)
        routes[cf.submissions_url(CIK)] = json.dumps(filings).encode()
        routes[cf.filing_index_url(CIK, "0000000001-26-000011")] = [URLError(ConnectionResetError())]
        ctx.run_sources(NOW, client(routes)[0])
        entry = self.entry()
        self.assertEqual((entry["status"], entry["quality"], len(entry["document_ids"])), ("success", "partial", 1))

    def test_partial_sources_make_the_step_degraded(self):
        with mock.patch.object(ctx, "run_sources", return_value={"held": [], "statuses": {"success": 1},
                                                                 "partial_sources": 1, "current": {}}), \
                mock.patch.object(ctx, "run_drafts", return_value={"failed": 0}):
            ctx.main([])
        self.assertEqual(c.read_json(c.DATA_DIR / "run_status.json", {})["candidate_context"]["status"], "degraded")

    def test_held_screen_makes_no_source_or_model_request(self):
        write_screen(self.data, ["AAA"], status="degraded")
        c.atomic_json(ctx.state_path(), {"candidates": {"CAN-0000000000000001": {
            "status": "success", "document_ids": ["DOC-X"], "eps_target_period": "2027-12-31"}},
            "days": {}, "documents_by_source": {}})
        with mock.patch.object(extract, "urlopen", side_effect=AssertionError("model")), \
                mock.patch.object(ctx, "run_sources", wraps=ctx.run_sources) as sources, \
                mock.patch.object(ctx, "run_drafts", side_effect=AssertionError("drafts while held")), \
                mock.patch.object(cf, "direct_open", side_effect=AssertionError("sec")), \
                mock.patch.object(c, "load_dotenv_value", return_value="key"):
            self.assertEqual(ctx.main([]), 0)
        self.assertTrue(sources.called)
        self.assertEqual(c.read_json(c.DATA_DIR / "run_status.json", {})["candidate_context"]["status"], "held")

    def test_only_current_candidates_with_the_same_fiscal_year_get_drafts(self):
        state = {"candidates": {
            "CAN-A": {"status": "success", "document_ids": ["D"], "eps_target_period": "2027-12-31"},
            "CAN-B": {"status": "success", "document_ids": ["D"], "eps_target_period": "2027-12-31"},
            "CAN-C": {"status": "success", "document_ids": ["D"], "eps_target_period": "2026-12-31"}}}
        queue = ctx.draft_queue(state, {"CAN-A": "2027-12-31", "CAN-C": "2027-12-31"}, NOW)
        self.assertEqual([cid for cid, _ in queue], ["CAN-A"])  # B left the list, C's fiscal year rolled

    def test_sources_fine_but_every_draft_failing_is_degraded(self):
        write_screen(self.data, ["AAA"])
        with mock.patch.object(ctx, "run_sources", return_value={"held": [], "statuses": {"success": 1}, "current": {}}), \
                mock.patch.object(ctx, "run_drafts", return_value={"failed": 2, "requests": 2}):
            ctx.main([])
        self.assertEqual(c.read_json(c.DATA_DIR / "run_status.json", {})["candidate_context"]["status"], "degraded")


class SecRequestTest(unittest.TestCase):
    def test_redirects_are_checked_and_counted_before_sending(self):
        start = cf.submissions_url(CIK)
        moved = "https://www.sec.gov/moved.json"
        counted = []
        sec, fake = client({start: [HTTPError(start, 301, "moved", {"Location": moved}, None)], moved: b"{}"})
        sec.on_attempt = lambda: counted.append(len(fake.calls))
        self.assertEqual(sec.get(start)[0], b"{}")
        self.assertEqual(counted, [0, 1])  # each hop counted before its request went out
        evil, fake = client({start: [HTTPError(start, 302, "x", {"Location": "https://evilsec.gov/x"}, None)]})
        with self.assertRaises(ValueError):
            evil.get(start)
        self.assertEqual(len(fake.calls), 1)
        loop = {start: [HTTPError(start, 302, "x", {"Location": start}, None)]}
        looping, fake = client(loop)
        with self.assertRaises(ValueError):
            looping.get(start)
        self.assertLessEqual(len(fake.calls), 4)

    def test_pacing_that_reaches_the_deadline_sends_nothing(self):
        url = cf.submissions_url(CIK)
        sec, fake = client({url: b"{}"}, deadline=0.2)
        cf._last_request[0] = sec.clock()  # the previous SEC request was just now: pacing waits 0.5 s
        with self.assertRaises(cf.Budget):
            sec.get(url)
        self.assertEqual(fake.calls, [])

    def test_the_request_count_is_saved_before_a_crash(self):
        url = cf.submissions_url(CIK)
        saved = []
        sec, _ = client({url: b"{}"})
        sec.opener = mock.Mock(side_effect=KeyboardInterrupt)  # the runner stops mid-request
        sec.on_attempt = lambda: saved.append("counted")
        with self.assertRaises(KeyboardInterrupt):
            sec.get(url)
        self.assertEqual(saved, ["counted"])


# ------------------------------------------------------------------ H3 useful documents

class DocumentRelevanceTest(unittest.TestCase):
    def test_six_k_without_a_table_is_a_results_document(self):
        blocks = cf.normalize_html(b"<html><body><p>BLTE reports results for the first half of fiscal 2026.</p>"
                                   b"<p>Revenue was $12.5 million and net income was $1.2 million.</p></body></html>")
        self.assertTrue(cf.looks_like_earnings(blocks)[0])

    def test_dividend_notice_and_boilerplate_are_not_results(self):
        dividend = cf.normalize_html(b"<html><body><p>The board declared a quarterly dividend of $0.25 per share, "
                                     b"payable next month.</p></body></html>")
        self.assertFalse(cf.looks_like_earnings(dividend)[0])
        boiler = cf.normalize_html(b"<html><body><p>Forward-looking statements: actual results could differ from "
                                   b"expectations for revenue and net income in the fiscal quarter, see risk factors "
                                   b"and our $1.2 million estimate.</p></body></html>")
        self.assertFalse(cf.looks_like_earnings(boiler)[0])

    def test_blocks_about_results_and_guidance_come_first(self):
        record = {"document_id": "DOC-A", "coverage": "complete", "blocks": [
            {"id": "p1", "kind": "p", "text": "About the company: operating income tradition. " * 40},
            {"id": "p2", "kind": "p", "text": "Forward-looking statements and safe harbor for revenue guidance."},
            {"id": "p3", "kind": "p", "text": "Revenue rose due to higher volume; the company expects revenue growth."}]}
        chosen, coverage = ctx.relevant_blocks([record], limit=200)
        self.assertEqual([b["block_id"] for b in chosen], ["p3"])
        self.assertEqual(coverage, "partial")


# ------------------------------------------------------------------ H4 issuer bootstrap

SEC_LIST = {"fields": ["cik", "name", "ticker", "exchange"],
            "data": [[1, "AAA Inc.", "AAA", "Nasdaq"], [2, "BBB Inc.", "BBB", "NYSE"]]}


class IssuerBootstrapTest(RunFixture):
    def test_missing_ciks_are_filled_from_one_sec_list_without_a_screen(self):
        write_screen(self.data, ["AAA"], cik=False)
        routes = default_routes()
        routes[screen_revisions.SEC_URL] = json.dumps(SEC_LIST).encode()
        sec, fake = client(routes)
        with mock.patch.object(screen_revisions, "main", side_effect=AssertionError("screen")):
            report = ctx.run_sources(NOW, sec)
        self.assertEqual(fake.calls.count(screen_revisions.SEC_URL), 1)
        self.assertEqual(report["statuses"], {"success": 1})
        import candidates
        self.assertIn(candidates.candidate_id("NASDAQ:AAA"), ctx.load_state()["candidates"])  # same CAN-ID
        issuers = ctx.load_issuers()
        self.assertEqual((issuers["issuers"]["AAA"]["cik"], len(issuers["source"]["sha256"])), (CIK, 64))

    def test_list_failure_is_recorded_and_the_next_run_recovers(self):
        write_screen(self.data, ["AAA"], cik=False)
        routes = default_routes()
        routes[screen_revisions.SEC_URL] = [HTTPError(screen_revisions.SEC_URL, 500, "x", {}, None)]
        report = ctx.run_sources(NOW, client(routes)[0])
        self.assertIn("issuer_refresh", report)
        entry = next(iter(ctx.load_state()["candidates"].values()))
        self.assertEqual(entry["status"], "unavailable")
        routes[screen_revisions.SEC_URL] = json.dumps(SEC_LIST).encode()
        report = ctx.run_sources(NOW + timedelta(hours=1), client(routes)[0])
        self.assertEqual(report["statuses"], {"success": 1})  # no 7-day wait after the identity came back


# ------------------------------------------------------------------ H5 send-blocked verification

class SendBlockTest(unittest.TestCase):
    def test_delivery_and_command_replies_are_blocked(self):
        with mock.patch.dict(os.environ, {"RESEARCH_DISABLE_SEND": "1"}), \
                mock.patch.object(notify, "urlopen", side_effect=AssertionError("network")):
            self.assertEqual(notify.deliver("t", "c", "m").status, "failed")
            import telegram_cmd
            with mock.patch.object(telegram_cmd, "telegram_request", side_effect=AssertionError("network")):
                with self.assertRaises(RuntimeError):
                    telegram_cmd.send_reply("t", "c", "m")


class ContextVerifyTest(RunFixture):
    def run_verify(self, env, context_main=None, generate=None):
        import candidates
        import context_verify
        with mock.patch.dict(os.environ, env, clear=False), \
                mock.patch.object(ctx, "main", side_effect=context_main or (lambda argv: 0)) as context, \
                mock.patch.object(candidates, "generate", side_effect=generate or (lambda **kw: {})):
            code = context_verify.main()
        return code, context

    def test_refuses_without_the_block_or_with_telegram_credentials(self):
        import context_verify
        with mock.patch.dict(os.environ, {"RESEARCH_DISABLE_SEND": ""}):
            with self.assertRaises(ValueError):
                context_verify.main()
        with mock.patch.dict(os.environ, {"RESEARCH_DISABLE_SEND": "1", "TELEGRAM_BOT_TOKEN": "x"}):
            with self.assertRaises(ValueError):
                context_verify.main()

    def test_cache_only_calls_nothing_and_leaves_counters_and_observations(self):
        c.atomic_json(self.data / "model_budget.json", {"days": {"2026-09-25": {"cards": 1}}})
        c.atomic_json(ctx.state_path(), {"candidates": {}, "days": {}, "documents_by_source": {}})
        obs = self.data / "candidate_observations"
        obs.mkdir()
        c.atomic_json(obs / "OB-0000000000000001.json", {"x": 1})
        env = {"RESEARCH_DISABLE_SEND": "1", "VERIFY_CACHE_ONLY": "true", "TELEGRAM_BOT_TOKEN": "",
               "TELEGRAM_CHAT_ID": ""}
        code, context = self.run_verify(env)
        self.assertEqual((code, context.called), (0, False))
        spend = lambda **kw: c.atomic_json(self.data / "model_budget.json", {"days": {"2026-09-25": {"cards": 2}}})
        with self.assertRaisesRegex(ValueError, "protected state"):
            self.run_verify(env, generate=spend)

    def test_a_changed_delivery_ledger_fails_the_verification(self):
        c.atomic_json(self.data / "candidate_alerts.json", {"events": {}})
        env = {"RESEARCH_DISABLE_SEND": "1", "VERIFY_CACHE_ONLY": "false", "TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}
        touch = lambda argv: (c.atomic_json(self.data / "candidate_alerts.json", {"events": {"x": 1}}), 0)[1]
        with self.assertRaisesRegex(ValueError, "protected state"):
            self.run_verify(env, context_main=touch)
        self.assertEqual(c.read_json(c.DATA_DIR / "run_status.json", {})["context_verification"]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
