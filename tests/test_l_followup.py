"""L1-L3 regression tests (docs/l_v7_acceptance_and_v8_spec_2026-10-04.md): what a number is
(level / change / effect), stored v7 drafts re-checked when read, over-refusal fixes and card
selection. Sentences are the production sources of the 9/29-10/4 runs; no network or model."""
import json
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import candidate_context as ctx  # noqa: E402
import candidates as k  # noqa: E402
import common as c  # noqa: E402
from test_candidate_context import claim  # noqa: E402
from test_candidates import NOW, CandidateFixture  # noqa: E402

# CLBK 8-K EX-99.1 (DOC-AC201A9BE0E4E848) p19 and p20, filed 2026-07-30.
CLBK_P19 = ("Net income of $14.5 million was recorded for the quarter ended June 30, 2026, an increase of $2.2 million "
            "compared to net income of $12.3 million for the quarter ended June 30, 2025. The increase in net income was "
            "primarily attributable to a $9.2 million increase in net interest income and a $657,000 increase in "
            "non-interest income, partially offset by a $1.8 million increase in provision for credit losses, $4.5 million "
            "increase in non-interest expense, and a $1.3 million increase in income tax expense.")
CLBK_P19_SENTENCE = CLBK_P19.split(". ", 1)[1]
CLBK_P5 = ("Columbia Financial, Inc. (the “Company”) (NASDAQ: CLBK) reported net income of $14.5 million, or $0.14 "
           "per basic and diluted share, for the quarter ended June 30, 2026, as compared to $12.3 million, or $0.12 per "
           "basic and diluted share, for the quarter ended June 30, 2025.")
CLBK_P20 = ("Net interest income was $62.9 million for the quarter ended June 30, 2026, an increase of $9.2 million, or "
            "17.2%, from $53.7 million for the quarter ended June 30, 2025.")
DAN = ("Dana has revised its full-year financial guidance upward, increasing its sales outlook by approximately "
       "$225 million and its adjusted EBITDA outlook by approximately $25 million.")
PBF = ("Non-cash special items included in the second quarter 2026 results, which increased net income by a net, "
       "after-tax benefit of $159.8 million, or $1.32 per share, primarily consisted of gains on insurance recoveries.")
TXO = ("Net settlements on oil futures and sell basis swap contracts decreased oil revenues by $28.5 million in the "
       "three months ended June 30, 2026 and increased oil revenues by $2.0 million in the three months ended June 30, 2025.")
RPAY = ("During the second and fourth quarter of 2025, Net loss was impacted by a $103.8 million and a $138.9 million "
        "goodwill impairment loss, respectively, primarily related to the Consumer Payments segment.")
SUNC = "Increases full year 2026 Adjusted EBITDA guidance by $400 million to $3.5 billion to $3.7 billion"
AXTI_MARGIN = ("GAAP gross margin was 44.9 percent of revenue for the second quarter of 2026, compared with 29.6 percent "
               "of revenue for the first quarter of 2026 and 8.0 percent for the second quarter of 2025.")


def run(quote, what="claims", block=None, **fields):
    fields.setdefault("note_ko", "원문에 적힌 내용입니다")
    item = claim(quote=quote, block_id="p1", **fields)
    return ctx.validate_draft({what: [item], "link": "unconfirmed"},
                              [{"document_id": "DOC-A", "block_id": "p1", "text": block or quote}], {"ticker": "AAA"})


def reason(result):
    return result["rejected"][0]["reason"] if result["rejected"] else None


class FigureRoleTest(unittest.TestCase):
    """L1 4.1: a change or effect amount is never shown as the metric's value."""

    def test_clbk_increase_is_not_net_interest_income(self):
        bad = run(CLBK_P19_SENTENCE, block=CLBK_P19, metric="net interest income", figures=["$9.2 million"],
                  period="quarter ended June 30, 2026", currency="USD")
        self.assertEqual(reason(bad), "delta_presented_as_level")
        level = run(CLBK_P20, metric="Net interest income", figures=["$62.9 million"],
                    period="quarter ended June 30, 2026", currency="USD")
        self.assertEqual(reason(level), None)
        self.assertIn("$62.9 million —", level["claims"][0]["text_ko"])
        self.assertEqual(level["claims"][0]["figure_roles"], ["level"])
        prior = run(CLBK_P20, metric="Net interest income", figures=["$53.7 million"],
                    period="quarter ended June 30, 2026", currency="USD")
        self.assertEqual(reason(prior), "figure_from_another_period")  # last year's level stays out of this quarter
        mixed = run(CLBK_P20, metric="Net interest income", figures=["$62.9 million", "$9.2 million"],
                    period="quarter ended June 30, 2026", currency="USD")
        self.assertEqual(reason(mixed), "delta_presented_as_level")  # two roles as one value: refused whole

    def test_dan_outlook_increments_stay_refused_with_l2_wording(self):
        for metric, figure in (("sales outlook", "approximately $225 million"),
                               ("adjusted EBITDA outlook", "approximately $25 million")):
            with self.subTest(metric=metric):
                result = run(DAN, kind="guidance", metric=metric, figures=[figure], period="full-year",
                             note_ko="연간 전망을 상향 조정했다", currency="USD")
                self.assertEqual(reason(result), "delta_presented_as_level")

    def test_pbf_effect_and_txo_described_change(self):
        for figures in (["$159.8 million"], ["$1.32 per share"], ["$159.8 million", "$1.32 per share"]):
            with self.subTest(figures=figures):
                result = run(PBF, metric="net income", figures=figures, period="second quarter 2026", currency="USD")
                self.assertEqual(reason(result), "effect_presented_as_level")
        kept = run(TXO, metric="oil revenues", figures=["decreased oil revenues by $28.5 million"],
                   period="three months ended June 30, 2026", currency="USD")
        self.assertEqual(reason(kept), None)
        self.assertIn("decreased oil revenues by $28.5 million(변화량·감소)", kept["claims"][0]["text_ko"])

    def test_effect_amount_is_not_net_loss_but_can_be_the_loss_itself(self):
        swapped = run(RPAY, metric="Net loss", figures=["$103.8 million"], period="second and fourth quarter of 2025",
                      currency="USD")
        self.assertEqual(reason(swapped), "effect_presented_as_level")
        itself = run(RPAY, metric="goodwill impairment loss", figures=["$138.9 million"],
                     period="second and fourth quarter of 2025", currency="USD")
        self.assertNotIn(reason(itself), ("effect_presented_as_level", "delta_presented_as_level"))
        no_metric = run("A one-time tax benefit of $12 million lifted results in 2026.", what="limitations",
                        metric="", figures=["$12 million"], period="2026", currency="USD")
        self.assertIn("$12 million(영향 금액)", no_metric["limitations"][0]["text_ko"])

    def test_targets_from_to_and_reported_by_are_levels(self):
        level_only = run(SUNC, kind="guidance", metric="Adjusted EBITDA guidance",
                         figures=["$3.5 billion to $3.7 billion"], period="full year 2026",
                         gaap="non-GAAP", note_ko="연간 가이던스를 제시했다", currency="USD")
        self.assertEqual(level_only["claims"][0]["figure_roles"], ["level"])  # the range after 'by $400 million to'
        self.assertEqual(reason(run(SUNC, kind="guidance", metric="Adjusted EBITDA guidance",
                                    figures=["$400 million", "$3.5 billion to $3.7 billion"], period="full year 2026",
                                    gaap="non-GAAP", note_ko="연간 가이던스를 제시했다", currency="USD")),
                         "delta_presented_as_level")
        quote = "Revenue increased to $40 million in 2026 from $30 million in 2025, as reported by the company."
        self.assertEqual(run(quote, metric="Revenue", figures=["$40 million"], period="2026",
                             currency="USD")["claims"][0]["figure_roles"], ["level"])
        quote = "Revenue was $40 million in 2026, down $3 million and lower than the $43 million reported in 2025."
        self.assertEqual(reason(run(quote, metric="Revenue", figures=["$3 million"], period="2026", currency="USD")),
                         "delta_presented_as_level")
        loss = "Net loss narrowed to $(5.2) million in 2026."
        self.assertEqual(reason(run(loss, metric="Net loss", figures=["$(5.2) million"], period="2026", currency="USD")),
                         None)

    def test_the_same_amount_twice_in_different_roles_is_ambiguous(self):
        quote = "Revenue was $5 million in 2026, an increase of $5 million from 2025."
        self.assertEqual(reason(run(quote, metric="Revenue", figures=["$5 million"], period="2026", currency="USD")),
                         "figure_role_ambiguous")

    def test_rate_changes_are_labelled_and_rate_levels_are_not(self):
        rose = run("Revenue rose 5% to $40 million in 2026.", metric="revenue", figures=["5%", "$40 million"],
                   period="2026", currency="USD")
        self.assertEqual(rose["claims"][0]["figure_roles"], ["delta", "level"])
        self.assertIn("5%(변화율·증가) / $40 million", rose["claims"][0]["text_ko"])
        bp = run("Net interest margin increased 25 basis points to 2.44% in 2026.", metric="Net interest margin",
                 figures=["2.44%"], period="2026", currency=None)
        self.assertEqual(bp["claims"][0]["figure_roles"], ["level"])
        margin = run(AXTI_MARGIN, metric="GAAP gross margin", figures=["44.9 percent"],
                     period="second quarter of 2026", gaap="GAAP", currency=None)
        self.assertEqual(margin["claims"][0]["figure_roles"], ["level"])
        share = run("Aehr also expects non-GAAP net income to be 18% to 22% of total revenue in fiscal 2027.",
                    kind="guidance", metric="non-GAAP net income", figures=["18% to 22%"], period="fiscal 2027",
                    gaap="non-GAAP", currency=None)
        self.assertEqual(share["claims"][0]["figure_roles"], ["level"])
        decline = run("Data Center revenue growth year-over-year is expected to decline approximately (4.0%).",
                      kind="guidance", metric="Data Center revenue growth year-over-year", figures=["(4.0%)"],
                      period="unknown", currency=None)
        self.assertEqual(decline["claims"][0]["figure_roles"], ["delta"])


AXTI_GAAP_NI = ("GAAP net income, after minority interests, for the second quarter of 2026 was a net income of $11.1 "
                "million, or $0.17 diluted income per share, compared with a net loss of $1.6 million, or $0.03 per share, "
                "for the first quarter of 2026 and a net loss of $7.0 million, or $0.16 per share, for the second quarter "
                "of 2025.")
AXTI_NON_GAAP_NI = ("Non-GAAP net income for the second quarter of 2026 was a net income of $11.9 million, or $0.19 per "
                    "share, compared with a net loss of $0.6 million, or $0.01 per share, for the first quarter of 2026.")
AXTI_NON_GAAP_GM = ("Non-GAAP gross margin, after excluding charges for stock-based compensation, was 45.0 percent of "
                    "revenue for the second quarter of 2026, compared with 29.9 percent of revenue for the first quarter "
                    "of 2026 and 8.2 percent for the second quarter of 2025.")
URGN = ("The Company is increasing its full-year 2026 operating expenses guidance to be in the range of $260 million "
        "to $270 million, including non-cash share-based compensation expense of $20 million to $24 million.")


class OverRefusalTest(unittest.TestCase):
    """L2: narrow fixes for correct sentences refused in the 9/29-10/4 runs, with their negatives."""

    Q2 = dict(period="second quarter of 2026", currency="USD")

    def test_axti_repeated_metric_and_ratio_denominator(self):
        for quote, metric, figure, gaap in ((AXTI_GAAP_NI, "GAAP net income", "$11.1 million", "GAAP"),
                                            (AXTI_NON_GAAP_NI, "Non-GAAP net income", "$11.9 million", "non-GAAP")):
            with self.subTest(metric=metric):
                result = run(quote, metric=metric, figures=[figure], gaap=gaap, **self.Q2)
                self.assertEqual(reason(result), None)
                self.assertEqual(result["claims"][0]["gaap"], gaap)
        margin = run(AXTI_NON_GAAP_GM, metric="Non-GAAP gross margin", figures=["45.0 percent"], gaap="non-GAAP",
                     period="second quarter of 2026", currency=None)
        self.assertEqual(reason(margin), None)
        # The basis, attribution, scope and amount still cannot be swapped.
        self.assertEqual(reason(run(AXTI_GAAP_NI, metric="GAAP net income", figures=["$11.1 million"],
                                    gaap="non-GAAP", **self.Q2)), "gaap_not_as_stated")
        self.assertEqual(reason(run(AXTI_GAAP_NI, metric="GAAP net income", figures=["$1.6 million"], **self.Q2)),
                         "figure_belongs_to_another_metric")  # the prior quarter's net loss
        attributed = ("GAAP net income for the second quarter of 2026 was $12.0 million and net income attributable to "
                      "AXT was a net income of $11.1 million.")
        self.assertEqual(reason(run(attributed, metric="GAAP net income", figures=["$11.1 million"], **self.Q2)),
                         "figure_belongs_to_another_metric")
        adjusted = ("GAAP net income for the second quarter of 2026 was $12.0 million while adjusted results were a "
                    "net income of $11.1 million.")
        self.assertEqual(reason(run(adjusted, metric="GAAP net income", figures=["$11.1 million"], **self.Q2)),
                         "figure_belongs_to_another_metric")
        revenue = ("Revenue for the second quarter of 2026 was $47.6 million and gross margin was 45.0 percent of "
                   "revenue.")
        self.assertEqual(reason(run(revenue, metric="Revenue", figures=["45.0 percent"], period="second quarter of 2026",
                                    currency=None)), "figure_belongs_to_another_metric")  # a margin is not revenue

    def test_out_of_list_drivers_are_dropped_and_kept_beside(self):
        quote = ("Revenue for the second quarter of 2026 was $47.6 million, compared with $26.9 million for the first "
                 "quarter of 2026.")
        result = run(quote, metric="Revenue", figures=["$47.6 million"],
                     drivers=["customer_demand", "volume", "productivity", "volume"], **self.Q2)
        item = result["claims"][0]
        self.assertEqual(item["drivers"], ["volume"])
        self.assertEqual(item["normalized"]["drivers_original"], ["customer_demand", "volume", "productivity", "volume"])
        only_bad = run(quote, metric="Revenue", figures=["$47.6 million"], drivers=["customer_demand"], **self.Q2)
        self.assertEqual(only_bad["claims"][0]["drivers"], ["unknown"])
        self.assertEqual(reason(run(quote, metric="Revenue", figures=["$47.6 million"], direction="sideways",
                                    **self.Q2)), "bad_tag")  # direction is still checked
        self.assertEqual(reason(run(quote, metric="Revenue", figures=["$47.6 million"], drivers="volume", **self.Q2)),
                         "invalid_field_type")

    def test_adjusted_label_only_for_a_non_gaap_metric(self):
        quote = ("For the second quarter of 2026, the Company reported Adjusted EBITDA2 of $286 million, a $191 million "
                 "improvement compared to Adjusted EBITDA2 of $95 million recorded in the first quarter of 2026.")  # CLF
        ok = run(quote, metric="Adjusted EBITDA2", figures=["$286 million"], gaap="Adjusted ", **self.Q2)
        self.assertEqual(reason(ok), None)
        self.assertEqual((ok["claims"][0]["gaap"], ok["claims"][0]["normalized"]["gaap_original"]),
                         ("non-GAAP", "Adjusted "))
        gaap_metric = ("For the second quarter of 2026, the Company reported net income of $134 million and Adjusted "
                       "EBITDA of $286 million.")
        self.assertEqual(reason(run(gaap_metric, metric="net income", figures=["$134 million"], gaap="adjusted",
                                    **self.Q2)), "gaap_not_as_stated")
        self.assertEqual(reason(run(quote, metric="Adjusted EBITDA2", figures=["$286 million"], gaap="adjusted-ish",
                                    **self.Q2)), "gaap_not_as_stated")

    def test_raise_wording_forms_and_dan_still_refused(self):
        kept = run(URGN, kind="guidance", metric="full-year 2026 operating expenses guidance",
                   figures=["$260 million to $270 million"], period="full-year 2026", note_ko="연간 영업비용 가이던스를 상향 조정했다",
                   currency="USD")
        self.assertEqual(reason(kept), None)
        self.assertEqual(kept["claims"][0]["figure_roles"], ["level"])
        dan = run(DAN, kind="guidance", metric="sales outlook", figures=["approximately $225 million"],
                  period="full-year", note_ko="연간 매출 전망을 상향 조정했다", currency="USD")
        self.assertEqual(reason(dan), "delta_presented_as_level")
        both = "The Company is raising revenue guidance in 2026 while lowering its margin outlook."
        self.assertEqual(reason(run(both, kind="guidance", metric="revenue guidance", figures=[], period="2026",
                                    note_ko="매출 가이던스를 상향했다", currency=None)), "raise_not_in_quote")
        execute = "The Company will execute its 2026 revenue guidance."
        self.assertEqual(reason(run(execute, kind="guidance", metric="revenue guidance", figures=[], period="2026",
                                    note_ko="매출 가이던스를 하향했다", currency=None)), "cut_not_in_quote")

    def test_prompt_states_the_gaap_values(self):
        self.assertEqual(ctx.PROMPT_VERSION, "context-ko-v4")
        prompt = ctx.draft_prompt({"ticker": "AAA", "issuer": {"name": "AAA Inc."}, "eps_target_period": "2027-12-31",
                                   "eps": {}}, [], [])
        self.assertIn("adjusted라고 적힌 지표도 출력은 non-GAAP", prompt)


def stored_item(quote, block_id, metric, figures, note, core=True):
    """An item as context-check-v7 accepted and stored it."""
    return {"text_ko": f"{metric}: {' / '.join(figures)} — {note}", "note_ko": note, "kind": "fact", "quote": quote,
            "document_id": "DOC-00000000000000CB", "block_id": block_id, "metric": metric, "figures": figures,
            "period": "quarter ended June 30, 2026", "currency": "USD", "gaap": "unknown", "subject": "issuer",
            "subject_name": None, "core": core, "drivers": ["unknown"], "direction": "positive"}


class StoredDraftViewTest(CandidateFixture):
    """L1 4.2: a stored v7 draft is shown only as v8 accepts it now, without changing the record."""

    CTX_ID = "CTX-00000000000000C7"
    CIK = "0002115119"

    def store(self, parser="context-check-v7", issuer_cik=CIK, with_document=True, period="2027-12-31",
              context_id=CTX_ID):
        import candidate_context
        import company_filings
        if with_document:
            company_filings.store_document({
                "document_id": "DOC-00000000000000CB", "issuer": {"cik": self.CIK}, "title": "Q2 results",
                "url": "https://www.sec.gov/Archives/edgar/data/2115119/x/ex991.htm", "accession": "0002115119-26-000001",
                "form": "8-K", "document_type": "EX-99.1", "filed_at": "2026-07-30", "published_at": None,
                "observed_at": "2026-09-28T05:32:53+00:00", "raw_sha256": "s", "content_type": "html",
                "coverage": "complete", "status": "parsed", "relevance": {"earnings": True},
                "normalization_version": "norm-v1",
                "blocks": [{"id": "p5", "kind": "p", "text": CLBK_P5}, {"id": "p19", "kind": "p", "text": CLBK_P19},
                           {"id": "p20", "kind": "p", "text": CLBK_P20}]})
        record = {"context_id": context_id, "candidate_id": self.aaa["candidate_id"], "ticker": "AAA",
                  "issuer_cik": issuer_cik, "document_ids": ["DOC-00000000000000CB"], "eps_target_period": period,
                  "source_blocks": ["DOC-00000000000000CB#p5", "DOC-00000000000000CB#p19", "DOC-00000000000000CB#p20"],
                  "input_sha": "x" * 64, "model": "gemini-2.5-flash", "prompt_version": "context-ko-v3",
                  "parser_version": parser, "generated_at": "2026-10-01T15:16:23+00:00", "source_coverage": "complete",
                  "claims": [stored_item(CLBK_P5, "p5", "net income", ["$14.5 million"], "순이익이 늘었다"),
                             stored_item(CLBK_P20, "p20", "Net interest income", ["$62.9 million"], "순이자이익이 늘었다"),
                             stored_item(CLBK_P19_SENTENCE, "p19", "net interest income", ["$9.2 million"],
                                         "순이자이익이 늘었다", core=False)],
                  "limitations": [], "next_check": [], "link": "unconfirmed", "link_note": None, "rejected": [],
                  "context_status": "draft_ready"}
        path = candidate_context.history_dir() / f"{context_id}.json"
        c.atomic_json(path, record)
        state = candidate_context.load_state()
        state["candidates"][self.aaa["candidate_id"]] = {
            "status": "success", "context_id": context_id, "document_ids": ["DOC-00000000000000CB"],
            "eps_target_period": "2027-12-31", "issuer": {"cik": self.CIK, "ticker": "CLBK", "name": "Columbia Financial, Inc."}}
        c.atomic_json(candidate_context.state_path(), state)
        return path

    def card(self):
        k.generate(now=NOW, translate_now=False)
        return next(x for x in k.load_index()["candidates"] if x["candidate_id"] == self.aaa["candidate_id"])

    def test_bare_change_disappears_level_stays_record_unchanged(self):
        path = self.store()
        before = path.read_bytes()
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network")):
            card = self.card()
        texts = [x["text_ko"] for x in card["context"]["claims"]]
        self.assertEqual(len(texts), 2)
        self.assertIn("$14.5 million", texts[0])
        self.assertIn("$62.9 million", texts[1])
        self.assertEqual(card["context"]["context_status"], "draft_ready")
        self.assertEqual((card["context"]["source_parser_version"], card["context"]["display_validator_version"],
                          card["context"]["validation_scope"], card["context"]["generated_at"]),
                         ("context-check-v7", ctx.PARSER_VERSION, "accepted_only", "2026-10-01T15:16:23+00:00"))
        reply = k.telegram_card(card)
        self.assertNotIn("$9.2 million", reply)
        self.assertIn("현재 검증기(context-check-v8)로 다시 확인", reply)
        self.assertEqual(path.read_bytes(), before)
        observations = sorted(p.name for p in k.observations_dir().glob("OB-*.json"))
        again = self.card()  # reading the same inputs again adds nothing
        self.assertEqual(again["candidate_version"], card["candidate_version"])
        self.assertEqual(sorted(p.name for p in k.observations_dir().glob("OB-*.json")), observations)
        self.assertEqual([x["text_ko"] for x in k.context_inputs()[0][self.aaa["candidate_id"]]["claims"]], texts)

    def test_missing_document_or_other_issuer_blocks_the_draft(self):
        for kwargs in ({"with_document": False}, {"issuer_cik": "0000000009"}):
            with self.subTest(**kwargs):
                import company_filings
                for p in company_filings.documents_dir().glob("*.json.gz"):
                    p.unlink()
                self.store(**kwargs)
                card = self.card()
                self.assertIsNone(card["context"])
                self.assertIn("재검증 불가", k.telegram_card(card))
                self.assertNotIn("$62.9 million", k.telegram_card(card))

    def test_other_fiscal_year_and_unsupported_versions_are_not_attached(self):
        self.store(period="2026-12-31")
        self.assertIsNone(self.card()["context"])
        self.store(parser="context-check-v4")
        self.assertIsNone(self.card()["context"])

    def test_quarantine_comes_before_revalidation(self):
        self.store()
        k.quarantine_path().write_text(json.dumps({"schema_version": 1, "contexts": {self.CTX_ID: {
            "candidate_id": self.aaa["candidate_id"], "reason": "delta_reported_as_level", "source_ref": "x#p19",
            "decided_at": "2026-10-04T07:44:07+00:00", "decided_by": "test", "note": "test"}}}), encoding="utf-8")
        card = self.card()
        self.assertIsNone(card["context"])
        self.assertEqual(card["context_hold"]["context_id"], self.CTX_ID)

    def test_import_uses_the_same_view(self):
        self.store()
        self.card()
        k.import_context(self.aaa["candidate_id"])
        entry = c.read_json(k.evidence_path(), {})[self.aaa["candidate_id"]]
        texts = [s["text"] for s in entry["explanations"]["earnings_path"]]
        self.assertEqual(len(texts), 2)
        self.assertFalse(any("$9.2 million" in t for t in texts))
        self.assertNotIn("approval", entry)


if __name__ == "__main__":
    unittest.main()
