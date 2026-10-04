"""O regression tests (docs/o_progress_2026-10-04.md): candidates that move together with their industry
leave room for others, and the card says when the estimate rose relative to the linked filing."""
import gzip
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import candidates as k  # noqa: E402
import common as c  # noqa: E402
import screen_revisions as sr  # noqa: E402
from test_candidates import NOW, CandidateFixture, row, snapshot  # noqa: E402

SNAPSHOT_10_4 = ROOT / "data" / "processed" / "revision_screen" / "20261004T060125Z_37181539693-1.json.gz"


def screen_row(ticker, industry, pct, yld, by_yield=True, by_growth=True):
    return {"ticker": ticker, "symbol": ticker, "industry": industry, "candidate": True, "by_yield": by_yield,
            "by_growth": by_growth, "pct_90": pct, "yield_change_90_pp": yld}


class IndustryLimitTest(unittest.TestCase):
    """O1: at most N own cards per industry in each list; the rest are folded, places go to the next rank."""

    def test_an_industry_keeps_its_top_n_and_frees_the_rest(self):
        rows = [screen_row(f"R{i}", "Refining", 300 - i, 20 - i) for i in range(5)]
        rows += [screen_row("OTHER", "Insurance", 40, 2), screen_row("NOIND", None, 30, 1.5)]
        plain_a, plain_b, none_folded = sr.rank(rows, 4)
        self.assertEqual([r["ticker"] for r in plain_a], ["R0", "R1", "R2", "R3"])
        self.assertEqual(none_folded, set())
        a, b, folded = sr.rank(rows, 4, 3)
        self.assertEqual([r["ticker"] for r in a], ["R0", "R1", "R2", "OTHER"])
        self.assertEqual(folded, {"R3", "R4"})
        groups = sr.industry_groups([r for r in rows if r["candidate"]], a, b, folded)
        self.assertEqual(groups, [{"industry": "Refining", "count": 5, "tickers": ["R0", "R1", "R2", "R3", "R4"],
                                   "shown": ["R0", "R1", "R2"], "folded": ["R3", "R4"]}])

    def test_unknown_industry_is_never_folded_and_a_card_elsewhere_is_not_folded(self):
        rows = [screen_row(f"N{i}", None, 100 - i, 10 - i) for i in range(5)]
        self.assertEqual(sr.rank(rows, 5, 1)[2], set())
        rows = [screen_row("A1", "X", 100, 10), screen_row("A2", "X", 90, 9, by_growth=False),
                screen_row("A3", "X", 80, 1, by_yield=False)]
        a, b, folded = sr.rank(rows, 5, 1)
        self.assertEqual(([r["ticker"] for r in a], [r["ticker"] for r in b]), (["A1"], ["A1"]))
        self.assertEqual(folded, {"A2", "A3"})  # A1 has its card in both lists, so it is never folded

    def test_the_stored_10_4_screen(self):
        with gzip.open(SNAPSHOT_10_4, "rt", encoding="utf-8") as handle:
            derived = json.load(handle)["derived"]
        a, b, folded = sr.rank(derived["rows"], 20, sr.settings()["max_per_industry"])
        shown = {r["ticker"] for r in a + b}
        self.assertEqual(len(shown), 33)
        self.assertTrue({"OSCR", "VSEC"} <= shown)  # N2: OSCR was a missed priority candidate
        self.assertEqual(folded, {"PARR", "DINO", "VLO", "PSX", "CVI"})
        self.assertTrue({"PBF", "DK", "MPC"} <= shown)  # the industry's top ones keep their own cards
        refining = next(g for g in sr.industry_groups([r for r in derived["rows"] if r["candidate"]], a, b, folded)
                        if g["industry"] == "Oil & Gas Refining & Marketing")
        self.assertEqual(refining["count"], 9)


class IndustryGroupCardTest(CandidateFixture):
    """O1 on the card, the list, /screen and the departed reason."""

    def write(self, snap, name="20260925T020000Z_2-1.json.gz"):
        with gzip.open(c.DATA_DIR / "revision_screen" / name, "wt", encoding="utf-8") as h:
            json.dump(snap, h)

    def grouped_snapshot(self):
        snap = snapshot(rows=[row("AAA", industry="Refining"), row("BBB", by_yield=False, industry="Refining"),
                              row("CRDO", by_growth=False), row("DDD", industry="Refining")],
                        finished="2026-09-25T02:00:00+00:00", run_id="2-1")
        snap["derived"]["industry_groups"] = [{"industry": "Refining", "count": 3, "tickers": ["AAA", "BBB", "DDD"],
                                               "shown": ["AAA", "BBB"], "folded": ["DDD"]}]
        return snap

    def test_card_list_and_screen_show_the_group(self):
        self.write(self.grouped_snapshot())
        k.generate(now=NOW, translate_now=False)
        index = k.load_index()
        card = next(x for x in index["candidates"] if x["identity"]["ticker"] == "AAA")
        self.assertEqual(card["industry_group"]["folded"], ["DDD"])
        text = k.telegram_card(card)
        self.assertIn("같은 업종 동반 상향: Refining 3곳", text)
        self.assertIn("원인은 미확인", text)
        crdo = next(x for x in index["candidates"] if x["identity"]["ticker"] == "CRDO")
        self.assertIsNone(crdo["industry_group"])
        markdown = (c.ROOT / "docs" / "candidates.md").read_text(encoding="utf-8")
        self.assertIn("## 같은 업종 동반 상향 (묶음)", markdown)
        self.assertIn("DDD +100%", markdown)
        self.assertIn("묶음: Refining 3곳", k.telegram_screen()[0])

    def test_a_folded_known_candidate_is_labelled_as_grouped(self):
        snap = snapshot(rows=[row("AAA", industry="Refining"), row("BBB", by_yield=False), row("CRDO", by_growth=False)],
                        finished="2026-09-25T02:00:00+00:00", run_id="2-1")
        self.write(snap)
        k.generate(now=NOW, translate_now=False)  # AAA has a card
        later = self.grouped_snapshot()
        later["derived"]["top_yield"] = ["CRDO"]
        later["derived"]["top_growth"] = ["BBB"]
        later["derived"]["industry_groups"][0].update(shown=["BBB"], folded=["AAA", "DDD"])
        later["run"].update(finished_at="2026-09-25T02:30:00+00:00", run_id="3-1")
        self.write(later, "20260925T023000Z_3-1.json.gz")
        k.generate(now=NOW, translate_now=False)
        departed = k.load_index()["departed"][self.aaa["candidate_id"]]
        self.assertEqual(departed["reason"], "industry_folded")


class RevisionTimingTest(unittest.TestCase):
    """O2: when the estimate rose, against the newest linked filing; a possibility, never a cause."""

    def cand(self, now, d30, d90):
        return {"observed_at": "2026-10-04T06:15:47+00:00", "eps": {"eps_now": now, "eps_30d": d30, "eps_90d": d90}}

    def test_a_recent_rise_after_an_older_filing_is_flagged(self):
        text = k.revision_timing(self.cand(1.38, 0.30, 0.30), {"documents": [{"filed_at": "2026-07-14"}]})
        self.assertIn("최근 30일(2026-09-04 이후) 몫 100%", text)
        self.assertIn("연결 원문 최신 제출 2026-07-14(최근 30일 시작 이전)", text)
        self.assertIn("설명하지 못할 수 있음", text)
        self.assertNotIn("때문", text)  # no cause is claimed

    def test_an_older_rise_or_a_recent_filing_is_not_flagged(self):
        early = k.revision_timing(self.cand(1.66, 1.44, -0.09), {"documents": [{"filed_at": "2026-08-04"}]})
        self.assertIn("몫 13%", early)
        self.assertNotIn("설명하지 못할", early)
        recent = k.revision_timing(self.cand(1.38, 0.30, 0.30),
                                   {"documents": [{"filed_at": "2026-07-14"}, {"filed_at": "2026-09-20"}]})
        self.assertIn("2026-09-20(최근 30일 시작 이후)", recent)
        self.assertNotIn("설명하지 못할", recent)

    def test_dip_no_rise_and_no_document(self):
        self.assertIn("90일 전체 변화보다 큼", k.revision_timing(self.cand(3.0, 1.0, 2.0), {"documents": []}))
        self.assertIn("연결된 공식 원문 없음", k.revision_timing(self.cand(3.0, 1.0, 2.0), {}))
        self.assertIsNone(k.revision_timing(self.cand(1.0, 1.0, 1.0), {}))
        self.assertIsNone(k.revision_timing({"observed_at": "2026-10-04T00:00:00+00:00", "eps": {}}, {}))


if __name__ == "__main__":
    unittest.main()
