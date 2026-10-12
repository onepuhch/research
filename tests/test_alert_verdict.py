"""The suggested judgment on new-discovery alerts (alert_verdict.py): fixed rules on screen fields only."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import alert_verdict as av  # noqa: E402


def cand(up=3, down=0, analysts=6, now=1.30, d30=1.05, d90=1.00, pct=30.0, price=5.0, rank=12,
         industry="Software", documents=None):
    return {"eps": {"eps_target_period": "2027-12-31", "eps_now": now, "eps_30d": d30, "eps_90d": d90,
                    "up30": up, "down30": down, "analysts": analysts, "pct_90": pct},
            "price": {"price_status": "success", "price_pct_90": price} if price is not None else {},
            "memberships": [{"list": "A", "rank": rank}], "observed_at": "2026-10-12T06:20:00+00:00",
            "industry": industry, "context": {"documents": documents or []}}


def previous(c, **change):
    return {**{k: c["eps"][k] for k in ("eps_target_period", "eps_now", "eps_30d", "eps_90d")}, **change}


class VerdictTest(unittest.TestCase):
    def test_broad_raise_with_own_move_is_consider(self):
        c = cand()
        v = av.assess(c, previous(c, eps_now=1.20))
        self.assertEqual(v["verdict"], "consider")
        self.assertIn("분석가 6명 중 3명이 올림(내린 사람 없음)", v["pros"][0])
        self.assertTrue(any("또 올라감(+8%)" in x for x in v["pros"]))
        self.assertIn("'추적'으로 답장", v["next"])

    def test_rank_shuffle_with_one_raise_is_low(self):
        c = cand(up=1, analysts=4, rank=19)
        v = av.assess(c, previous(c))
        self.assertEqual(v["verdict"], "low")
        self.assertTrue(any("1명만 올림" in x for x in v["cons"]))
        self.assertTrue(any("지난번 관측과 같음" in x and "19위" in x for x in v["cons"]))

    def test_rank_shuffle_with_broad_raises_is_watch(self):
        c = cand(up=13, analysts=15, rank=20)
        self.assertEqual(av.assess(c, previous(c))["verdict"], "watch")

    def test_a_few_cuts_among_many_raises_stay_broad(self):
        c = cand(up=9, down=1, analysts=10)
        v = av.assess(c, previous(c, eps_now=1.2))
        self.assertEqual(v["verdict"], "consider")
        self.assertIn("같은 30일에 내린 분석가도 1명", v["cons"])

    def test_raises_by_a_small_share_of_analysts_are_not_broad(self):
        c = cand(up=3, down=1, analysts=33)
        v = av.assess(c, previous(c, eps_now=1.2))
        self.assertEqual(v["verdict"], "watch")
        self.assertTrue(any("일부 분석가의 상향" in x for x in v["cons"]))

    def test_price_that_already_moved_blocks_consider(self):
        c = cand(price=40.0)
        v = av.assess(c, previous(c, eps_now=1.2))
        self.assertEqual(v["verdict"], "watch")
        self.assertTrue(any("이미 움직임" in x for x in v["cons"]))

    def test_estimate_that_fell_is_low(self):
        c = cand()
        self.assertEqual(av.assess(c, previous(c, eps_now=2.0))["verdict"], "low")

    def test_tiny_own_rise_is_not_a_reason(self):
        c = cand(up=1)
        v = av.assess(c, previous(c, eps_now=1.299))
        self.assertFalse(any("또 올라감" in x for x in v["pros"]))
        self.assertEqual(v["verdict"], "watch")  # moved itself, so not a rank shuffle

    def test_no_previous_snapshot_says_nothing_about_own_change(self):
        v = av.assess(cand(), None)
        self.assertFalse(any("지난번 관측" in x for x in v["pros"] + v["cons"]))
        self.assertEqual(v["verdict"], "consider")

    def test_filing_in_the_rise_window_is_a_possible_cause(self):
        docs = [{"document_id": "D1", "form": "8-K", "filed_at": "2026-09-30"},
                {"document_id": "D0", "form": "8-K", "filed_at": "2026-07-22"}]
        v = av.assess(cand(documents=docs), None)
        self.assertIn("9/30 회사 공식 발표(SEC 8-K)", v["cause"])
        self.assertIn("가능성", v["cause"])
        old = av.assess(cand(documents=docs[1:]), None)
        self.assertIn("아직 모름", old["cause"])
        early = av.assess(cand(d30=1.25, documents=docs), None)  # most of the rise was before 30 days
        self.assertIn("아직 모름", early["cause"])

    def test_few_analysts_and_reit_are_cautions(self):
        v = av.assess(cand(up=2, analysts=3, industry="REIT - Diversified"), None)
        self.assertTrue(any("3명뿐" in x for x in v["cons"]))
        self.assertTrue(any("REIT" in x for x in v["cons"]))

    def test_no_buy_language(self):
        for c in (cand(), cand(up=1), cand(price=40.0)):
            v = av.assess(c, None)
            text = " ".join(v["pros"] + v["cons"] + [v["cause"], v["next"], v["label"]])
            for word in ("매수", "목표가", "상승 확률", "저평가"):
                self.assertNotIn(word, text)


if __name__ == "__main__":
    unittest.main()
