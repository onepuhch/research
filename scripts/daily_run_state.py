"""Daily run completion by step, so a failed or stale step is redone the same KST day.

The required steps and both kinds of step relation are defined here and nowhere
else (the workflow only asks the plan whether to start a step):

  requires  the step must not run unless these succeeded; otherwise it is
            recorded as blocked and its command is never called.
  inputs    the step reads these outputs; whenever one of them finishes again
            (success or failure), the step is redone so it reflects the change.
            "@name" is state changed outside the daily steps (a /track command,
            human evidence); its revision is a hash of that state.

Each step records execution_status (pending/started/success/failed/blocked)
separately from quality_status (complete/partial/unavailable/unknown). Exit
code 0 means the process ended, not that the data is complete. A partial step
gets a limited automatic top-up (research_policy daily_run).

State lives in data/processed/daily_runs.json and is committed with the step's
outputs by persist_state, so a rejected push leaves no remote success record and
the next run retries.

Modes:
  daily     explicit full run of every required step (a new run record)
  auto      only steps not yet done today, stale renders, due partial top-ups,
            plus every step that requires or reads them
  commands  Telegram commands only; never counts toward the daily run

Usage (from the workflow):
  python scripts/daily_run_state.py plan --mode auto >> "$GITHUB_ENV"
  python scripts/daily_run_state.py step collect -- python scripts/collect.py
  python scripts/daily_run_state.py finish
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import common as c

KST = timezone(timedelta(hours=9))
STATE_PATH = c.DATA_DIR / "daily_runs.json"
SCHEMA_VERSION = 2
KEEP_DAYS = 60
KEEP_ATTEMPTS = 10
MONDAY = 0
DEFAULT_POLICY = {"partial_retry_max": 1, "partial_retry_min_gap_minutes": 60}


@dataclass(frozen=True)
class Step:
    requires: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ()
    weekday: int | None = None
    # A render step is redone when its generator version changes, without recollecting inputs.
    version: str | None = None


# Order is the workflow order: collection/calculation -> baseline -> returns -> views -> weekly.
STEPS: dict[str, Step] = {
    "collect": Step(),
    "extract": Step(requires=("collect",)),   # never extracts from an older collection
    "eps": Step(inputs=("@tracking",)),          # a newly tracked ticker is collected the same day
    "notify": Step(requires=("extract",)),     # tracked-company risk alerts; independent of cards
    "quarterly": Step(inputs=("@tracking",)),
    "screen": Step(),
    "prices": Step(inputs=("@tracking",)),
    # Version tracks candidates.GENERATOR_VERSION: a new card generator redoes the cards.
    "cards": Step(inputs=("screen", "@tracking", "@evidence"), version="cards-v2"),
    # New-candidate alerts (news + screen, one daily budget). A failed cards step stops only these.
    "alerts": Step(requires=("cards",), inputs=("extract",)),
    "baseline": Step(),                        # research_journal --capture: frozen case baselines
    "returns": Step(inputs=("baseline",)),
    "views": Step(inputs=("extract", "eps", "quarterly", "screen", "prices", "cards", "alerts", "baseline", "returns"),
                  version="views-v2"),
    "community": Step(weekday=MONDAY),
    "weekly_report": Step(requires=("views",), weekday=MONDAY),
}
MODES = ("daily", "auto", "commands")
EXECUTION = ("pending", "started", "success", "failed", "blocked")
QUALITY = ("complete", "partial", "unavailable", "unknown")


def kst_day(now: datetime) -> str:
    return now.astimezone(KST).date().isoformat()


def required_steps(day: str) -> list[str]:
    weekday = date.fromisoformat(day).weekday()
    return [name for name, step in STEPS.items() if step.weekday is None or step.weekday == weekday]


def uses(name: str) -> tuple[str, ...]:
    return STEPS[name].requires + STEPS[name].inputs


def dependents(names: set[str], required: list[str]) -> set[str]:
    """names plus every required step that directly or indirectly requires or reads them."""
    result = set(names)
    changed = True
    while changed:
        changed = False
        for name in required:
            if name not in result and any(dep in result for dep in uses(name)):
                result.add(name)
                changed = True
    return result


def day_steps(state: dict, day: str) -> dict:
    return state.get("days", {}).get(day, {}).get("steps", {})


def tracking_revision() -> str:
    """Which companies the user tracks: changes when /track registers or an idea closes."""
    rows = sorted((r.get("idea_id", ""), r.get("ticker", ""), r.get("entity_id", ""),
                   r.get("현재 단계") != "제외" and r.get("검토 상태") != "종료")
                  for r in c.read_live_rows("investment_review_log"))
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def evidence_revision() -> str:
    path = c.DATA_DIR / "candidate_evidence.json"
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16] if path.exists() else "none"


EXTERNAL = {"@tracking": tracking_revision, "@evidence": evidence_revision}


def input_revisions(steps: dict, name: str) -> dict:
    return {dep: EXTERNAL[dep]() if dep in EXTERNAL else steps.get(dep, {}).get("revision")
            for dep in STEPS[name].inputs}


def stale(steps: dict, name: str) -> bool:
    """A successful step whose inputs or generator changed since it ran."""
    entry = steps.get(name, {})
    step = STEPS[name]
    if step.version is not None and entry.get("version") != step.version:
        return True
    return bool(step.inputs) and entry.get("inputs") != input_revisions(steps, name)


def retry_due(entry: dict, now: datetime, policy: dict) -> bool:
    """A partial result gets a limited top-up, spaced from the last attempt."""
    if entry.get("quality_status") != "partial" or not entry.get("finished_at"):
        return False
    if entry.get("auto_retries", 0) >= policy["partial_retry_max"]:
        return False
    gap = timedelta(minutes=policy["partial_retry_min_gap_minutes"])
    return datetime.fromisoformat(entry["finished_at"]) + gap <= now


def plan_detail(state: dict, day: str, mode: str, now: datetime | None = None,
                policy: dict | None = None, redo: set[str] | frozenset = frozenset()) -> dict[str, str]:
    """{step: why} for the steps to run now, in workflow order.

    redo (auto only) asks for named steps to run again today, with the steps that use them.
    """
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode}")
    unknown = set(redo) - set(STEPS)
    if unknown:
        raise ValueError(f"unknown redo step {sorted(unknown)}")
    if mode == "commands":
        return {}
    required = required_steps(day)
    if mode == "daily":
        return {name: "daily" for name in required}
    now = now or datetime.now(timezone.utc)
    policy = {**DEFAULT_POLICY, **(policy or {})}
    steps = day_steps(state, day)
    why: dict[str, str] = {}
    for name in required:
        entry = steps.get(name, {})
        if name in redo:
            why[name] = "requested"
        elif entry.get("execution_status") != "success":
            why[name] = entry.get("execution_status") or "not_run"
        elif stale(steps, name):
            why[name] = "inputs_changed"
        elif retry_due(entry, now, policy):
            why[name] = "partial_retry"
    for name in dependents(set(why), required) - set(why):
        why[name] = "dependency_rerun"
    return {name: why[name] for name in required if name in why}


def plan(state: dict, day: str, mode: str, now: datetime | None = None, policy: dict | None = None,
         redo: set[str] | frozenset = frozenset()) -> list[str]:
    return list(plan_detail(state, day, mode, now, policy, redo))


def day_record(state: dict, day: str) -> dict:
    return state.setdefault("days", {}).setdefault(day, {"runs": [], "steps": {}})


def apply_plan(state: dict, day: str, run_id: str, mode: str, event: str, detail: dict[str, str],
               now: datetime, code_version: str, policy_hash: str) -> dict:
    """Record the run and invalidate every planned step, in one state write.

    An earlier success of a planned step no longer counts: if this run stops
    after an upstream step, the next plan still sees the rest as pending.
    """
    record = day_record(state, day)
    stamp = now.isoformat(timespec="seconds")
    record["runs"].append({
        "run_id": run_id, "mode": mode, "event": event, "planned": list(detail), "reasons": detail,
        "started_at": stamp, "finished_at": None, "code_version": code_version, "policy_hash": policy_hash})
    for name, why in detail.items():
        entry = record["steps"].setdefault(name, {})
        entry.update(execution_status="pending", planned_by=run_id, planned_at=stamp, plan_reason=why)
        if why == "partial_retry":
            entry["auto_retries"] = entry.get("auto_retries", 0) + 1
    return state


def start_run(state: dict, day: str, run_id: str, mode: str, event: str, planned: list[str],
              now: datetime, code_version: str, policy_hash: str) -> dict:
    return apply_plan(state, day, run_id, mode, event, {name: mode for name in planned},
                      now, code_version, policy_hash)


def blocking(steps: dict, name: str) -> tuple[str, dict] | None:
    """The first required predecessor that has not succeeded, if any."""
    for dep in STEPS[name].requires:
        if steps.get(dep, {}).get("execution_status") != "success":
            return dep, steps.get(dep, {})
    return None


def record_step(state: dict, day: str, step: str, status: str, run_id: str, now: datetime,
                exit_code: int | None = None, quality: str = "unknown", reason: str | None = None,
                dependency_run_id: str | None = None) -> dict:
    """status: started | success | failed | blocked. The latest attempt decides.

    last_success_at and the previous attempts are kept. Every finished run of
    the command (success or failure) gives the step a new output revision, so
    steps that read it are redone.
    """
    if step not in STEPS:
        raise ValueError(f"unknown step {step}")
    if status not in EXECUTION or status == "pending":
        raise ValueError(f"unknown step status {status}")
    if quality not in QUALITY:
        raise ValueError(f"unknown quality {quality}")
    steps = day_record(state, day)["steps"]
    entry = steps.setdefault(step, {})
    stamp = now.isoformat(timespec="seconds")
    same_run = entry.get("run_id") == run_id and entry.get("execution_status") == "started"
    entry.update(execution_status=status, run_id=run_id)
    if status == "started":
        entry.update(started_at=stamp, finished_at=None, exit_code=None, quality_status="unknown")
        entry.pop("blocked_reason", None)
        entry.pop("dependency_run_id", None)
        if STEPS[step].inputs:
            entry["inputs"] = input_revisions(steps, step)
        if STEPS[step].version is not None:
            entry["version"] = STEPS[step].version
        return state
    if status == "blocked":
        entry.update(started_at=None, finished_at=stamp, exit_code=None, quality_status="unknown",
                     blocked_reason=reason, dependency_run_id=dependency_run_id)
    else:
        if not same_run:
            entry["started_at"] = None
        entry.update(finished_at=stamp, exit_code=exit_code,
                     quality_status=quality if status == "success" else "unknown",
                     revision=f"{run_id}@{stamp}")
        if status == "success":
            entry["last_success_at"] = stamp
    attempts = entry.setdefault("attempts", [])
    attempts.append({k: entry.get(k) for k in ("run_id", "execution_status", "quality_status", "started_at",
                                                "finished_at", "exit_code", "revision", "blocked_reason")})
    del attempts[:-KEEP_ATTEMPTS]
    return state


def finish_run(state: dict, day: str, run_id: str, now: datetime) -> dict:
    for run in day_record(state, day)["runs"]:
        if run["run_id"] == run_id:
            run["finished_at"] = now.isoformat(timespec="seconds")
    return state


def complete(state: dict, day: str, now: datetime | None = None, policy: dict | None = None) -> bool:
    """Every required step ran successfully on current inputs, with no top-up due.

    A partial step whose top-ups are used up still counts as done here; its
    quality stays partial (see quality_summary).
    """
    return plan(state, day, "auto", now, policy) == []


def quality_summary(state: dict, day: str) -> dict[str, str]:
    steps = day_steps(state, day)
    return {name: steps.get(name, {}).get("quality_status", "unknown") for name in required_steps(day)
            if steps.get(name, {}).get("quality_status") not in (None, "unknown", "complete")}


def prune(state: dict, today: str) -> dict:
    cutoff = (date.fromisoformat(today) - timedelta(days=KEEP_DAYS)).isoformat()
    state["days"] = {d: v for d, v in state.get("days", {}).items() if d >= cutoff}
    return state


def migrate(state: dict) -> dict:
    """Schema 1 stored one "status". Keep it as the execution status; past quality stays unknown."""
    for record in state.get("days", {}).values():
        for entry in record.get("steps", {}).values():
            if "status" in entry:
                entry.setdefault("execution_status", entry.pop("status"))
                entry.setdefault("quality_status", "unknown")
    state["schema_version"] = SCHEMA_VERSION
    return state


# -------------------------------------------------------------- step quality

def screen_quality(run_id: str) -> str:
    """Quality of this run's screener snapshot; an earlier run's status never counts."""
    import screen_revisions
    matches = sorted(screen_revisions.SCREEN_DIR.glob(f"*_{run_id}.json.gz"))
    if not matches:
        return "unknown"
    with gzip.open(matches[-1], "rt", encoding="utf-8") as handle:
        run = json.load(handle).get("run", {})
    if run.get("run_id") != run_id:
        return "unknown"
    return {"success": "complete", "degraded": "partial"}.get(run.get("status"), "unknown")


QUALITY_PROBES = {"screen": screen_quality}


# ------------------------------------------------------------------------ CLI

def load() -> dict:
    return migrate(c.read_json(STATE_PATH, {"schema_version": SCHEMA_VERSION, "days": {}}))


def save(state: dict) -> None:
    c.atomic_json(STATE_PATH, state)


def env_name(step: str) -> str:
    return "RUN_" + step.upper()


def code_version() -> str:
    return (os.environ.get("GITHUB_SHA") or "local")[:12]


def policy_hash() -> str:
    path = c.ROOT / "config" / "research_policy.json"
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12] if path.exists() else "missing"


def run_policy() -> dict:
    return {**DEFAULT_POLICY, **c.policy().get("daily_run", {})}


def cmd_plan(mode: str, event: str, redo: str = "") -> int:
    now = datetime.now(timezone.utc)
    day = kst_day(now)
    state = prune(load(), day)
    names = {x.strip() for x in redo.split(",") if x.strip()}
    detail = plan_detail(state, day, mode, now, run_policy(), names if mode == "auto" else frozenset())
    run_id = (f"{os.environ['GITHUB_RUN_ID']}-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}"
              if os.environ.get("GITHUB_RUN_ID") else f"local-{uuid.uuid4().hex[:8]}")
    if detail:  # A commands-only run leaves no daily run record.
        save(apply_plan(state, day, run_id, mode, event, detail, now, code_version(), policy_hash()))
    for name in STEPS:
        print(f"{env_name(name)}={'true' if name in detail else 'false'}")
    print(f"DAILY_DAY={day}")
    print(f"DAILY_RUN_ID={run_id}")
    reasons = " ".join(f"{name}({why})" for name, why in detail.items()) or "none"
    print(f"DAILY_STEPS={reasons}", file=sys.stderr)
    return 0


def cmd_step(step: str, command: list[str]) -> int:
    day, run_id = os.environ["DAILY_DAY"], os.environ["DAILY_RUN_ID"]
    state = load()
    blocked = blocking(day_steps(state, day), step)
    if blocked:
        dep, entry = blocked
        reason = f"{dep} {entry.get('execution_status') or 'not_run'}"
        save(record_step(state, day, step, "blocked", run_id, datetime.now(timezone.utc),
                         reason=reason, dependency_run_id=entry.get("run_id")))
        # The failed dependency already fails the job; this step is recorded, not run.
        print(f"::warning::{step} blocked: {reason}")
        return 0
    save(record_step(state, day, step, "started", run_id, datetime.now(timezone.utc)))
    code = subprocess.run(command, cwd=c.ROOT).returncode
    status = "success" if code == 0 else "failed"
    quality = QUALITY_PROBES[step](run_id) if status == "success" and step in QUALITY_PROBES else "unknown"
    save(record_step(load(), day, step, status, run_id, datetime.now(timezone.utc), code, quality))
    return code


def cmd_finish() -> int:
    day, run_id = os.environ.get("DAILY_DAY"), os.environ.get("DAILY_RUN_ID")
    if not day or not run_id:
        return 0
    state = load()
    if any(r["run_id"] == run_id for r in state.get("days", {}).get(day, {}).get("runs", [])):
        save(finish_run(state, day, run_id, datetime.now(timezone.utc)))
    state = load()
    print(f"[daily] {day} complete={complete(state, day, policy=run_policy())} "
          f"quality_gaps={quality_summary(state, day) or 'none'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    command: list[str] = []
    if "--" in argv:
        split = argv.index("--")
        argv, command = argv[:split], argv[split + 1:]
    parser = argparse.ArgumentParser(description="Daily run completion state")
    sub = parser.add_subparsers(dest="action", required=True)
    p_plan = sub.add_parser("plan")
    p_plan.add_argument("--mode", choices=MODES, required=True)
    p_plan.add_argument("--event", default="")
    p_plan.add_argument("--redo", default="", help="auto only: comma-separated steps to run again today")
    p_step = sub.add_parser("step")
    p_step.add_argument("name", choices=list(STEPS))
    sub.add_parser("finish")
    args = parser.parse_args(argv)
    if args.action == "plan":
        return cmd_plan(args.mode, args.event, args.redo)
    if args.action == "step":
        if not command:
            parser.error("step needs a command after --")
        return cmd_step(args.name, command)
    return cmd_finish()


if __name__ == "__main__":
    raise SystemExit(main())
