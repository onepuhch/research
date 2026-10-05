"""Read-only P acceptance probes. Synthetic data, temporary repositories, no external requests.

Run: python -X utf8 docs/q_p_boundary_probe_2026-10-05.py
Exit 1 means at least one Q follow-up boundary remains open; stdout is JSON evidence.
The existing 516-test suite is independent of these additional probes.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]

import common as c
import candidate_context
import discovery_timing as timing
import material_updates as material
import persist_state
from test_p2_material import MaterialFixture, THESIS
from test_p3_timing import closes
from test_p_followup import SubjectDraftPathTest


def update_case(name, filed, report, text):
    f = MaterialFixture()
    try:
        f.setUp()
        ledger = f.boot(eps=1.0)
        index = f.screen("2026-10-10", eps=1.0)
        f.update_doc(filed, report=report, text=text)
        items, diagnostics, _ = material.evaluate(index, ledger, candidate_context.load_state())
        result = {"case": name, "expected": "no_A_alert", "actual": "A_alert" if items else "no_A_alert",
                  "filed_at": filed, "report_date": report, "sentence": text,
                  "triggers": [x["material"]["triggers"] for x in items], "fixed": not items}
    finally:
        f.doCleanups()
    return result


def baseline_case():
    f = MaterialFixture()
    try:
        f.setUp()
        f.boot(eps=1.0)
        f.screen("2026-10-10", eps=1.30)
        f.update_doc("2026-10-09")
        f.send_alerts()  # fake delivery + fake persistence from the isolated fixture
        announced = f.material_events()[0]
        index = f.screen("2026-10-11", eps=1.31)
        _, diagnostics, _ = material.evaluate(index, f.ledger(), candidate_context.load_state())
        diag = diagnostics[0]
        result = {"case": "A_only_moves_B_baseline", "first_alert_triggers": announced["material"]["triggers"],
                  "expected_B_baseline_eps": 1.0, "actual_B_baseline_eps": diag["baseline"]["eps_now"],
                  "actual_B_pct": diag["pct"], "actual_B_status": diag["b"],
                  "fixed": diag["baseline"]["eps_now"] == 1.0 and diag["b"] == "confirmed"}
    finally:
        f.doCleanups()
    return result


def outcome_case():
    record = {"ticker": "AAA", "first_pass": {"observed_at": "2026-09-25T01:00:00+00:00"}, "first_card": None}
    batch = {"retrieved_at": "2027-05-01T00:00:00+00:00",
             "series": {"AAA": closes("2026-09-20", 220), "SPY": closes("2026-09-20", 220)}}
    before = timing.outcomes(record, batch)[30]
    record["first_card"] = {"observed_at": "2026-10-05T01:00:00+00:00"}
    after = timing.outcomes(record, batch)[30]
    return {"case": "outcome_start_moves_on_later_card", "expected": "fixed_population_start",
            "before": {k: before.get(k) for k in ("start", "due", "net_pct")},
            "after": {k: after.get(k) for k in ("start", "due", "net_pct")},
            "fixed": before.get("start") == after.get("start")}


def subject_case():
    answer = SubjectDraftPathTest().run_with("Northstar Acquisition LLC", issuer_name="Northstar Manufacturing Inc.")
    return {"case": "shared_name_word_is_not_same_entity", "expected": "withhold_unverified_subject",
            "accepted_claims": len(answer["claims"]), "fixed": len(answer["claims"]) == 0}


def remote_new_state_case():
    """A real local bare remote adds a new state path absent from the local enumeration."""
    def git(where, *args):
        return subprocess.run(["git", *args], cwd=where, check=True, capture_output=True,
                              encoding="utf-8").stdout.strip()

    with tempfile.TemporaryDirectory(prefix="codex-q-persist-probe-") as directory:
        root = Path(directory).resolve()
        remote, work, other = (root / name for name in ("remote.git", "work", "other"))
        assert all(path.resolve().is_relative_to(root) for path in (remote, work, other))
        git(root, "init", "--bare", "-q", str(remote))
        git(root, "clone", "-q", str(remote), str(work))
        for key, value in (("user.name", "Q probe"), ("user.email", "probe@example.invalid"), ("commit.gpgsign", "false")):
            git(work, "config", key, value)
        alerts = work / "data/processed/candidate_alerts.json"
        alerts.parent.mkdir(parents=True)
        alerts.write_text('{"events": {}}', encoding="utf-8")
        git(work, "add", ".")
        git(work, "commit", "-qm", "seed")
        git(work, "push", "-qu", "origin", "HEAD")
        git(root, "clone", "-q", str(remote), str(other))
        for key, value in (("user.name", "Q probe"), ("user.email", "probe@example.invalid"), ("commit.gpgsign", "false")):
            git(other, "config", key, value)
        new_path = "data/processed/company_documents/DOC-NEW.json.gz"
        new_doc = other / new_path
        new_doc.parent.mkdir(parents=True)
        new_doc.write_bytes(b"synthetic-state")
        git(other, "add", ".")
        git(other, "commit", "-qm", "another writer adds state")
        git(other, "push", "-q")
        alerts.write_text('{"events": {"local": {}}}', encoding="utf-8")
        git(work, "add", ".")
        git(work, "commit", "-qm", "local state")
        with mock.patch.object(c, "ROOT", work):
            try:
                persist_state.replay_on_remote(["data/processed/candidate_alerts.json"])
                blocked = False
            except subprocess.CalledProcessError:
                blocked = True
        return {"case": "remote_new_state_path_must_block_replay", "remote_added": new_path,
                "expected": "blocked_other_writer", "actual": "blocked" if blocked else "replayed",
                "fixed": blocked}


def main():
    results = [
        update_case("old_event_in_later_filing", "2026-10-01", "2026-09-01",
                    "On September 1, 2026, the company received a purchase order valued at $50 million."),
        update_case("unchanged_guidance_is_not_new_change", "2026-10-01", "2026-10-01",
                    "The company reaffirmed its unchanged revenue outlook of $50 million for fiscal 2027."),
        baseline_case(), outcome_case(), subject_case(), remote_new_state_case(),
    ]
    print(json.dumps({"baseline_head": "fcab8a9", "probes": results,
                      "open_boundaries": sum(not r["fixed"] for r in results)}, ensure_ascii=True, indent=2))
    return int(any(not r["fixed"] for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
