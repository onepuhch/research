"""Companies that may be alerted today are researched and drafted first (2026-10-12)."""
import pathlib
import sys
import unittest
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import candidate_alerts  # noqa: E402
import candidate_context as ctx  # noqa: E402
import candidates  # noqa: E402

NOW = datetime(2026, 10, 12, 6, 0, tzinfo=timezone.utc)


def target(n, folded=False, first_seen="2026-10-01T00:00:00+00:00"):
    return {"candidate_id": f"CAN-{n}", "ticker": f"T{n}", "entity_id": f"NASDAQ:T{n}", "rank": n,
            "first_seen_at": first_seen, "eps_key": "x", "eps_target_period": "2027-12-31", "folded": folded}


def key(n):
    return candidate_alerts.logical_key(f"NASDAQ:T{n}", candidates.THESIS_KEY, candidate_alerts.NEW)


class AlertFirstTest(unittest.TestCase):
    def test_only_unalerted_card_companies(self):
        ledger = {"events": {key(1): {}}, "bootstrap": {"keys": [key(2)]}}
        targets = [target(1), target(2), target(3), target(4, folded=True)]
        with mock.patch.object(candidate_alerts, "load_ledger", return_value=ledger):
            self.assertEqual(ctx.alert_first(targets), {"CAN-3"})

    def test_unreadable_ledger_gives_no_priority(self):
        with mock.patch.object(candidate_alerts, "load_ledger", side_effect=ValueError("broken")):
            self.assertEqual(ctx.alert_first([target(1)]), set())

    def test_select_puts_them_before_older_waiting_companies(self):
        old = [target(n, first_seen="2026-09-25T00:00:00+00:00") for n in range(1, 5)]
        new = target(9, first_seen="2026-10-12T00:00:00+00:00")
        state = {"candidates": {}}
        plain = [t["candidate_id"] for t in ctx.select(old + [new], state, NOW, 2)]
        self.assertNotIn("CAN-9", plain)
        chosen = [t["candidate_id"] for t in ctx.select(old + [new], state, NOW, 2, first={"CAN-9"})]
        self.assertEqual(chosen[0], "CAN-9")

    def test_draft_order_keeps_folded_share_and_queue_order(self):
        queue = [(f"C{n}", {}) for n in range(6)] + [("F0", {})]
        order = [cid for cid, _ in ctx.draft_order(queue, {"F0"}, 3, 1, {"C4", "C2"})]
        self.assertEqual(order[:3], ["C2", "C4", "F0"])  # first ones in queue order, then the folded share
        self.assertEqual(order[3:], ["C0", "C1", "C3", "C5"])
        self.assertEqual([cid for cid, _ in ctx.draft_order(queue, {"F0"}, 3, 1)][:3], ["C0", "C1", "F0"])


if __name__ == "__main__":
    unittest.main()
