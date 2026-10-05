"""P regression tests (docs/p_o_acceptance_and_discovery_followup_2026-10-05.md). Stored inputs and fakes only."""
import json
import pathlib
import re
import sys
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import candidate_context as ctx  # noqa: E402
import common as c  # noqa: E402
import company_filings as cf  # noqa: E402
import extract  # noqa: E402
from test_candidate_context import claim  # noqa: E402


def stored_novt_item():
    state = json.loads((ROOT / "data" / "processed" / "source_state.json").read_text(encoding="utf-8"))
    return next(v for v in state.values() if v.get("signal_id") == "SIG-0900")["item"]


NOVT_QUOTE = ("Contract liabilities related to customer prepayments and accrued customer rebates totaled $3,312,226 "
              "and $1,058,978 as of December 31, 2025 and January 1, 2025, respectively.")


class SubjectNewsPathTest(unittest.TestCase):
    """P0: a quote in another company's own statements is not the filer's signal."""

    def test_stored_novt_input_is_refused(self):
        item = stored_novt_item()
        problem = extract.evidence_subject_problem(NOVT_QUOTE, item["raw_text"], item)
        self.assertTrue(problem.startswith("subject_other_entity"))
        self.assertIn("Runway Buyer, LLC", problem)

    def test_own_statements_and_an_acquisition_fact_are_kept(self):
        own = ("NOVANTA INC (NOVT) (CIK 0001076930) EX-99.1. Novanta Inc. CONSOLIDATED STATEMENTS OF OPERATIONS "
               "Revenue was $250.1 million in the quarter.")
        item = {"title": "NOVANTA INC (NOVT, NOVTU) (CIK 0001076930) EX-99.1 2026-10-02"}
        self.assertIsNone(extract.evidence_subject_problem("Revenue was $250.1 million in the quarter.", own, item))
        deal = ("Novanta Inc. completed the acquisition of Runway Buyer, LLC for $300 million on October 1, 2026. "
                "Runway Buyer, LLC CONSOLIDATED STATEMENT OF CASH FLOWS Net income $ 11,462,563")
        self.assertIsNone(extract.evidence_subject_problem(
            "Novanta Inc. completed the acquisition of Runway Buyer, LLC for $300 million", deal, item))
        self.assertTrue(extract.evidence_subject_problem("Net income $ 11,462,563", deal, item)
                        .startswith("subject_other_entity"))

    def test_q0_a_news_quote_under_a_name_sharing_entity_is_unverified(self):
        text = ("NORTHSTAR MANUFACTURING INC (NSM) EX-99.1. Northstar Acquisition LLC CONSOLIDATED STATEMENTS OF "
                "OPERATIONS Revenue was $40.0 million in 2025.")
        item = {"title": "NORTHSTAR MANUFACTURING INC (NSM) (CIK 0000000009) EX-99.1 2026-10-02"}
        self.assertTrue(extract.evidence_subject_problem("Revenue was $40.0 million in 2025.", text, item)
                        .startswith("subject_unverified"))

    def test_an_unreadable_filer_is_unverified(self):
        item = stored_novt_item()
        problem = extract.evidence_subject_problem(NOVT_QUOTE, item["raw_text"], {"title": ""})
        self.assertTrue(problem.startswith("subject_unverified"))


class SubjectDraftPathTest(unittest.TestCase):
    """P0 in the validator (context-check-v10): blocks under another entity's statements."""

    TEXT = "Net income was $11.5 million in 2025."

    def run_with(self, scope, issuer_name="Novanta Inc."):
        blocks = [{"document_id": "DOC-A", "block_id": "p1", "text": self.TEXT, "scope": scope}]
        item = claim(quote=self.TEXT, block_id="p1", document_id="DOC-A", metric="Net income",
                     figures=["$11.5 million"], period="2025", note_ko="순이익이 기재되어 있다")
        return ctx.validate_draft({"claims": [item], "link": "unconfirmed"}, blocks, {"ticker": "NOVT", "name": issuer_name})

    def test_other_entity_unverified_and_own(self):
        self.assertEqual(self.run_with("Runway Buyer, LLC")["rejected"][0]["reason"], "subject_other_entity")
        self.assertEqual(self.run_with("Runway Buyer, LLC", issuer_name=None)["rejected"][0]["reason"], "subject_unverified")
        self.assertEqual(len(self.run_with("Novanta Inc.")["claims"]), 1)
        self.assertEqual(len(self.run_with(None)["claims"]), 1)  # no statement heading: the usual checks only
        self.assertEqual(ctx.PARSER_VERSION, "context-check-v11")
        self.assertIn("context-check-v10", ctx.REVALIDATED_VERSIONS)

    def test_q0_a_shared_name_word_is_unverified_not_the_same_company(self):
        answer = self.run_with("Northstar Acquisition LLC", issuer_name="Northstar Manufacturing Inc.")
        self.assertEqual((len(answer["claims"]), answer["rejected"][0]["reason"]), (0, "subject_unverified"))
        self.assertEqual(self.run_with("PBF Holding Company LLC", issuer_name="PBF Energy Inc.")["rejected"][0]["reason"],
                         "subject_unverified")  # a subsidiary is not merged into the parent by a shared word
        for heading, issuer in (("NOVANTA INC.", "Novanta Inc"), ("Valero Energy Corporation", "VALERO ENERGY CORP/TX"),
                                ("Cracker Barrel Old Country Store, Inc.", "CRACKER BARREL OLD COUNTRY STORE, INC")):
            self.assertEqual(len(self.run_with(heading, issuer_name=issuer)["claims"]), 1, heading)

    def test_q0_a_a_cik_linked_former_name_is_the_filer(self):
        blocks = [{"document_id": "DOC-A", "block_id": "p1", "text": self.TEXT, "scope": "Old Name Corp"}]
        item = claim(quote=self.TEXT, block_id="p1", document_id="DOC-A", metric="Net income",
                     figures=["$11.5 million"], period="2025", note_ko="순이익이 기재되어 있다")
        issuer = {"ticker": "NEW", "name": "New Name Inc.", "aliases": ["OLD NAME CORP/DE"]}
        self.assertEqual(len(ctx.validate_draft({"claims": [item], "link": "unconfirmed"}, blocks, issuer)["claims"]), 1)
        self.assertEqual(cf.same_entity("Old Name Corp", "New Name Inc."), None)

    def test_block_scopes_follow_document_order(self):
        blocks = cf.normalize_html(b"<p>Novanta reports results.</p><p>Runway Buyer, LLC CONSOLIDATED STATEMENT OF "
                                   b"CASH FLOWS</p><p>Net income $ 11,462,563</p>")
        scopes = cf.block_scopes(blocks)
        self.assertEqual([scopes.get(b["id"]) for b in blocks], [None, "Runway Buyer, LLC", "Runway Buyer, LLC"])


def html(*paragraphs):
    return ("<html><body>" + "".join(f"<p>{p}</p>" for p in paragraphs) + "</body></html>").encode()


BOARD = html("AAA Inc. announced that its board appointed a new director effective October 1, 2026.")
DIVIDEND = html("The board increases the quarterly dividend to $0.25 per share and expects payment in October.")
CONTRACT_MAIN = html("On September 22, 2026, AAA Inc. entered into a multi-year supply agreement with a data center "
                     "customer that is expected to generate approximately $40 million of revenue in fiscal 2027.")


class UpdateJudgmentTest(unittest.TestCase):
    """P1-A: one sentence names the business event and carries its number; excluded topics never count."""

    def judge(self, *paragraphs):
        return cf.business_update_judgment(cf.normalize_html(html(*paragraphs)), "AAA Inc.")[0]

    def test_words_and_numbers_from_different_sentences_do_not_add_up(self):
        self.assertFalse(self.judge("Revenue was $50 million in the quarter.", "The company signed a supply agreement."))
        self.assertFalse(self.judge("We expect growth. Our capacity is large.", "Net income was $5 million."))

    def test_finance_and_a_real_event_in_one_document(self):
        self.assertFalse(self.judge("The company entered into a credit agreement with borrowing capacity of $500 million."))
        self.assertTrue(self.judge("The board declared a dividend of $0.25 per share.",
                                   "AAA Inc. received orders of $35 million from a new customer for delivery in 2027."))
        self.assertTrue(self.judge("AAA Inc. raises fiscal 2027 revenue guidance to $150 million."))

    def test_v3_company_description_tables_and_static_capacity_are_not_events(self):
        # 10/5 operation: a director-election release passed on its 'About Valero' paragraph.
        self.assertFalse(self.judge(
            "Valero Energy Corporation Elects Matt Audette to its Board of Directors",
            "About Valero",
            "Valero is a joint venture member in Diamond Green Diesel Holdings LLC, which produces renewable diesel, "
            "with a production capacity of approximately 1.2 billion gallons per year in the U.S."))
        self.assertFalse(self.judge("Our plant has a production capacity of 40,000 tons per year at 90% utilization."))
        self.assertTrue(self.judge("AAA Inc. will expand production capacity by 40% to 50,000 tons in 2027."))
        self.assertFalse(self.judge("We raised prices in order to offset a 5% cost increase."))
        blocks = cf.normalize_html("<html><body><table><tr><td>Amortization of acquired intangibles</td>"
                                   "<td>$114,916</td></tr></table></body></html>".encode())
        self.assertFalse(cf.business_update_judgment(blocks, "AAA Inc.")[0])
        self.assertTrue(self.judge("The company has acquired Beta Systems for $400 million in cash."))

    def test_an_acquired_business_statement_is_not_the_filers_update(self):
        blocks = cf.normalize_html(html("Runway Buyer, LLC CONSOLIDATED STATEMENT OF CASH FLOWS",
                                        "Customer orders of $3.3 million were received."))
        self.assertFalse(cf.business_update_judgment(blocks, "Novanta Inc.")[0])


class UpdateResearchPathTest(unittest.TestCase):
    """P1-A through research(): budget protection, EX-99-less text, cached judgment."""

    def setUp(self):
        import test_candidate_context as tc
        self.tc = tc
        self.fixture = tc.RunFixture()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def routes(self, update_docs, update_main=None):
        tc = self.tc
        acc_a, acc_b = "0000000001-26-000020", "0000000001-26-000021"
        base_a = f"https://www.sec.gov/Archives/edgar/data/1/{acc_a.replace('-', '')}/"
        base_b = f"https://www.sec.gov/Archives/edgar/data/1/{acc_b.replace('-', '')}/"
        routes = tc.default_routes()
        filings = [{"accessionNumber": acc_a, "filingDate": "2026-09-20", "form": "8-K", "items": "7.01,9.01"},
                   {"accessionNumber": acc_b, "filingDate": "2026-09-22", "form": "8-K", "items": "8.01"},
                   {"accessionNumber": tc.ACC, "filingDate": "2026-09-10", "form": "8-K", "items": "2.02,9.01"}]
        routes[cf.submissions_url(tc.CIK)] = json.dumps(tc.submissions(filings)).encode()
        rows = [(f"Exhibit {i}", f"ex99{i}.htm", base_a + f"ex99{i}.htm", f"EX-99.{i}") for i in range(1, len(update_docs) + 1)]
        routes[cf.filing_index_url(tc.CIK, acc_a)] = tc.index_page(rows).encode()
        for i, body in enumerate(update_docs, 1):
            routes[base_a + f"ex99{i}.htm"] = body
        main_rows = [("8-K", "form8k.htm", base_b + "form8k.htm", "8-K")]
        routes[cf.filing_index_url(tc.CIK, acc_b)] = tc.index_page(main_rows).encode()
        routes[base_b + "form8k.htm"] = update_main or BOARD
        return routes

    def research(self, routes, state=None):
        sec, fake = self.tc.client(routes)
        result = ctx.research({"issuer": {"cik": self.tc.CIK, "ticker": "AAA"}}, sec, state or ctx.load_state(),
                              self.tc.NOW, ctx.settings())
        return result, [u for u in fake.calls if u.endswith(".htm") and not u.endswith("-index.htm")]

    def test_many_irrelevant_update_attachments_do_not_push_the_results_release_out(self):
        result, fetched = self.research(self.routes([BOARD, BOARD, BOARD, BOARD]))
        self.assertIn(self.tc.BASE + "ex991.htm", fetched)  # the results release was downloaded
        self.assertEqual(len(fetched), 4)  # documents_per_company
        self.assertEqual(fetched.index(self.tc.BASE + "ex991.htm"), 2)  # right after the 2 update downloads
        docs = [cf.load_document(d) for d in result["document_ids"]]
        self.assertEqual([d["accession"] for d in docs], [self.tc.ACC])
        self.assertTrue(all(not c["eligible"] for c in result["update_checks"]))

    def test_an_eligible_8k_text_without_exhibit_is_linked_first(self):
        result, _ = self.research(self.routes([BOARD], update_main=CONTRACT_MAIN))
        docs = [cf.load_document(d) for d in result["document_ids"]]
        self.assertEqual([d["document_type"] for d in docs], ["8-K", "EX-99.1"])
        self.assertIn("customer_contract", next(c["reason"] for c in result["update_checks"] if c["eligible"]))

    def test_a_cached_document_is_judged_again_without_rewriting_it(self):
        routes = self.routes([DIVIDEND])
        self.research(routes)  # stores the dividend exhibit
        state = ctx.load_state()
        stored = None
        import gzip
        for path in cf.documents_dir().glob("*.json.gz"):
            record = json.loads(gzip.open(path, "rt", encoding="utf-8").read())
            if record["accession"] == "0000000001-26-000020":
                stored = path
                record["relevance"]["business_update"] = True  # as the O3 word rule would have stored it
                record["relevance"]["update_reason"] = "business_update_terms:increases,expects"
                cf.store_document(record)
        before = stored.read_bytes()
        result, fetched = self.research(routes, state)
        self.assertNotIn("0000000001-26-000020", [cf.load_document(d)["accession"] for d in result["document_ids"]])
        self.assertEqual(stored.read_bytes(), before)  # judged from stored blocks, never rewritten

    def test_stored_pbf_and_aehr_results_documents_stay_results(self):
        for doc_id in ("DOC-9FC60A7023735EC9", "DOC-EA4425A446380C5A"):
            record = None
            path = ROOT / "data" / "processed" / "company_documents" / f"{doc_id}.json.gz"
            import gzip
            record = json.loads(gzip.open(path, "rt", encoding="utf-8").read())
            with self.subTest(doc_id):
                self.assertTrue(record["relevance"]["earnings"])
                self.assertTrue(ctx.own_statements(record, record["issuer"]["name"]))


from test_candidates import NOW, CandidateFixture, row, snapshot  # noqa: E402

SNAPSHOT_10_4 = ROOT / "data" / "processed" / "revision_screen" / "20261004T060125Z_37181539693-1.json.gz"


class FoldedGroupTest(unittest.TestCase):
    """P1-B on the stored 10/4 screen: three states add up, SUN is 'outside', not folded."""

    def test_three_states_add_up(self):
        import gzip
        import screen_revisions as sr
        import candidates as k
        derived = json.loads(gzip.open(SNAPSHOT_10_4, "rt", encoding="utf-8").read())["derived"]
        a, b, folded = sr.rank(derived["rows"], 20, 3)
        cands = [r for r in derived["rows"] if r["candidate"]]
        group = next(g for g in sr.industry_groups(cands, a, b, folded) if g["industry"] == "Oil & Gas Refining & Marketing")
        self.assertEqual((len(group["shown"]), len(group["folded"]), group["outside"]), (3, 5, ["SUN"]))
        self.assertEqual(len(group["shown"]) + len(group["folded"]) + len(group["outside"]), group["count"])
        self.assertEqual(len({r["ticker"] for r in a + b}), 33)
        old = {**group}
        del old["outside"]  # a snapshot written before 'outside' existed
        self.assertEqual(k.group_states(old)["outside"], ["SUN"])


class FoldedCandidateCardTest(CandidateFixture):
    """P1-B: a folded company has a current summary everywhere; other members never change a version."""

    def write(self, snap, name):
        import gzip
        with gzip.open(c.DATA_DIR / "revision_screen" / name, "wt", encoding="utf-8") as h:
            json.dump(snap, h)

    def grouped(self, folded, run_id="2-1", minute="02"):
        rows = [row("AAA", industry="Refining"), row("BBB", by_yield=False, industry="Refining"),
                row("CRDO", by_growth=False)] + [row(t, industry="Refining") for t in folded]
        snap = snapshot(rows=rows, finished=f"2026-09-25T02:{minute}:00+00:00", run_id=run_id)
        snap["derived"]["industry_groups"] = [{"industry": "Refining", "count": 2 + len(folded),
                                               "tickers": ["AAA", "BBB"] + folded, "shown": ["AAA", "BBB"],
                                               "folded": folded, "outside": []}]
        return snap

    def test_first_folded_company_opens_everywhere(self):
        import candidates as k
        self.write(self.grouped(["DDD"]), "20260925T020200Z_2-1.json.gz")
        k.generate(now=NOW, translate_now=False)
        index = k.load_index()
        ddd = index["folded_candidates"][0]
        self.assertEqual((ddd["identity"]["ticker"], ddd["display_rank"], ddd["display_state"]), ("DDD", None, "industry_folded"))
        self.assertNotIn("DDD", [x["identity"]["ticker"] for x in index["candidates"]])  # no card rank, no alert
        reply = k.telegram_candidate(ddd["candidate_id"])[0]
        self.assertIn("업종 묶음에 포함되어 개별 카드는 없습니다", reply)
        self.assertIn("내년 EPS 예상", reply)
        markdown = (c.ROOT / "docs" / "candidates.md").read_text(encoding="utf-8")
        self.assertIn(f"`/candidate {ddd['candidate_id']}`", markdown)
        page = k.render_html(index)
        self.assertIn('"folded": [{"candidate"', page)
        self.assertIn("업종 제한으로 접힌 기업", (ROOT / "templates" / "candidates.html").read_text(encoding="utf-8"))
        line = next(t for kind, t in k.card_lines(index["candidates"][0]) if "같은 업종" in t)
        self.assertIn("업종 제한으로 접힘 1곳(DDD), 일반 순위 밖 0곳", line)

    def test_other_members_do_not_change_this_companys_version(self):
        import candidates as k
        self.write(self.grouped(["DDD"]), "20260925T020200Z_2-1.json.gz")
        k.generate(now=NOW, translate_now=False)
        before = next(x for x in k.load_index()["candidates"] if x["identity"]["ticker"] == "AAA")["candidate_version"]
        self.write(self.grouped(["DDD", "EEE"], run_id="3-1", minute="30"), "20260925T023000Z_3-1.json.gz")
        k.generate(now=NOW, translate_now=False)
        after = next(x for x in k.load_index()["candidates"] if x["identity"]["ticker"] == "AAA")
        self.assertEqual(after["candidate_version"], before)
        self.assertEqual(after["industry_group"]["folded"], ["DDD", "EEE"])  # shown as observation metadata


class FoldedResearchShareTest(unittest.TestCase):
    """P1-B: folded companies keep research and draft turns without starving the cards."""

    @staticmethod
    def target(i, folded):
        return {"candidate_id": f"CAN-{'F' if folded else 'C'}{i:015d}", "first_seen_at": "2026-10-04T00:00:00+00:00",
                "rank": i + (100 if folded else 0), "folded": folded, "eps_key": "x"}

    def test_research_places(self):
        state = {"candidates": {}}
        many = [self.target(i, False) for i in range(12)] + [self.target(i, True) for i in range(5)]
        chosen = ctx.select(many, state, NOW, 10, 2)
        self.assertEqual((sum(not t["folded"] for t in chosen), sum(t["folded"] for t in chosen)), (8, 2))
        few = [self.target(i, False) for i in range(3)] + [self.target(i, True) for i in range(5)]
        chosen = ctx.select(few, state, NOW, 10, 2)
        self.assertEqual((sum(not t["folded"] for t in chosen), sum(t["folded"] for t in chosen)), (3, 5))
        only_cards = [self.target(i, False) for i in range(12)]
        self.assertEqual(len(ctx.select(only_cards, state, NOW, 10, 2)), 10)

    def test_draft_order_keeps_one_model_request_for_folded(self):
        queue = [(f"C{i}", {}) for i in range(8)] + [("F0", {}), ("F1", {})]
        order = [cid for cid, _ in ctx.draft_order(queue, {"F0", "F1"}, 6, 1)]
        self.assertEqual(order[:6], ["C0", "C1", "C2", "C3", "C4", "F0"])
        self.assertEqual(order[6:], ["C5", "C6", "C7", "F1"])
        no_folded = [cid for cid, _ in ctx.draft_order(queue[:8], set(), 6, 1)]
        self.assertEqual(no_folded[:6], ["C0", "C1", "C2", "C3", "C4", "C5"])


class SignalQuarantineTest(unittest.TestCase):
    """P0: SIG-0900 is withheld from every reader; the ledger is unchanged; a broken list stops readers."""

    def test_withheld_everywhere_but_kept_in_the_ledger(self):
        self.assertIn("SIG-0900", {r["signal_id"] for r in c.read_rows("signal_log")})
        self.assertNotIn("SIG-0900", {r["signal_id"] for r in c.read_signals()})
        self.assertNotIn("SIG-0900", {r["signal_id"] for r in c.read_signals(live_only=False)})
        import promote
        self.assertIsNone(promote.find_signal("SIG-0900"))  # /track SIG-0900 finds nothing
        readers = {"candidate_alerts.py", "digest.py", "evaluate.py", "gen_report.py", "notify.py", "promote.py",
                   "telegram_cmd.py"}
        for name in readers:
            text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
            with self.subTest(name):
                self.assertFalse(re.search(r'read_(?:live_)?rows\("signal_log"\)', text))
                self.assertIn("read_signals(", text)

    def test_a_broken_list_raises(self):
        with mock.patch.object(c, "ROOT", ROOT / "does-not-exist"):
            with self.assertRaises(ValueError):
                c.read_signals()


if __name__ == "__main__":
    unittest.main()
