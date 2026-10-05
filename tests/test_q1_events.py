"""Q1: verified new events (update-check-v4) and A/B baselines kept apart (material-update-v2)."""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common as c  # noqa: E402
import candidate_alerts as a  # noqa: E402
import candidate_context  # noqa: E402
import company_filings as cf  # noqa: E402
import material_updates as m  # noqa: E402
from test_p2_material import MaterialFixture  # noqa: E402


def blocks(*paragraphs):
    return cf.normalize_html(("<html><body>" + "".join(f"<p>{p}</p>" for p in paragraphs) + "</body></html>").encode())


DATE = "NEW YORK, October 9, 2026 -- AAA Inc. announced today."


class AlertJudgmentTest(unittest.TestCase):
    def one(self, *paragraphs, prior=None):
        events = cf.business_events(blocks(*paragraphs), "AAA Inc.", prior)
        self.assertEqual(len(events), 1, events)
        return events[0]

    def test_unchanged_first_or_mixed_outlook_is_not_an_alert(self):
        self.assertEqual(self.one(DATE, "AAA reaffirmed its unchanged revenue outlook of $50 million for fiscal 2027.")
                         ["alert_reason"], "guidance_unchanged")
        self.assertEqual(self.one(DATE, "AAA raises fiscal 2027 revenue guidance to $150 million.")["alert_reason"],
                         "guidance_no_prior_value")
        self.assertEqual(self.one(DATE, "AAA updates fiscal 2027 revenue guidance from $130 million - $150 million to "
                                        "$120 million - $160 million.")["alert_reason"], "guidance_mixed_range")

    def test_same_period_outlook_raised_or_lowered_is_an_alert(self):
        up = self.one(DATE, "AAA raises fiscal 2027 revenue guidance to $150 million from $130 million.")
        self.assertEqual((up["alert_eligible"], up["guidance"]["direction"], up["event_date"]), (True, "up", "2026-10-09"))
        down = self.one(DATE, "AAA lowers fiscal 2027 revenue outlook from $1.1 - $1.2 billion to $1.0 - $1.1 billion.")
        self.assertEqual((down["alert_eligible"], down["guidance"]["direction"]), (True, "down"))
        self.assertEqual(down["guidance"]["old"], [1100.0, 1200.0])

    def test_prior_outlook_of_the_same_key_only(self):
        prior = cf.guidance_statements(blocks("AAA expects fiscal 2027 revenue of $130 million."))
        self.assertTrue(self.one(DATE, "AAA raises fiscal 2027 revenue guidance to $150 million.", prior=prior)
                        ["alert_eligible"])
        other_year = cf.guidance_statements(blocks("AAA expects fiscal 2026 revenue of $130 million."))
        self.assertFalse(self.one(DATE, "AAA raises fiscal 2027 revenue guidance to $150 million.", prior=other_year)
                         ["alert_eligible"])
        other_basis = cf.guidance_statements(blocks("AAA expects fiscal 2027 adjusted EBITDA of $30 million."))
        self.assertFalse(self.one(DATE, "AAA raises fiscal 2027 EBITDA guidance to $35 million.", prior=other_basis)
                         ["alert_eligible"])  # GAAP basis differs from the earlier non-GAAP outlook

    def test_dated_old_event_restated_results_and_undated_sentences(self):
        old = self.one(DATE, "On September 1, 2026, the company received a purchase order valued at $50 million.")
        self.assertEqual((old["event_date"], old["date_precision"]), ("2026-09-01", "day"))
        self.assertEqual(self.one(DATE, "Backlog was $80.6 million compared with $15.2 million a year ago.")
                         ["alert_reason"], "restated_result_or_unchanged")
        self.assertEqual(self.one("AAA Inc. results.", "Orders of $35 million were strong.")["alert_reason"],
                         "event_date_unknown")
        self.assertEqual(self.one(DATE, "Orders of $35 million were received during the third quarter.")["alert_reason"],
                         "period_recount")


class MaterialATest(MaterialFixture):
    def run_report(self):
        return self.report()["candidates"][0]

    def test_probe_cases_old_event_and_unchanged_outlook_are_not_sent(self):
        self.boot(eps=1.0)
        self.screen("2026-10-10", eps=1.0)
        self.update_doc("2026-10-01", text="On September 1, 2026, the company received a purchase order valued at $50 million.")
        self.update_doc("2026-10-02", doc_id="DOC-A2",
                        text="The company reaffirmed its unchanged revenue outlook of $50 million for fiscal 2027.")
        self.send_alerts()
        self.assertEqual(self.sent, [])
        notes = " ".join(self.run_report()["a_notes"])
        self.assertIn("기준(2026-09-25) 이전", notes)
        self.assertIn("guidance_unchanged", notes)

    def test_two_documents_of_one_event_and_body_plus_release_are_one_event(self):
        self.boot(eps=1.0)
        self.screen("2026-10-10", eps=1.0)
        raise_text = "AAA raises fiscal 2027 revenue guidance to $150 million from $130 million."
        self.update_doc("2026-10-08", text=raise_text)                    # the release (EX-99.1)
        self.update_doc("2026-10-08", doc_id="DOC-A2", text=raise_text)   # the 8-K body of the same filing
        self.send_alerts()
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(len(self.material_events()[0]["material"]["documents"]), 1)
        self.assertIn("전망 revenue FY2027", self.sent[0])
        self.assertIn("130.00 → 150.00 — 상향", self.sent[0])

    def test_contracts_with_different_named_customers_are_different_events(self):
        self.boot(eps=1.0)
        self.screen("2026-10-10", eps=1.0)
        self.update_doc("2026-10-08", text="AAA received a purchase order of $50 million from Beta Systems.")
        self.update_doc("2026-10-08", doc_id="DOC-A2", text="AAA received a purchase order of $50 million from Gamma Labs.")
        self.send_alerts()
        docs = self.material_events()[0]["material"]["documents"]
        self.assertEqual(sorted(d["counterparty"] for d in docs), ["Beta Systems", "Gamma Labs"])

    def test_same_date_other_amount_without_named_parties_is_held(self):
        self.boot(eps=1.0)
        self.screen("2026-10-10", eps=1.0)
        self.update_doc("2026-10-08", text="AAA received a purchase order of $50 million.")
        self.update_doc("2026-10-08", doc_id="DOC-A2", text="AAA received a purchase order of $55 million.")
        self.send_alerts()
        self.assertEqual(len(self.material_events()[0]["material"]["documents"]), 1)
        self.assertIn("모호", " ".join(self.run_report()["a_notes"]))


class BaselineSplitTest(MaterialFixture):
    def test_a_only_alert_keeps_the_eps_baseline_and_first_day(self):
        self.boot(eps=1.0)
        self.screen("2026-10-10", eps=1.30)
        self.update_doc("2026-10-09")
        self.send_alerts()
        self.assertEqual(self.material_events()[0]["material"]["triggers"], ["A"])
        self.screen("2026-10-11", eps=1.31)
        self.send_alerts()
        diag = self.report()["candidates"][0]
        self.assertEqual((diag["baseline"]["eps_now"], diag["b"]), (1.0, "confirmed"))
        self.assertEqual(diag["pct"], 31.0)
        self.assertEqual(len(self.sent), 1)  # B is confirmed but waits for the 14-day gap

    def test_b_sent_moves_the_baseline_and_a_plus_b_is_one_event(self):
        self.boot(eps=1.0)
        self.screen("2026-10-10", eps=1.3)
        self.send_alerts()
        self.update_doc("2026-10-10")
        self.screen("2026-10-11", eps=1.3)
        self.send_alerts()
        events = self.material_events()
        self.assertEqual((len(events), sorted(events[0]["material"]["triggers"])), (1, ["A", "B"]))
        self.screen("2026-10-30", eps=1.3)
        self.assertEqual(self.report()["candidates"][0]["baseline"]["source"], m.KIND)

    def test_uncertain_locks_without_moving_the_baseline(self):
        self.boot(eps=1.0)
        self.screen("2026-10-10", eps=1.3)
        self.send_alerts()
        self.screen("2026-10-11", eps=1.3)
        self.outcomes = ["uncertain"]
        self.send_alerts()
        self.screen("2026-10-30", eps=1.3)
        self.update_doc("2026-10-29")  # a new A part while the B part is still unconfirmed
        self.send_alerts()
        diag = self.report()["candidates"][0]
        self.assertEqual((diag["decision"], diag["baseline"]["source"]), ("locked_unconfirmed", "bootstrap"))
        self.assertEqual(self.sent, [])
        self.assertEqual(len(self.material_events()), 1)

    def test_failed_event_is_retried_with_its_fixed_payload_when_parts_grow(self):
        self.boot(eps=1.0)
        self.screen("2026-10-10", eps=1.3)
        self.send_alerts()
        self.screen("2026-10-11", eps=1.3)
        self.outcomes = ["failed"]
        self.send_alerts()
        first = self.material_events()[0]
        self.update_doc("2026-10-11")
        self.screen("2026-10-12", eps=1.3)
        self.send_alerts()
        events = self.material_events()
        self.assertEqual(len(events), 1)
        self.assertEqual((events[0]["status"], events[0]["material"]["triggers"]), ("sent", first["material"]["triggers"]))

    def test_v1_ledger_migrates_once_and_keeps_the_pending_first_day(self):
        ledger = self.boot(eps=1.0)
        self.screen("2026-10-10", eps=1.3)
        self.send_alerts()
        stored = self.ledger()
        stored["material"]["version"] = "material-update-v1"
        c.atomic_json(a.ledger_path(), stored)
        pending = stored["material"]["pending"]
        self.screen("2026-10-10", eps=1.3, hour="06")
        self.send_alerts()
        after = self.ledger()["material"]
        self.assertEqual((after["version"], after["previous_version"]), (m.VERSION, "material-update-v1"))
        self.assertEqual(after["pending"], pending)
        backup = c.DATA_DIR / f"candidate_alerts.pre_{m.VERSION}.json"
        self.assertEqual(json.loads(backup.read_text(encoding="utf-8"))["material"]["version"], "material-update-v1")
        del ledger


if __name__ == "__main__":
    unittest.main()
