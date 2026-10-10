"""Read-only review using existing S0 fake-model fixtures and temporary state."""
import json
import sys
from pathlib import Path
from datetime import timedelta

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tests'), str(ROOT / 'scripts')]
from test_s0_partial_extract import PartialExtractTest, http
from test_s0_recover import RecoverTest, EVENING, THU, due
import daily_run_state as d

results = {}
for label, items, answers in [
    ('503_wait_rerun', [0], {'acc-0': http(503)}),
    ('401_wait_rerun', [0, 1], {'acc-1': http(401)}),
]:
    t = PartialExtractTest()
    t.setUp()
    try:
        first = t.run_extract([t.item(n) for n in items], answers)
        second = t.run_extract([], {}, 'run-2')
        results[label] = {'first_exit': first, 'second_exit': second, 'status': t.status()}
    finally:
        t.doCleanups()

t = RecoverTest()
t.setUp()
try:
    state = t.daily()
    state['days'][THU]['recoveries'] = [
        {'started_at': (EVENING - timedelta(hours=n)).isoformat()} for n in (3, 2)]
    results['auto_after_recovery_limit'] = d.plan_detail(
        state, THU, 'auto', EVENING, {}, frozenset(), None, due)
    state = t.daily()
    plan = t.plan(state, EVENING)
    d.apply_plan(state, THU, 'r2', 'recover', 'schedule', plan, EVENING, 'sha', 'pol')
    results['recover_after_interruption'] = t.plan(state, EVENING + timedelta(minutes=61))
finally:
    t.doCleanups()

print(json.dumps(results, ensure_ascii=False, indent=2))
