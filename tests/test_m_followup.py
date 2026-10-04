"""M1-M4 regression tests (docs/m_l_acceptance_and_followup_2026-10-04.md): number-role edges and the
PBF effect warning, verification on every display path, comparable periods and disclaimers, and the
independence/integrity of the offline evaluation. Production sources; no network or model."""
import copy
import gzip
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import candidate_context as ctx  # noqa: E402
import candidates as k  # noqa: E402
import common as c  # noqa: E402
from test_l_followup import CLBK_P19_SENTENCE, DAN, PBF, RPAY, StoredDraftViewTest, reason, run  # noqa: E402

L4 = ROOT / "data" / "eval" / "l4_2026-10-04"


def stored_audit(ticker, day):
    with gzip.open(L4 / "audits.json.gz", "rt", encoding="utf-8") as handle:
        records = json.load(handle)
    rows = json.loads((L4 / "manifest.json").read_text(encoding="utf-8"))
    return next(r for r, m in zip(records, rows) if m["ticker"] == ticker and m["kst_day"] == day)


class EffectAndRateBoundaryTest(unittest.TestCase):
    """M1-1: an effect stays an effect unless the amount measures the metric itself; an amount and a
    rate in one figure are refused; units and directions come only from the number's own grammar."""

    def test_codex_probes(self):
        effect = "A one-time tax benefit of $12 million increased net income in 2026."
        self.assertEqual(reason(run(effect, metric="net income", figures=["$12 million"], period="2026")),
                         "effect_presented_as_level")
        self.assertIsNone(reason(run(effect, metric="tax benefit", figures=["$12 million"], period="2026")))
        level = "A tax benefit of $12 million increased net income to $50 million in 2026."
        self.assertIsNone(reason(run(level, metric="net income", figures=["$50 million"], period="2026")))
        mixed = "Net interest income was $62.9 million in 2026, an increase of $9.2 million, or 17.2%."
        self.assertEqual(reason(run(mixed, metric="net interest income", figures=["$9.2 million, or 17.2%"],
                                    period="2026")), "figure_mixes_amount_and_rate")

    def test_effect_target_and_subject_cannot_swap(self):
        quote = "Net loss was impacted by a $138.9 million goodwill impairment loss in 2025."
        self.assertEqual(reason(run(quote, metric="Net loss", figures=["$138.9 million"], period="2025")),
                         "effect_presented_as_level")
        own = run(quote, metric="goodwill impairment loss", figures=["$138.9 million"], period="2025")
        self.assertIsNone(reason(own))
        self.assertEqual(own["claims"][0]["figure_roles"], ["level"])
        verb_between = "A $12 million gain lifted net income in 2026."
        self.assertEqual(reason(run(verb_between, metric="net income", figures=["$12 million"], period="2026")),
                         "effect_presented_as_level")
        self.assertIsNone(reason(run(verb_between, metric="gain", figures=["$12 million"], period="2026")))
        self.assertEqual(reason(run("A one-time charge of $12 million reduced net income in 2026.",
                                    metric="net income", figures=["$12 million"], period="2026")),
                         "effect_presented_as_level")

    def test_a_change_of_the_effect_itself_is_not_its_level(self):
        quote = "The tax benefit increased by $12 million in 2026."
        self.assertEqual(reason(run(quote, metric="tax benefit", figures=["$12 million"], period="2026")),
                         "delta_presented_as_level")

    def test_pure_rates_keep_their_unit_and_direction(self):
        rng = run("Aehr expects non-GAAP net income to be 18% to 22% of total revenue in fiscal 2027.",
                  kind="guidance", metric="non-GAAP net income", figures=["18% to 22%"], period="fiscal 2027",
                  gaap="non-GAAP", currency=None)
        self.assertEqual(rng["claims"][0]["figure_roles"], ["level"])
        bp = run("Net interest margin increased 25 basis points in 2026.", metric="Net interest margin",
                 figures=["25 basis points"], period="2026", currency=None)
        self.assertIn("25 basis points(변화폭·증가)", bp["claims"][0]["text_ko"])
        pp = run("Gross margin declined 1.5 percentage points in 2026.", metric="Gross margin",
                 figures=["1.5 percentage points"], period="2026", currency=None)
        self.assertIn("1.5 percentage points(변화폭·감소)", pp["claims"][0]["text_ko"])
        pct = run("Revenue grew 23% year-over-year to $183.3 million in 2026.", metric="Revenue",
                  figures=["23%"], period="2026", currency=None)
        self.assertIn("23%(변화율·증가)", pct["claims"][0]["text_ko"])
        plain = run("Revenue changed 4% in 2026 compared with 2025.", metric="Revenue", figures=["4%"],
                    period="2026", currency=None)
        self.assertNotIn("증가", plain["claims"][0]["text_ko"] if plain["claims"] else "")  # no direction invented

    def test_a_real_level_in_the_same_sentence_stays(self):
        quote = ("Net interest income was $62.9 million for the quarter ended June 30, 2026, an increase of "
                 "$9.2 million, or 17.2%, from $53.7 million for the quarter ended June 30, 2025.")
        ok = run(quote, metric="Net interest income", figures=["$62.9 million"],
                 period="quarter ended June 30, 2026")
        self.assertEqual(ok["claims"][0]["figure_roles"], ["level"])


class EffectLimitationTest(unittest.TestCase):
    """M1-2: the PBF special-items warning comes back as an effect on net income, never as its value."""

    def test_stored_pbf_limitation_is_restored_as_an_effect(self):
        record = stored_audit("PBF", "2026-09-29")
        result = ctx.validate_draft(copy.deepcopy(record["answer"]), record["blocks"], record["issuer"])
        item = next(x for x in result["limitations"] if "$159.8 million" in x["figures"])
        self.assertEqual(item["text_ko"].split(" — ")[0],
                         "순이익에 미친 영향(net income) · second quarter 2026: $159.8 million(세후 순증가 효과) / "
                         "$1.32 per share(주당 증가 효과)")
        self.assertEqual(item["figure_roles"], ["effect_on_metric", "effect_on_metric"])
        self.assertEqual(item["figure_readings"][0]["direction"], "up")
        self.assertFalse(any("$159.8 million" in x["figures"] for x in result["claims"]))

    def test_the_same_effect_as_a_claim_stays_refused(self):
        self.assertEqual(reason(run(PBF, metric="net income", figures=["$159.8 million"], period="second quarter 2026")),
                         "effect_presented_as_level")

    def test_moving_a_change_or_wrong_scope_to_limitations_does_not_help(self):
        for quote, metric, figures, period in (
                (DAN, "sales outlook", ["approximately $225 million"], "full-year"),
                (CLBK_P19_SENTENCE, "net interest income", ["$9.2 million"], "quarter ended June 30, 2026")):
            with self.subTest(metric=metric):
                self.assertEqual(reason(run(quote, what="limitations", metric=metric, figures=figures, period=period)),
                                 "delta_presented_as_level")
        rpay = run(RPAY, what="limitations", metric="Net loss", figures=["$103.8 million", "$138.9 million"],
                   period="second and fourth quarter of 2025")
        self.assertEqual(rpay["limitations"], [])  # the Consumer Payments segment, not the company's net loss
        self.assertNotEqual(reason(rpay), None)

    def test_a_per_share_figure_must_be_the_same_effect(self):
        quote = ("Special items increased net income by a net, after-tax benefit of $159.8 million in the second "
                 "quarter of 2026, and diluted earnings were $7.54 per share.")
        result = run(quote, what="limitations", metric="net income", figures=["$159.8 million", "$7.54 per share"],
                     period="second quarter of 2026")
        self.assertEqual(result["limitations"], [])


class DisplayPathTest(StoredDraftViewTest):
    """M2: a card read back from an index or an observation is checked as a new card would be."""

    test_bare_change_disappears_level_stays_record_unchanged = None  # inherited tests run in test_l_followup
    test_missing_document_or_other_issuer_blocks_the_draft = None
    test_other_fiscal_year_and_unsupported_versions_are_not_attached = None
    test_quarantine_comes_before_revalidation = None
    test_import_uses_the_same_view = None

    def old_program_output(self):
        """The card as an older program stored it: the v7 draft's own claims, unchecked."""
        import candidate_context
        self.store()
        card = self.card()
        raw = c.read_json(candidate_context.history_dir() / f"{self.CTX_ID}.json", {})
        old = {**card["context"], "claims": raw["claims"], "limitations": raw["limitations"]}
        for key in ("source_parser_version", "display_validator_version", "validation_scope"):
            old.pop(key, None)
        index = k.load_index()
        for cand in index["candidates"]:
            if cand["candidate_id"] == self.aaa["candidate_id"]:
                cand["context"] = old
        c.atomic_json(k.index_path(), index)
        version_path = k.history_dir() / f"{card['candidate_version']}.json"
        version = c.read_json(version_path, {})
        version["context"] = old
        c.atomic_json(version_path, version)
        self.assertIn("$9.2 million", json.dumps(k.load_index(), ensure_ascii=False))
        return card

    def hashes(self):
        import hashlib
        import candidate_context
        files = sorted(candidate_context.history_dir().glob("CTX-*.json")) + sorted(k.history_dir().glob("CV-*.json")) \
            + sorted(k.observations_dir().glob("OB-*.json")) + [k.index_path()]
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}

    def assert_checked(self, text):
        # The level's quote may mention the increase; no card line may show it as a value.
        self.assertNotIn(": $9.2 million —", text)
        self.assertIn("$62.9 million —", text)

    def test_index_outputs_are_checked_without_regenerating(self):
        self.old_program_output()
        before = self.hashes()
        self.assert_checked(k.telegram_candidate(self.aaa["candidate_id"])[0])
        self.assert_checked(k.render_markdown(k.load_index()))
        page = k.render_html(k.load_index())
        self.assertNotIn("net interest income: $9.2 million", page)  # lines and the embedded candidate JSON
        self.assertIn("Net interest income · quarter ended June 30, 2026: $62.9 million", page)
        self.assertEqual(self.hashes(), before)  # reading changes nothing stored

    def test_past_observation_and_departed_candidate_are_checked(self):
        card = self.old_program_output()
        version, obs = k.load_observation(card["observation_id"])
        self.assertIn("$9.2 million", json.dumps(version, ensure_ascii=False))  # stored as it was
        self.assert_checked(k.telegram_card(k.assemble(version, obs, [])))
        index = k.load_index()
        index["candidates"] = [x for x in index["candidates"] if x["candidate_id"] != self.aaa["candidate_id"]]
        # The fixture renders twice at one fixed clock; name the observation that carried the draft.
        index["known"][self.aaa["candidate_id"]]["latest_observation"] = card["observation_id"]
        c.atomic_json(k.index_path(), index)
        found, state = k.find(self.aaa["candidate_id"])
        self.assertEqual(state, "not_current")
        self.assert_checked(k.telegram_card(found))

    def test_a_newer_render_of_the_same_snapshot_is_the_latest_observation(self):
        older = {"observed_at": "2026-10-04T06:15:47+00:00", "observation_id": "OB-FFFFFFFFFFFFFFFF",
                 "generator_version": "cards-v4"}
        newer = {**older, "observation_id": "OB-0000000000000000", "generator_version": "cards-v5"}
        tenth = {**older, "observation_id": "OB-0000000000000001", "generator_version": "cards-v10"}
        self.assertEqual(sorted([newer, tenth, older], key=k.observation_order), [older, newer, tenth])
        first = {**newer, "observation_id": "OB-FFFFFFFFFFFFFFFE", "rendered_at": "2026-10-04T06:16:19+00:00"}
        again = {**newer, "observation_id": "OB-0000000000000002", "rendered_at": "2026-10-04T07:52:08+00:00"}
        self.assertEqual(sorted([again, first], key=k.observation_order), [first, again])

    def test_missing_document_or_other_issuer_hides_the_draft_on_read(self):
        import company_filings
        self.old_program_output()
        for p in company_filings.documents_dir().glob("*.json.gz"):
            p.unlink()
        reply = k.telegram_candidate(self.aaa["candidate_id"])[0]
        self.assertNotIn("$62.9 million", reply)
        self.assertNotIn("$9.2 million", reply)
        self.assertIn("재검증 불가", reply)

    def test_other_issuer_on_read(self):
        import candidate_context
        self.old_program_output()
        record = c.read_json(candidate_context.history_dir() / f"{self.CTX_ID}.json", {})
        other = {**record, "context_id": "CTX-00000000000000C8", "issuer_cik": "0000000009"}
        c.atomic_json(candidate_context.history_dir() / "CTX-00000000000000C8.json", other)
        index = k.load_index()
        for cand in index["candidates"]:
            if cand["candidate_id"] == self.aaa["candidate_id"]:
                cand["context"]["context_id"] = "CTX-00000000000000C8"
        c.atomic_json(k.index_path(), index)
        reply = k.telegram_candidate(self.aaa["candidate_id"])[0]
        self.assertNotIn("$62.9 million", reply)
        self.assertIn("재검증 불가", reply)

    def test_imported_evidence_from_a_withheld_draft_is_held_on_read(self):
        self.store()
        self.card()
        k.import_context(self.aaa["candidate_id"])
        card = self.card()
        self.assertIn("$62.9 million", json.dumps(card["explanations"], ensure_ascii=False))
        k.quarantine_path().write_text(json.dumps({"schema_version": 1, "contexts": {self.CTX_ID: {
            "candidate_id": self.aaa["candidate_id"], "reason": "delta_reported_as_level", "source_ref": "x#p19",
            "decided_at": "2026-10-04T07:44:07+00:00", "decided_by": "test", "note": "test"}}}), encoding="utf-8")
        reply = k.telegram_candidate(self.aaa["candidate_id"])[0]  # the index still holds the copied text
        self.assertNotIn("$62.9 million", reply)
        self.assertIn("격리되어 사용 중지", reply)


def fact(metric, period, kind="fact", subject="issuer", subject_name=None, doc="DOC-A", core=False):
    return {"kind": kind, "metric": metric, "period": period, "document_id": doc, "subject": subject,
            "subject_name": subject_name, "core": core, "figures": ["$1 million"], "text_ko": f"{metric} {period}"}


class ComparablePeriodTest(unittest.TestCase):
    """M3-1: 'past' only within the same document, subject, calendar, period length and form."""

    def order(self, claims):
        return [x["text_ko"] for x in k.stated_order(claims)]

    def test_an_annual_or_fiscal_fact_does_not_push_the_current_quarter_down(self):
        claims = [fact("revenue", "fiscal year 2026"), fact("net income", "quarter ended June 30, 2026"),
                  fact("net income", "six months ended June 30, 2026"), fact("net income", "quarter ended June 30, 2025")]
        self.assertEqual(self.order(claims)[-1], "net income quarter ended June 30, 2025")
        self.assertEqual(self.order(claims)[0], "net income quarter ended June 30, 2026")
        # v8 compared everything in a document: 'fiscal 2026' made the second quarter of 2026 'past'.
        mixed = [fact("revenue", "fiscal 2026"), fact("net income", "second quarter 2026")]
        self.assertEqual(self.order(mixed)[0], "net income second quarter 2026")

    def test_same_quarter_of_two_years_is_compared(self):
        claims = [fact("net loss", "second quarter 2025", core=True), fact("net income", "second quarter 2026")]
        self.assertEqual(self.order(claims), ["net income second quarter 2026", "net loss second quarter 2025"])

    def test_non_december_fiscal_years_and_other_forms_are_not_compared(self):
        claims = [fact("net income", "quarter ended May 29, 2026"), fact("revenue", "fourth quarter of fiscal 2026"),
                  fact("revenue", "fourth quarter of fiscal 2025"), fact("revenue", "first quarter 2027")]
        ordered = self.order(claims)
        self.assertEqual(ordered[-1], "revenue fourth quarter of fiscal 2025")  # only within the fiscal ordinal group
        self.assertIn("net income quarter ended May 29, 2026", ordered[:2])

    def test_other_subjects_and_unclear_periods_are_never_made_past(self):
        claims = [fact("net income", "second quarter 2026"),
                  fact("revenue", "second quarter 2025", subject="segment", subject_name="Retail"),
                  fact("revenue", "second quarter"), fact("revenue", "2026 and 2027"), fact("revenue", "2025")]
        ordered = self.order(claims)
        self.assertEqual(ordered[:2], ["net income second quarter 2026", "revenue second quarter 2025"])
        self.assertEqual(ordered[2:], ["revenue second quarter", "revenue 2026 and 2027", "revenue 2025"])  # stable

    def test_guidance_does_not_set_the_latest_point(self):
        claims = [fact("revenue", "fiscal year 2027", kind="guidance"), fact("revenue", "fiscal year 2026")]
        self.assertEqual(self.order(claims), ["revenue fiscal year 2027", "revenue fiscal year 2026"])


PUBM_P68 = ("Adjusted EBITDA does not reflect: (a) changes in, or cash requirements for, our working capital needs; "
            "(b) the potentially dilutive impact of stock-based compensation; or (c) tax payments that may represent "
            "a reduction in cash available to us;")
PUBM_P70 = ("Non-GAAP net income does not include: (a) the potentially dilutive impact of stock-based compensation; "
            "(b) non-ordinary course litigation related expenses; or (c) income tax effects for stock-based compensation")


class DisclaimerRankTest(unittest.TestCase):
    """M3-2: a measure's definition is supporting text; a real one-off with an amount or a period stays first."""

    def rank(self, quote):
        return k.limitation_rank({"quote": quote})

    def test_pubm_definitions_are_supporting_text(self):
        self.assertEqual((self.rank(PUBM_P68), self.rank(PUBM_P70)), (2, 2))
        self.assertEqual(self.rank("We believe non-GAAP net income per share provides consistency, as it eliminates "
                                   "the effect of restructuring and related charges."), 2)

    def test_real_one_offs_stay_first_and_bare_words_do_not(self):
        self.assertEqual(self.rank(PBF), 0)
        self.assertEqual(self.rank("Adjusted net income excludes a $40 million impairment charge in the second quarter "
                                   "of 2026; non-GAAP measures should not be considered a substitute for GAAP."), 0)
        self.assertEqual(self.rank("Adjusted EBITDA excludes impairment charges."), 2)
        self.assertEqual(self.rank("Results included restructuring charges at the Retail segment."), 1)
        self.assertEqual(self.rank("Revenue was partially offset by lower year-over-year membership."), 1)

    def test_only_definitions_say_no_specific_warning_was_found(self):
        ordered = k.limitation_order([{"quote": PUBM_P68}, {"quote": PUBM_P70}])
        self.assertTrue(all(rank == 2 for rank, _ in ordered))


if __name__ == "__main__":
    unittest.main()
