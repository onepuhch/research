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
from test_l_followup import CLBK_P19_SENTENCE, DAN, PBF, RPAY, reason, run  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
