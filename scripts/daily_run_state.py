"""Daily run completion by step, so a failed step is retried the same KST day.

The required steps and their dependencies are defined here and nowhere else.
A step counts as done only with status "success" in data/processed/daily_runs.json.
That file is committed with the step's outputs by persist_state, so a
rejected push leaves no remote success record and the next run retries.

Modes:
  daily     explicit full run of every required step (a new run record)
  auto      run only steps not yet successful today, plus steps that use their output
  commands  Telegram commands only; never counts toward the daily run

Usage (from the workflow):
  python scripts/daily_run_state.py plan --mode auto >> "$GITHUB_ENV"
  python scripts/daily_run_state.py step collect -- python scripts/collect.py
  python scripts/daily_run_state.py finish
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

import common as c

KST = timezone(timedelta(hours=9))
STATE_PATH = c.DATA_DIR / "daily_runs.json"
KEEP_DAYS = 60
MONDAY = 0

# name: (dependencies, weekday or None). Order is the workflow order.
STEPS: dict[str, tuple[tuple[str, ...], int | None]] = {
    "collect": ((), None),
    "extract": (("collect",), None),     # never extracts from an older collection
    "eps": ((), None),
    "notify": (("extract",), None),
    "quarterly": ((), None),
    "screen": ((), None),
    "prices": ((), None),
    "views": (("extract", "eps", "quarterly", "prices"), None),
    "returns": ((), None),
    "community": ((), MONDAY),
    "weekly_report": (("views",), MONDAY),
}
MODES = ("daily", "auto", "commands")


def kst_day(now: datetime) -> str:
    return now.astimezone(KST).date().isoformat()


def required_steps(day: str) -> list[str]:
    weekday = date.fromisoformat(day).weekday()
    return [name for name, (_, only) in STEPS.items() if only is None or only == weekday]


def dependents(names: set[str], required: list[str]) -> set[str]:
    """names plus every required step that directly or indirectly uses them."""
    result = set(names)
    changed = True
    while changed:
        changed = False
        for name in required:
            if name not in result and any(dep in result for dep in STEPS[name][0]):
                result.add(name)
                changed = True
    return result


def plan(state: dict, day: str, mode: str) -> list[str]:
    """Steps to run now, in workflow order."""
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode}")
    if mode == "commands":
        return []
    required = required_steps(day)
    if mode == "daily":
        return required
    steps = state.get("days", {}).get(day, {}).get("steps", {})
    pending = {name for name in required if steps.get(name, {}).get("status") != "success"}
    selected = dependents(pending, required)
    return [name for name in required if name in selected]


def day_record(state: dict, day: str) -> dict:
    return state.setdefault("days", {}).setdefault(day, {"runs": [], "steps": {}})


def start_run(state: dict, day: str, run_id: str, mode: str, event: str, planned: list[str],
              now: datetime, code_version: str, policy_hash: str) -> dict:
    day_record(state, day)["runs"].append({
        "run_id": run_id, "mode": mode, "event": event, "planned": planned,
        "started_at": now.isoformat(timespec="seconds"), "finished_at": None,
        "code_version": code_version, "policy_hash": policy_hash})
    return state


def record_step(state: dict, day: str, step: str, status: str, run_id: str, now: datetime,
                exit_code: int | None = None) -> dict:
    """status: started | success | failed. The latest attempt decides; last_success_at is kept."""
    if step not in STEPS:
        raise ValueError(f"unknown step {step}")
    steps = day_record(state, day)["steps"]
    previous = steps.get(step, {})
    entry = {"status": status, "run_id": run_id, "exit_code": exit_code,
             "last_success_at": previous.get("last_success_at")}
    stamp = now.isoformat(timespec="seconds")
    if status == "started":
        entry["started_at"], entry["finished_at"] = stamp, None
    else:
        entry["started_at"] = previous.get("started_at") if previous.get("run_id") == run_id else None
        entry["finished_at"] = stamp
        if status == "success":
            entry["last_success_at"] = stamp
    steps[step] = entry
    return state


def finish_run(state: dict, day: str, run_id: str, now: datetime) -> dict:
    for run in day_record(state, day)["runs"]:
        if run["run_id"] == run_id:
            run["finished_at"] = now.isoformat(timespec="seconds")
    return state


def complete(state: dict, day: str) -> bool:
    return plan(state, day, "auto") == []


def prune(state: dict, today: str) -> dict:
    cutoff = (date.fromisoformat(today) - timedelta(days=KEEP_DAYS)).isoformat()
    state["days"] = {d: v for d, v in state.get("days", {}).items() if d >= cutoff}
    return state


# ------------------------------------------------------------------------ CLI

def load() -> dict:
    return c.read_json(STATE_PATH, {"schema_version": 1, "days": {}})


def save(state: dict) -> None:
    c.atomic_json(STATE_PATH, state)


def env_name(step: str) -> str:
    return "RUN_" + step.upper()


def code_version() -> str:
    return (os.environ.get("GITHUB_SHA") or "local")[:12]


def policy_hash() -> str:
    path = c.ROOT / "config" / "research_policy.json"
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12] if path.exists() else "missing"


def cmd_plan(mode: str, event: str) -> int:
    now = datetime.now(timezone.utc)
    day = kst_day(now)
    state = prune(load(), day)
    steps = plan(state, day, mode)
    run_id = (f"{os.environ['GITHUB_RUN_ID']}-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}"
              if os.environ.get("GITHUB_RUN_ID") else f"local-{uuid.uuid4().hex[:8]}")
    if steps:  # A commands-only run leaves no daily run record.
        start_run(state, day, run_id, mode, event, steps, now, code_version(), policy_hash())
        save(state)
    for name in STEPS:
        print(f"{env_name(name)}={'true' if name in steps else 'false'}")
    print(f"DAILY_DAY={day}")
    print(f"DAILY_RUN_ID={run_id}")
    print(f"DAILY_STEPS={' '.join(steps) or 'none'}", file=sys.stderr)
    return 0


def cmd_step(step: str, command: list[str]) -> int:
    day, run_id = os.environ["DAILY_DAY"], os.environ["DAILY_RUN_ID"]
    save(record_step(load(), day, step, "started", run_id, datetime.now(timezone.utc)))
    code = subprocess.run(command, cwd=c.ROOT).returncode
    status = "success" if code == 0 else "failed"
    save(record_step(load(), day, step, status, run_id, datetime.now(timezone.utc), code))
    return code


def cmd_finish() -> int:
    day, run_id = os.environ.get("DAILY_DAY"), os.environ.get("DAILY_RUN_ID")
    if not day or not run_id:
        return 0
    state = load()
    if any(r["run_id"] == run_id for r in state.get("days", {}).get(day, {}).get("runs", [])):
        save(finish_run(state, day, run_id, datetime.now(timezone.utc)))
    print(f"[daily] {day} complete={complete(load(), day)}")
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
    p_step = sub.add_parser("step")
    p_step.add_argument("name", choices=list(STEPS))
    sub.add_parser("finish")
    args = parser.parse_args(argv)
    if args.action == "plan":
        return cmd_plan(args.mode, args.event)
    if args.action == "step":
        if not command:
            parser.error("step needs a command after --")
        return cmd_step(args.name, command)
    return cmd_finish()


if __name__ == "__main__":
    raise SystemExit(main())
