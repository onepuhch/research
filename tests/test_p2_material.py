"""P2: re-review changes (material_update) of candidates already announced or in the bootstrap set."""
import gzip
import hashlib
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common as c  # noqa: E402
import candidates as k  # noqa: E402
import candidate_alerts as a  # noqa: E402
import candidate_context  # noqa: E402
import company_filings as cf  # noqa: E402
import material_updates as m  # noqa: E402
import screen_revisions  # noqa: E402
from test_candidate_alerts import AlertTest  # noqa: E402
from test_candidates import build, row, snapshot  # noqa: E402

THESIS = k.THESIS_KEY
BOOT_DAY = "2026-09-25"


def dateline(day):
    """A release dateline as press releases print it: 'NEW YORK, October 9, 2026'."""
    from datetime import date as _date
    d = _date.fromisoformat(day)
    return f"NEW YORK, {d.strftime('%B')} {d.day}, {d.year}"


class MaterialFixture(AlertTest):
    def setUp(self):
        super().setUp()
        c.atomic_json(c.DATA_DIR / "notify_state.json", {"pushed": [], "sent": {}})
        self.runs = 0

    def write_snapshot(self, day, rows, hour="01", top=None):
        self.runs += 1
        finished = f"{day}T{hour}:23:02+00:00"
        snap = {**snapshot(rows=rows, top_yield=top or [r["ticker"] for r in rows], top_growth=[],
                           finished=finished, run_id=f"{self.runs}-1"), "schema_version": screen_revisions.SCHEMA_VERSION}
        name = f"{day.replace('-', '')}T{hour}2302Z_{self.runs}-1.json.gz"
        path = screen_revisions.SCREEN_DIR / name
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(snap, handle)
        ref = {"path": f"data/processed/revision_screen/{name}", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
               "run_id": f"{self.runs}-1", "finished_at": finished}
        return snap, ref

    def boot(self, tickers=("AAA",), eps=1.0, events=None):
        _, ref = self.write_snapshot(BOOT_DAY, [row(t, eps_now=eps) for t in tickers])
        ledger = {"events": events or {}, "bootstrap": {
            "date": BOOT_DAY, "source_snapshot": ref,
            "keys": [a.logical_key(f"NASDAQ:{t}", THESIS, a.NEW) for t in tickers]}}
        c.atomic_json(a.ledger_path(), ledger)
        return ledger

    def screen(self, day, eps=1.0, hour="01", folded=False, **fields):
        """One normal daily screen and its cards on 'day' (the alert run happens the same day)."""
        self.day = day
        rows = [row("AAA", eps_now=eps, **fields)]
        snap, ref = self.write_snapshot(day, rows, hour)
        if folded:
            snap["derived"]["top_yield"] = []
            snap["derived"]["industry_groups"] = [{"industry": "Semiconductors", "count": 4, "tickers": ["AAA"],
                                                   "shown": [], "folded": ["AAA"], "outside": []}]
        cands = k.build(snap, ref, {}, {}, {}, [], "pol")
        k.store_observations(cands)
        index = {"observed_at": ref["finished_at"], "run_status": "success", "stale": [], "source_snapshot": ref,
                 "candidates": [x for x in cands if x.get("display_state") == "card"],
                 "folded_candidates": [x for x in cands if x.get("display_state") == "industry_folded"]}
        c.atomic_json(k.index_path(), index)
        return index

    def material_events(self):
        return [e for e in self.ledger()["events"].values() if e["event"] == m.KIND]

    def update_doc(self, filed, report=None, text=None, doc_id="DOC-A1", cid=None):
        record = {"document_id": doc_id, "issuer": {"cik": "0000000001", "name": "AAA Inc."}, "issuer_name": "AAA Inc.",
                  "url": f"https://www.sec.gov/Archives/edgar/data/1/{doc_id}.htm", "final_url": None,
                  "accession": f"0000000001-26-{doc_id[-4:]}", "form": "8-K", "document_type": "EX-99.1",
                  "title": "EX-99.1", "published_at": None, "filed_at": filed, "report_date": report or filed,
                  "observed_at": f"{filed}T20:00:00+00:00", "raw_sha256": "0" * 64, "raw_bytes": 10,
                  "content_type": "html", "coverage": "complete", "status": "parsed", "relevance": {},
                  "normalization_version": cf.NORMALIZATION_VERSION,
                  "blocks": [{"id": "p0", "kind": "p", "text": dateline(filed) + " -- AAA Inc. announced today."},
                             {"id": "p1", "kind": "p", "text": text or
                              "AAA Inc. received a purchase order valued at $50 million from a data center customer."}]}
        missing = [f for f in c.SCHEMA["json_records"]["company_document"] if f not in record]
        record.update({f: None for f in missing})
        cf.store_document(record)
        state = candidate_context.load_state()
        entry = state["candidates"].setdefault(cid or self.cid(), {"issuer": {"cik": "0000000001"}, "update_checks": []})
        entry["update_checks"].append({"document_id": doc_id, "eligible": True, "reason": "update-check-v4:x:p1"})
        c.atomic_json(candidate_context.state_path(), state)

    def cid(self):
        return k.load_index()["candidates"][0]["candidate_id"] if k.load_index().get("candidates") else \
            k.load_index()["folded_candidates"][0]["candidate_id"]

    def report(self):
        path = self.data / "material_report.json"
        a.main(["--dry-run", "--material-report", str(path)])
        return json.loads(path.read_text(encoding="utf-8"))


class TriggerBTest(MaterialFixture):
    def test_aehr_zero_change_since_bootstrap_is_not_a_change(self):
        self.boot(eps=1.38333)
        for day in ("2026-10-10", "2026-10-11"):
            self.screen(day, eps=1.38333)
            self.send_alerts()
        self.assertEqual(self.material_events(), [])
        self.assertEqual(self.sent, [])
        self.assertEqual(self.report()["candidates"][0]["b"], "below_threshold")

    def test_rise_held_on_two_daily_screens_is_sent_once(self):
        self.boot(eps=1.0)
        self.screen("2026-10-10", eps=1.3)
        self.send_alerts()
        self.assertEqual(self.sent, [])  # first day only
        self.screen("2026-10-11", eps=1.31)
        self.send_alerts()
        self.assertEqual(len(self.sent), 1)
        self.assertIn("기존 후보의 재검토 변화", self.sent[0])
        self.assertIn("두 정상 일간", self.sent[0])
        self.assertIn("사업 원인: 원문 미확인", self.sent[0])
        event = self.material_events()[0]
        self.assertEqual(event["material"]["baseline"]["source"], "bootstrap")
        self.assertEqual(event["material"]["first"]["day"], "2026-10-10")
        self.screen("2026-10-12", eps=1.32)  # the new baseline is the alerted observation
        self.send_alerts()
        self.assertEqual(len(self.sent), 1)

    def test_same_day_rerun_is_not_a_second_day(self):
        self.boot(eps=1.0)
        self.screen("2026-10-10", eps=1.3, hour="01")
        self.send_alerts()
        self.screen("2026-10-10", eps=1.3, hour="06")
        self.send_alerts()
        self.assertEqual(self.sent, [])
        self.assertEqual(self.report()["candidates"][0]["b"], "same_day_waiting")

    def test_fiscal_year_or_currency_change_rebases_without_an_event(self):
        self.boot(eps=1.0)
        for day, change in (("2026-10-10", {"eps_target_period": "2028-12-31"}),
                            ("2026-10-11", {"eps_target_period": "2028-12-31"})):
            self.screen(day, eps=2.0, **change)
            self.send_alerts()
        self.assertEqual(self.sent, [])
        rebase = self.ledger()["material"]["rebases"]["NASDAQ:AAA|" + THESIS]
        self.assertEqual((rebase["reason"], rebase["day"]), ("comparison_key_changed", "2026-10-10"))
        self.screen("2026-10-12", eps=2.0, eps_currency="EUR", eps_target_period="2028-12-31")
        self.send_alerts()
        self.assertEqual(self.sent, [])

    def test_a_rise_that_falls_back_after_the_first_day_is_cancelled(self):
        self.boot(eps=1.0)
        self.screen("2026-10-10", eps=1.3)
        self.send_alerts()
        self.screen("2026-10-11", eps=1.1)
        self.send_alerts()
        cancelled = self.ledger()["material"]["cancelled"]
        self.assertEqual(cancelled[-1]["reason"], "condition_lapsed")
        self.screen("2026-10-12", eps=1.3)  # counts from the start again
        self.send_alerts()
        self.assertEqual(self.sent, [])

    def test_small_or_negative_base_is_left_to_business_evidence(self):
        self.boot(eps=0.2)
        for day in ("2026-10-10", "2026-10-11"):
            self.screen(day, eps=0.9)
            self.send_alerts()
        self.assertEqual(self.sent, [])

    def test_waiting_for_the_gap_then_lapsing_records_the_cancellation(self):
        self.boot(eps=1.0)  # bootstrap 9/25: the 14-day gap runs to 10/9
        self.screen("2026-10-05", eps=1.3)
        self.send_alerts()
        self.screen("2026-10-06", eps=1.3)
        self.send_alerts()
        self.assertEqual(self.sent, [])
        self.assertEqual(self.report()["eligible"] != [], True)
        self.screen("2026-10-07", eps=1.0)
        self.send_alerts()
        self.assertEqual(self.ledger()["material"]["cancelled"][-1]["reason"], "condition_lapsed")
        self.screen("2026-10-10", eps=1.0)
        self.send_alerts()
        self.assertEqual(self.sent, [])

    def test_a_never_announced_candidate_gets_no_re_review(self):
        c.atomic_json(a.ledger_path(), {"events": {}, "bootstrap": {"date": BOOT_DAY, "keys": []}})
        self.screen("2026-10-10", eps=1.3)
        diag = self.report()["candidates"][0]
        self.assertEqual(diag["decision"], "not_known")

    def test_alerted_new_discovery_observation_is_the_baseline(self):
        c.atomic_json(a.ledger_path(), {"events": {}, "bootstrap": {"date": BOOT_DAY, "keys": []}})
        self.screen("2026-10-10", eps=1.0)
        self.send_alerts()  # new discovery
        self.assertEqual(len(self.sent), 1)
        for day in ("2026-10-25", "2026-10-26"):
            self.screen(day, eps=1.3)
            self.send_alerts()
        self.assertEqual(len(self.sent), 2)
        self.assertEqual(self.material_events()[0]["material"]["baseline"]["source"], "new_discovery")


class TriggerATest(MaterialFixture):
    def test_new_contract_after_the_baseline_is_sent_once(self):
        self.boot(eps=1.0)
        self.screen("2026-10-10", eps=1.0)
        self.update_doc("2026-10-08")
        self.send_alerts()
        self.assertEqual(len(self.sent), 1)
        self.assertIn("고객 계약·수주", self.sent[0])
        self.assertNotIn("원문 미확인", self.sent[0])
        # the same event in another document (another URL) is not sent again
        self.update_doc("2026-10-08", doc_id="DOC-A2")
        self.screen("2026-10-30", eps=1.0)
        self.send_alerts()
        self.assertEqual(len(self.sent), 1)

    def test_old_filing_collected_late_and_same_day_filing_are_not_new(self):
        self.boot(eps=1.0)
        self.screen("2026-10-10", eps=1.0)
        self.update_doc("2026-09-20", doc_id="DOC-OLD1")
        self.update_doc("2026-09-24", doc_id="DOC-SAME")  # bootstrap 01:23Z = 9/24 evening in New York
        self.send_alerts()
        self.assertEqual(self.sent, [])
        notes = self.report()["candidates"][0]["a_notes"]
        # the 9/20 filing is before the baseline and gives no note; the 9/24 one cannot be ordered
        self.assertEqual([n for n in notes if "DOC-OLD1" in n], [])
        self.assertTrue(any("DOC-SAME" in n and "공개 순서 미확인" in n for n in notes))

    def test_a_reposted_event_on_another_date_is_held(self):
        c.atomic_json(a.ledger_path(), {"events": {}, "bootstrap": {"date": BOOT_DAY, "keys": []}})
        self.screen("2026-10-01", eps=1.0)
        self.send_alerts()  # new discovery: baseline 10/1
        self.update_doc("2026-10-05")
        self.screen("2026-10-20", eps=1.0)
        self.send_alerts()
        self.assertEqual(len(self.material_events()), 1)
        self.update_doc("2026-10-24", doc_id="DOC-A9")  # same numbers, later date: a re-post
        self.screen("2026-11-10", eps=1.0)
        self.send_alerts()
        self.assertEqual(len(self.material_events()), 1)
        self.assertTrue(any("재게재" in n for n in self.report()["candidates"][0]["a_notes"]))

    def test_business_evidence_and_eps_rise_together_make_one_event(self):
        self.boot(eps=1.0)
        self.screen("2026-10-10", eps=1.3)
        self.send_alerts()
        self.assertEqual(self.sent, [])
        self.update_doc("2026-10-10")
        self.screen("2026-10-11", eps=1.3)
        self.send_alerts()
        self.assertEqual(len(self.sent), 1)
        event = self.material_events()[0]
        self.assertEqual(sorted(event["material"]["triggers"]), ["A", "B"])

    def test_folded_company_change_is_announced(self):
        self.boot(eps=1.0)
        self.screen("2026-10-10", eps=1.0, folded=True)
        self.update_doc("2026-10-08")
        self.send_alerts()
        self.assertEqual(len(self.sent), 1)
        self.assertIn("업종 제한으로 개별 카드는 접혀", self.sent[0])


class LedgerTest(MaterialFixture):
    def test_dry_run_writes_nothing(self):
        self.boot(eps=1.0)
        before = (self.data / "candidate_alerts.json").read_text(encoding="utf-8")
        self.screen("2026-10-10", eps=1.3)
        self.send_alerts(dry=True)
        self.assertEqual((self.data / "candidate_alerts.json").read_text(encoding="utf-8"), before)
        self.assertFalse(a.material_backup_path().exists())

    def test_old_ledger_is_read_and_backed_up_once(self):
        old = self.boot(eps=1.0)
        self.screen("2026-10-10", eps=1.3)
        self.send_alerts()
        self.assertEqual(json.loads(a.material_backup_path().read_text(encoding="utf-8")), old)
        self.assertIn("material", self.ledger())
        self.screen("2026-10-11", eps=1.3)
        self.send_alerts()
        self.assertEqual(json.loads(a.material_backup_path().read_text(encoding="utf-8")), old)

    def test_failed_send_is_retried_as_the_same_event_and_uncertain_is_not(self):
        self.boot(eps=1.0)
        self.screen("2026-10-10", eps=1.3)
        self.send_alerts()
        self.screen("2026-10-11", eps=1.3)
        self.outcomes = ["failed"]
        self.send_alerts()
        key = self.material_events()[0]
        self.screen("2026-10-12", eps=1.3)
        self.send_alerts()
        events = self.material_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["status"], "sent")
        self.assertEqual(events[0]["material"]["first"], key["material"]["first"])

    def test_uncertain_event_is_never_resent(self):
        self.boot(eps=1.0)
        self.screen("2026-10-10", eps=1.3)
        self.send_alerts()
        self.screen("2026-10-11", eps=1.3)
        self.outcomes = ["uncertain"]
        self.send_alerts()
        self.screen("2026-10-12", eps=1.3)
        self.send_alerts()
        self.assertEqual(self.sent, [])
        self.assertEqual([e["status"] for e in self.material_events()], ["uncertain"])

    def test_re_review_shares_the_one_company_a_day_rule(self):
        self.boot(eps=1.0)
        self.screen("2026-10-10", eps=1.3)
        self.send_alerts()
        self.screen("2026-10-11", eps=1.3)
        c.write_rows("signal_log", [__import__("test_candidate_alerts").signal(
            0, entity_id="NASDAQ:AAA", **{"종목/티커": "AAA"})])
        self.send_alerts()
        self.assertEqual(len(self.sent), 1)


if __name__ == "__main__":
    unittest.main()
