"""G1: issuer mapping, SEC filing selection, normalization and paced, budgeted collection."""
import contextlib
import gzip
import io
import json
import pathlib
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock
from urllib.error import HTTPError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common as c  # noqa: E402
import candidate_context as ctx  # noqa: E402
import company_filings as cf  # noqa: E402
import screen_revisions  # noqa: E402
from test_candidates import isolate_ci_environment, row, snapshot  # noqa: E402

NOW = datetime(2026, 9, 25, 3, 0, tzinfo=timezone.utc)
CIK = "0000000001"
ACC = "0000000001-26-000010"
BASE = f"https://www.sec.gov/Archives/edgar/data/1/{ACC.replace('-', '')}/"

RELEASE = b"""<html><head><script>var x=1;</script><style>p{}</style></head><body>
<p>AAA Inc. Reports Second Quarter Fiscal 2027 Results</p>
<p>Revenue grew 40% year over year to $120.0 million. Net income was $15.2 million.</p>
<p>Outlook: for the third quarter the company expects revenue of $130 million to $135 million.</p>
<table><tr><td>Net income (loss)</td><td>$</td><td>15.2</td><td></td><td>(</td><td>1.3</td><td>)</td></tr>
<tr><td>Gross margin</td><td>41.5</td><td>%</td></tr></table>
<p>Earnings per share and operating income are shown in the tables.</p></body></html>"""
UNRELATED = b"<html><body><p>AAA appoints a new director to its board.</p></body></html>"


def submissions(entries):
    keys = ("accessionNumber", "filingDate", "reportDate", "form", "primaryDocument", "primaryDocDescription", "items")
    return {"name": "AAA Inc.", "filings": {"recent": {k: [e.get(k, "") for e in entries] for k in keys}}}


def index_page(rows):
    body = "".join(f'<tr><td>{i}</td><td>{d}</td><td><a href="{h}">{n}</a></td><td>{t}</td><td>1</td></tr>'
                   for i, (d, n, h, t) in enumerate(rows, 1))
    return f"<table><tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th><th>Size</th></tr>{body}</table>"


class FakeResponse(io.BytesIO):
    def __init__(self, body, url):
        super().__init__(body)
        self.url = url

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeSec:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, request, timeout=None):
        url = request.full_url
        self.calls.append(url)
        answer = self.routes.get(url)
        if answer is None:
            raise HTTPError(url, 404, "nf", {}, None)
        if isinstance(answer, list):
            answer = answer.pop(0) if len(answer) > 1 else answer[0]
        if isinstance(answer, Exception):
            raise answer
        return FakeResponse(answer, url)


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


def client(routes, attempts=100, deadline=180.0, max_bytes=2_000_000):
    clock = Clock()
    fake = FakeSec(routes)
    return cf.SecClient(user_agent="test", attempts_left=attempts, deadline=deadline, clock=clock, sleep=clock.sleep,
                        opener=fake, max_bytes=max_bytes), fake


def default_routes():
    filings = [{"accessionNumber": ACC, "filingDate": "2026-09-10", "form": "8-K", "items": "2.02,9.01"},
               {"accessionNumber": "0000000001-26-000009", "filingDate": "2026-09-01", "form": "8-K", "items": "5.02"},
               {"accessionNumber": "0000000001-26-000001", "filingDate": "2026-01-10", "form": "8-K", "items": "2.02"}]
    return {cf.submissions_url(CIK): json.dumps(submissions(filings)).encode(),
            cf.filing_index_url(CIK, ACC): index_page([
                ("Press release", "ex991.htm", BASE + "ex991.htm", "EX-99.1"),
                ("Other", "ex992.htm", BASE + "ex992.htm", "EX-99.2"),
                ("8-K", "form8k.htm", BASE + "form8k.htm", "8-K")]).encode(),
            BASE + "ex991.htm": RELEASE, BASE + "ex992.htm": UNRELATED}


class IssuerTest(unittest.TestCase):
    def test_mapping_sources_conflicts_and_share_classes(self):
        cached = {"source": {"sha256": "s", "observed_at": "t"},
                  "issuers": {"OLD": {"cik": "0000000007", "exchange": "NYSE", "name": "Old"}}}
        issuer, problem = ctx.issuer_for({"ticker": "AAA", "exchange": "Nasdaq", "cik": "1"}, {}, cached)
        self.assertEqual((issuer["cik"], problem), (CIK, None))
        self.assertEqual(ctx.issuer_for({"ticker": "OLD", "exchange": "NYSE"}, {}, cached)[0]["cik"], "0000000007")
        self.assertEqual(ctx.issuer_for({"ticker": "OLD", "exchange": "Nasdaq"}, {}, cached), (None, "unavailable"))
        self.assertEqual(ctx.issuer_for({"ticker": "ZZZ", "exchange": "NYSE"}, {}, cached), (None, "unavailable"))
        registry = {"CRDO": {"entity_id": "NASDAQ:CRDO", "aliases": ["CIK:0001807794"]}}
        self.assertEqual(ctx.issuer_for({"ticker": "CRDO", "exchange": "Nasdaq", "cik": "1807794"}, registry, cached)[1], None)
        self.assertEqual(ctx.issuer_for({"ticker": "CRDO", "exchange": "Nasdaq", "cik": "99"}, registry, cached),
                         (None, "identity_conflict"))
        # Two share classes of one issuer: same CIK, separate candidates (IDs unchanged).
        snap = snapshot(rows=[row("GOOA", cik="0001652044"), row("GOOB", cik="0001652044", by_yield=False)],
                        top_yield=["GOOA"], top_growth=["GOOB"])
        found = ctx.targets(snap, {}, cached, {})
        self.assertEqual({t["issuer"]["cik"] for t in found}, {"0001652044"})
        self.assertEqual(len({t["candidate_id"] for t in found}), 2)
        import candidates
        self.assertEqual(found[0]["candidate_id"], candidates.candidate_id("NASDAQ:GOOA"))  # not replaced by the CIK


class DocumentTest(unittest.TestCase):
    def test_filing_selection_window_and_order(self):
        rows = cf.recent_filings(submissions([
            {"accessionNumber": "a", "filingDate": "2026-09-10", "form": "8-K", "items": "2.02"},
            {"accessionNumber": "b", "filingDate": "2026-09-01", "form": "8-K", "items": "5.02"},
            {"accessionNumber": "c", "filingDate": "2026-08-01", "form": "10-Q"},
            {"accessionNumber": "d", "filingDate": "2026-09-20", "form": "6-K"},
            {"accessionNumber": "e", "filingDate": "2026-01-01", "form": "8-K", "items": "2.02"}]), NOW.date())
        self.assertEqual([r["accessionNumber"] for r in rows], ["a", "d", "c"])

    def test_index_parsing_and_exhibit_choice(self):
        docs = cf.filing_documents(default_routes()[cf.filing_index_url(CIK, ACC)].decode(), BASE)
        self.assertEqual([d["type"] for d in cf.pick_documents(docs, "8-K")], ["EX-99.1", "EX-99.2"])

    def test_normalization_keeps_tables_and_negatives_and_drops_scripts(self):
        blocks = cf.normalize_html(RELEASE)
        text = json.dumps(blocks)
        self.assertNotIn("var x", text)
        table = next(b for b in blocks if b["kind"] == "table")
        self.assertEqual(table["rows"][0], ["Net income (loss)", "$15.2", "(1.3)"])
        self.assertEqual(table["rows"][1], ["Gross margin", "41.5%"])
        self.assertEqual([b["id"] for b in blocks if b["kind"] == "p"][:2], ["p1", "p2"])
        self.assertTrue(cf.looks_like_earnings(blocks)[0])
        self.assertFalse(cf.looks_like_earnings(cf.normalize_html(UNRELATED))[0])

    def test_pdf_is_unsupported_and_ids_follow_content(self):
        issuer = {"cik": CIK, "ticker": "AAA"}
        filing = {"accessionNumber": ACC, "form": "8-K", "filingDate": "2026-09-10"}
        doc = {"url": BASE + "deck.pdf", "name": "deck.pdf", "type": "EX-99.2", "description": "Deck"}
        pdf = cf.build_record(issuer, filing, doc, b"%PDF-1.4 ...", doc["url"], False, NOW.isoformat())
        self.assertEqual((pdf["status"], pdf["relevance"]["earnings"]), ("unsupported_content", False))
        doc = {"url": BASE + "ex991.htm", "name": "ex991.htm", "type": "EX-99.1", "description": "Release"}
        first = cf.build_record(issuer, filing, doc, RELEASE, doc["url"], False, NOW.isoformat())
        again = cf.build_record(issuer, filing, doc, RELEASE, doc["url"], False, (NOW + timedelta(days=1)).isoformat())
        corrected = cf.build_record(issuer, filing, doc, RELEASE + b"<p>Corrected.</p>", doc["url"], False, NOW.isoformat())
        self.assertEqual(first["document_id"], again["document_id"])
        self.assertNotEqual(first["document_id"], corrected["document_id"])
        self.assertIsNone(first["published_at"])  # no invented release time; filed_at is the SEC date


class ClientTest(unittest.TestCase):
    def test_retry_after_within_budget_then_success(self):
        url = cf.submissions_url(CIK)
        sec, fake = client({url: [HTTPError(url, 429, "slow", {"Retry-After": "3"}, None), b"{}"]})
        self.assertEqual(sec.get(url)[0], b"{}")
        self.assertEqual((len(fake.calls), sec.attempts), (2, 2))

    def test_retry_after_longer_than_the_budget_is_deferred(self):
        url = cf.submissions_url(CIK)
        sec, fake = client({url: [HTTPError(url, 503, "busy", {"Retry-After": "500"}, None)]})
        with self.assertRaises(cf.Budget):
            sec.get(url)
        self.assertEqual(len(fake.calls), 1)
        self.assertLess(sec.clock(), 180)  # it did not sleep 500 seconds first

    def test_repeated_403_blocks_the_provider(self):
        url = cf.submissions_url(CIK)
        sec, _ = client({url: [HTTPError(url, 403, "no", {}, None)]})
        with self.assertRaises(HTTPError):
            sec.get(url)
        with self.assertRaises(cf.Blocked):
            sec.get(url)

    def test_no_request_without_attempts_or_time_and_size_is_capped(self):
        url = cf.submissions_url(CIK)
        sec, fake = client({url: b"x" * 50}, attempts=0)
        with self.assertRaises(cf.Budget):
            sec.get(url)
        self.assertEqual(fake.calls, [])
        sec, _ = client({url: b"x" * 50}, max_bytes=10)
        body, _, truncated = sec.get(url)
        self.assertEqual((len(body), truncated), (10, True))
        with self.assertRaises(ValueError):
            sec.get("https://example.com/x")


class RunFixture(unittest.TestCase):
    """Temporary data and screener directories (no tests of its own)."""

    def setUp(self):
        isolate_ci_environment(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data = pathlib.Path(tmp.name)
        (self.data / "revision_screen").mkdir()
        for patch in (mock.patch.object(c, "DATA_DIR", self.data),
                      mock.patch.object(screen_revisions, "SCREEN_DIR", self.data / "revision_screen"),
                      contextlib.redirect_stdout(io.StringIO())):
            patch.__enter__()
            self.addCleanup(patch.__exit__, None, None, None)

    def screen(self, tickers, run_id="1-1", status="success", finished="2026-09-25T01:23:02+00:00"):
        rows = [row(t, cik=f"{i + 1:010d}") for i, t in enumerate(tickers)]
        stamp = datetime.fromisoformat(finished).strftime("%Y%m%dT%H%M%SZ")
        with gzip.open(self.data / "revision_screen" / f"{stamp}_{run_id}.json.gz", "wt", encoding="utf-8") as h:
            json.dump(snapshot(rows=rows, top_yield=list(tickers), top_growth=[], status=status, run_id=run_id,
                               finished=finished), h)

class RunTest(RunFixture):
    def test_success_documents_and_cache(self):
        self.screen(["AAA"])
        sec, fake = client(default_routes())
        report = ctx.run_sources(NOW, sec)
        self.assertEqual(report["statuses"], {"success": 1})
        entry = ctx.load_state()["candidates"][next(iter(ctx.load_state()["candidates"]))]
        self.assertEqual(len(entry["document_ids"]), 1)
        record = cf.load_document(entry["document_ids"][0])
        self.assertEqual((record["form"], record["document_type"], record["issuer"]["cik"]), ("8-K", "EX-99.1", CIK))
        # Next week: the same filing's body comes from the cache, not the network.
        self.screen(["AAA"], run_id="2-1", finished="2026-10-03T01:23:02+00:00")
        sec2, fake2 = client(default_routes())
        report = ctx.run_sources(NOW + timedelta(days=8), sec2)
        self.assertEqual(report["researched"], 1)
        self.assertIn(cf.submissions_url(CIK), fake2.calls)
        self.assertNotIn(BASE + "ex991.htm", fake2.calls)

    def test_same_day_candidates_follow_display_order_and_periodic_reports_are_skipped(self):
        import candidates
        tickers = ["AAA", "BBB", "CCC"]
        self.screen(tickers)
        snap = json.load(gzip.open(next((self.data / "revision_screen").glob("*.json.gz")), "rt", encoding="utf-8"))
        # First seen seconds apart on one day, in the reverse of the display order.
        seen = {candidates.candidate_id(f"NASDAQ:{t}"): f"2026-09-25T01:1{9 - i}:00+00:00" for i, t in enumerate(tickers)}
        found = ctx.targets(snap, {}, {}, seen)
        state = ctx.load_state()
        self.assertEqual([t["ticker"] for t in ctx.select(found, state, NOW, 3)], tickers)
        routes = default_routes()
        filings = json.loads(routes[cf.submissions_url(CIK)])
        recent = filings["filings"]["recent"]
        for key, value in (("accessionNumber", "0000000001-26-000011"), ("filingDate", "2026-09-10"), ("form", "10-Q"),
                           ("reportDate", ""), ("primaryDocument", ""), ("primaryDocDescription", ""), ("items", "")):
            recent[key].append(value)
        routes[cf.submissions_url(CIK)] = json.dumps(filings).encode()
        sec, fake = client(routes)
        target = {"issuer": {"cik": CIK, "ticker": "AAA"}}
        ctx.research(target, sec, ctx.load_state(), NOW, ctx.settings())
        self.assertFalse(any("000000000126000011" in u for u in fake.calls))

    def test_no_relevant_document_waits_seven_days_and_failures_24_hours(self):
        self.screen(["AAA"])
        routes = default_routes()
        routes[BASE + "ex991.htm"] = UNRELATED
        ctx.run_sources(NOW, client(routes)[0])
        entry = next(iter(ctx.load_state()["candidates"].values()))
        self.assertEqual(entry["status"], "no_relevant_document")
        self.assertEqual(entry["next_eligible_at"], (NOW + timedelta(days=7)).isoformat(timespec="seconds"))
        sec, fake = client(routes)
        ctx.run_sources(NOW + timedelta(days=1), sec)
        self.assertEqual(fake.calls, [])

    def test_daily_company_and_request_limits_hold_across_runs_and_rotate(self):
        tickers = [f"T{i:02d}" for i in range(14)]
        self.screen(tickers)
        empty = json.dumps(submissions([])).encode()
        routes = {cf.submissions_url(f"{i + 1:010d}"): empty for i in range(14)}
        ctx.run_sources(NOW, client(routes)[0])
        state = ctx.load_state()
        self.assertEqual(state["days"]["2026-09-25"]["companies"], 10)
        sec, fake = client(routes)
        ctx.run_sources(NOW + timedelta(hours=5), sec)  # a second auto the same day
        self.assertEqual(fake.calls, [])
        sec, fake = client(routes)
        ctx.run_sources(NOW + timedelta(days=1), sec)  # the four that waited go first
        self.assertEqual(len(fake.calls), 4)

    def test_request_budget_defers_without_failure(self):
        self.screen(["AAA"])
        sec, _ = client(default_routes(), attempts=1)
        report = ctx.run_sources(NOW, sec)
        entry = next(iter(ctx.load_state()["candidates"].values()))
        self.assertEqual(entry["status"], "deferred_budget")
        self.assertNotIn("failed", report["statuses"])

    def test_stale_or_partial_screen_holds_new_research(self):
        self.screen(["AAA"], status="degraded")
        sec, fake = client(default_routes())
        report = ctx.run_sources(NOW, sec)
        self.assertEqual((report["held"], fake.calls), (["partial_screen"], []))

    def test_identity_problem_is_recorded_without_requests(self):
        with gzip.open(self.data / "revision_screen" / "20260925T010000Z_1-1.json.gz", "wt", encoding="utf-8") as h:
            json.dump(snapshot(rows=[row("NOCIK")], top_yield=["NOCIK"], top_growth=[]), h)
        sec, fake = client({})
        ctx.run_sources(NOW, sec)
        self.assertEqual((next(iter(ctx.load_state()["candidates"].values()))["status"], fake.calls), ("unavailable", [screen_revisions.SEC_URL]))


def release_record(document_id="DOC-A", text=RELEASE):
    issuer = {"cik": CIK, "ticker": "AAA"}
    filing = {"accessionNumber": ACC, "form": "8-K", "filingDate": "2026-09-10"}
    doc = {"url": BASE + "ex991.htm", "name": "ex991.htm", "type": "EX-99.1", "description": "Release"}
    record = cf.build_record(issuer, filing, doc, text, doc["url"], False, NOW.isoformat())
    record["document_id"] = document_id
    return record


def claim(**fields):
    base = {"note_ko": "회사가 매출 증가를 보고했습니다.", "kind": "fact", "subject": "issuer",
            "metric": "revenue", "figures": ["40%", "$120.0 million"],
            "quote": "Revenue grew 40% year over year to $120.0 million.", "document_id": "DOC-A", "block_id": "p2",
            "period": "unknown", "currency": "USD", "gaap": "unknown", "drivers": ["volume"], "direction": "positive"}
    base.update(fields)
    return base


class DraftCheckTest(unittest.TestCase):
    def setUp(self):
        self.blocks, _ = ctx.relevant_blocks([release_record()])

    def check(self, **fields):
        return ctx.validate_draft({"claims": [claim(**fields)], "link": "unconfirmed"}, self.blocks)

    def rejected(self, **fields):
        result = self.check(**fields)
        self.assertEqual(result["claims"], [])
        return result["rejected"][0]["reason"]

    def test_supported_fact_and_guidance_pass(self):
        self.assertEqual(len(self.check()["claims"]), 1)
        result = self.check(kind="guidance", block_id="p3", figures=["$130 million", "$135 million"],
                            note_ko="회사가 다음 분기 매출 전망을 제시했습니다.",
                            quote="the company expects revenue of $130 million to $135 million")
        self.assertEqual(len(result["claims"]), 1)

    def test_unsupported_outputs_are_refused(self):
        self.assertEqual(self.rejected(quote="Revenue tripled to a record."), "quote_not_in_block")
        self.assertEqual(self.rejected(figures=["55%"]), "figure_not_verbatim")
        self.assertEqual(self.rejected(block_id="p99"), "unknown_block")
        self.assertEqual(self.rejected(note_ko="매수하세요"), "forbidden_wording")
        self.assertEqual(self.rejected(currency="EUR"), "currency_not_in_figures")
        self.assertEqual(self.rejected(unit="billion"), "unit_not_in_figures")
        self.assertEqual(self.rejected(gaap="GAAP"), "gaap_not_as_stated")

    def test_period_and_free_numeric_notes_are_rejected(self):
        self.assertEqual(self.rejected(period="Q3 FY2028"), "period_not_in_source")
        self.assertEqual(self.rejected(note_ko="매출은 5 billion EUR입니다."), "number_or_unit_in_note")

    def test_a_lowered_outlook_is_never_called_a_raise(self):
        quote = "The company lowered its revenue guidance to $5 million."
        blocks = [{"document_id":"DOC-A", "block_id":"p1", "text":quote}]
        base = claim(block_id="p1", quote=quote, figures=["$5 million"], kind="guidance")
        bad = ctx.validate_draft({"claims":[{**base,"note_ko":"회사가 전망을 상향했습니다."}]}, blocks)
        good = ctx.validate_draft({"claims":[{**base,"note_ko":"회사가 전망을 하향했습니다."}]}, blocks)
        self.assertEqual((len(bad["claims"]),len(good["claims"])),(0,1))

    def test_typographic_quotes_and_object_next_checks(self):
        quote="The company’s revenue grew 40%"
        blocks=[{"document_id":"DOC-A","block_id":"p1","text":quote}]
        result=ctx.validate_draft({"claims":[claim(block_id="p1",quote="The company's revenue grew 40%",
                    figures=["40%"],currency=None)],"next_check":[{"text_ko":"다음 분기 수주 확인"},7]},blocks)
        self.assertEqual(len(result["claims"]),1)
        self.assertEqual(result["next_check"],["다음 분기 수주 확인"])

    def test_quarter_ordinals_are_preserved_not_invented(self):
        quote="Second quarter revenue grew 40% as of July 30"
        blocks=[{"document_id":"DOC-A","block_id":"p1","text":quote}]
        base=claim(block_id="p1",quote=quote,figures=["40%"],currency=None,period="Second quarter")
        self.assertEqual(len(ctx.validate_draft({"claims":[base]},blocks)["claims"]),1)
        self.assertEqual(ctx.validate_draft({"claims":[{**base,"period":"Third quarter"}]},blocks)["claims"],[])

    def test_explicit_link_is_never_automatic(self):
        blocks=self.blocks+[{"document_id":"DOC-A","block_id":"p99","text":"Analyst consensus is elsewhere."}]
        result=ctx.validate_draft({"claims":[claim()],"link":"explicit_link"},blocks)
        self.assertEqual(result["link"],"unconfirmed")

    def test_subsidiary_is_not_issuer_earnings(self):
        quote="MPLX expects distributions of $5 million."
        base=claim(quote=quote,block_id="p1",metric="distributions",kind="guidance",figures=["$5 million"])
        blocks=[{"document_id":"DOC-A","block_id":"p1","text":quote}]
        self.assertEqual(ctx.validate_draft({"claims":[base]},blocks,{"ticker":"MPC"})["claims"],[])
        sub={**base,"subject":"subsidiary","subject_name":"MPLX"}
        self.assertEqual(ctx.validate_draft({"claims":[sub]},blocks,{"ticker":"MPC"})["context_status"],"insufficient_earnings_context")

    def test_limitations_use_same_currency_checks(self):
        result=ctx.validate_draft({"limitations":[claim(currency="EUR")]},self.blocks)
        self.assertEqual(result["limitations"],[])


class DraftRunTest(RunFixture):
    def setUp(self):
        super().setUp()
        cf.store_document(release_record())
        entry = {"status": "success", "ticker": "AAA", "document_ids": ["DOC-A"], "eps_target_period": "2027-12-31",
                 "issuer": {"cik": CIK}, "attempted_at": NOW.isoformat()}
        state = {"candidates": {f"CAN-{i:016X}": {**entry, "ticker": f"T{i}"} for i in range(8)},
                 "days": {}, "documents_by_source": {}}
        c.atomic_json(ctx.state_path(), state)
        self.prompts = []
        patch = mock.patch.object(c, "policy", return_value={**c.policy(), "max_model_calls": 20,
                                                             "model_budget": {"candidate_context": 6}})
        patch.start()
        self.addCleanup(patch.stop)

    def gemini(self, request, timeout=None):
        prompt = json.loads(request.data)["contents"][0]["parts"][0]["text"]
        self.prompts.append(prompt)
        body = json.dumps({"claims": [claim()], "limitations": [], "next_check": ["3분기 실적 발표 확인"],
                           "link": "temporal_context"})
        return FakeResponse(json.dumps({"candidates": [{"content": {"parts": [{"text": body}]}}]}).encode(), "x")

    def test_one_company_per_request_six_requests_a_day_and_cache(self):
        import extract
        with mock.patch.object(c, "load_dotenv_value", return_value="key"), \
                mock.patch.object(extract, "urlopen", side_effect=self.gemini), \
                mock.patch.object(c, "today", return_value="2026-09-25"):
            # Both days are pinned: the budget day must not depend on the date the tests run.
            report = ctx.run_drafts(NOW)
            self.assertEqual((report["insufficient_earnings_context"], report["deferred"]), (6, 2))
            self.assertTrue(all(sum(f"회사: T{i} (" in p for i in range(8)) == 1 for p in self.prompts))
            again = ctx.run_drafts(NOW)  # same day: no budget left
            self.assertEqual((len(self.prompts), again["drafted"]), (6, 0))
            with mock.patch.object(c, "today", return_value="2026-09-26"):
                tomorrow = ctx.run_drafts(NOW + timedelta(days=1))  # budget resets; drafted inputs are not asked again
        self.assertEqual((len(self.prompts), tomorrow["insufficient_earnings_context"]), (8, 2))
        record = json.loads(next(ctx.history_dir().glob("CTX-*.json")).read_text(encoding="utf-8"))
        self.assertEqual((record["context_status"], record["review"], record["link"]),
                         ("insufficient_earnings_context", "자동 정리·미검토", "temporal_context"))
        self.assertFalse((self.data / "candidate_evidence.json").exists())  # never the human evidence file
        self.assertFalse((self.data / "investment_review_log.csv").exists())

    def test_missing_model_key_makes_no_request(self):
        import extract
        with mock.patch.object(c, "load_dotenv_value", return_value=""), \
                mock.patch.object(extract, "urlopen", side_effect=AssertionError("request")):
            self.assertEqual(ctx.run_drafts(NOW)["skipped"], "model_key_missing")


if __name__ == "__main__":
    unittest.main()
