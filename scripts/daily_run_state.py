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
  recover   the six-hourly schedule (S0-B): only a same-day resume of an extract left partial or
            stopped by model unavailability, and the context draft resume, with the steps that
            use them; never without today's daily record, at most recover_max a day

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
DEFAULT_POLICY = {"partial_retry_max": 1, "partial_retry_min_gap_minutes": 60, "draft_resume_max": 2,
                  "recover_max": 2, "recover_min_gap_minutes": 60}


@dataclass(frozen=True)
class Step:
    requires: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ()
    weekday: int | None = None
    # A render step is redone when its generator version changes, without recollecting inputs.
    version: str | None = None
    # A partial result may get the generic 60-minute top-up; steps with their own retry rules opt out.
    partial_top_up: bool = True


# Order is the workflow order: collection/calculation -> baseline -> returns -> views -> weekly.
STEPS: dict[str, Step] = {
    "collect": Step(),
    # Never extracts from an older collection. A partial extract (S0-A) is retried by the
    # extract resume rule (S0-B), which knows the model waits; no generic top-up.
    "extract": Step(requires=("collect",), partial_top_up=False),
    "eps": Step(inputs=("@tracking",)),          # a newly tracked ticker is collected the same day
    "notify": Step(requires=("extract",)),     # tracked-company risk alerts; independent of cards
    "quarterly": Step(inputs=("@tracking",)),
    "screen": Step(),
    "prices": Step(inputs=("@tracking",)),
    # Official filings and drafts for the screen's candidates. It keeps its own limits and retry
    # times (24 h after failures, 7 days after 'nothing relevant'), so no generic partial top-up.
    "context": Step(inputs=("screen",), version="context-v11", partial_top_up=False),
    # Version tracks candidates.GENERATOR_VERSION: a new card generator redoes the cards.
    "cards": Step(inputs=("screen", "context", "@tracking", "@evidence", "@quarantine"), version="cards-v10"),
    # New-candidate alerts (news + screen, one daily budget). A failed cards step stops only these.
    "alerts": Step(requires=("cards",), inputs=("extract",)),
    # research_journal --capture-only reads research case files and metric_log; tracking changes
    # (/track) are not an input, so a new tracked ticker does not redo baselines or returns.
    "baseline": Step(inputs=("@cases",)),
    "returns": Step(inputs=("baseline",)),
    # Candidate prices for discovery outcomes (Q3): a budgeted daily share, separate from tracked returns.
    "candidate_prices": Step(),  # once a day; its queue picks up new screens and receipts the next day
    "views": Step(inputs=("extract", "eps", "quarterly", "screen", "prices", "cards", "alerts", "baseline", "returns",
                          "candidate_prices"), version="views-v4"),
    "community": Step(weekday=MONDAY),
    "weekly_report": Step(requires=("views",), weekday=MONDAY),
}
MODES = ("daily", "auto", "commands", "recover")
RESUMES = ("extract_resume", "draft_resume")  # reasons counted as same-day recoveries
# An interrupted recovery is continued under these reasons: no new slot, no new draft resume count.
CONTINUES = {"extract_resume": "extract_resume_continue", "draft_resume": "draft_resume_continue"}
DRAFTS_ONLY = ("draft_resume", "draft_resume_continue")
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


def file_bytes(path) -> bytes:
    """File content with line endings normalized: a Windows checkout (CRLF) and the CI
    runner (LF) must see the same revision of the same file."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def evidence_revision() -> str:
    path = c.DATA_DIR / "candidate_evidence.json"
    return hashlib.sha256(file_bytes(path)).hexdigest()[:16] if path.exists() else "none"


def quarantine_revision() -> str:
    """The withheld-draft list: a change redoes the cards (a missing file makes the cards step fail)."""
    path = c.ROOT / "config" / "context_quarantine.json"
    return hashlib.sha256(file_bytes(path)).hexdigest()[:16] if path.exists() else "none"


def cases_revision() -> str:
    directory = c.DATA_DIR.parent / "research" / "cases"
    digest = hashlib.sha256()
    for path in sorted(directory.glob("*.json")):
        digest.update(path.name.encode("utf-8") + file_bytes(path))
    return digest.hexdigest()[:16]


EXTERNAL = {"@tracking": tracking_revision, "@evidence": evidence_revision, "@cases": cases_revision,
            "@quarantine": quarantine_revision}


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


def retry_due(entry: dict, now: datetime, policy: dict, step: str = "screen") -> bool:
    """A partial result gets a limited top-up, spaced from the last attempt."""
    if not STEPS[step].partial_top_up:
        return False
    if entry.get("quality_status") != "partial" or not entry.get("finished_at"):
        return False
    if entry.get("auto_retries", 0) >= policy["partial_retry_max"]:
        return False
    gap = timedelta(minutes=policy["partial_retry_min_gap_minutes"])
    return datetime.fromisoformat(entry["finished_at"]) + gap <= now


def extract_model_stopped(entry: dict) -> bool:
    """A failed extract whose own run status says the model could not serve it (model_unavailable)."""
    if entry.get("execution_status") != "failed":
        return False
    status = c.read_json(c.DATA_DIR / "run_status.json", {}).get("extract", {})
    return bool(entry.get("run_id")) and status.get("run_id") == entry["run_id"] \
        and status.get("outcome") == "model_unavailable"


def extract_recoverable(entry: dict) -> bool:
    """An extract worth a same-day resume: partial (S0-A), or failed only because the model could
    not serve it. Other failures are not resumed here."""
    if entry.get("execution_status") == "success":
        return entry.get("quality_status") == "partial"
    return extract_model_stopped(entry)


def recovery_runs(record: dict) -> set[str]:
    """Run ids of the day's latest recovery and of the runs that continued it."""
    done = record.get("recoveries", [])
    return {done[-1]["run_id"], *done[-1].get("continued_by", [])} if done and done[-1].get("run_id") else set()


def recovery_room(record: dict, now: datetime, policy: dict) -> str | None:
    """None when another same-day recovery may start, else why not (daily limit or spacing)."""
    done = record.get("recoveries", [])
    if len(done) >= policy["recover_max"]:
        return f"recover_max {policy['recover_max']} used"
    gap = timedelta(minutes=policy["recover_min_gap_minutes"])
    if done and datetime.fromisoformat(done[-1]["started_at"]) + gap > now:
        return f"last recovery at {done[-1]['started_at']}"
    return None


def plan_detail(state: dict, day: str, mode: str, now: datetime | None = None,
                policy: dict | None = None, redo: set[str] | frozenset = frozenset(),
                draft_resume=None, extract_resume=None, notes: dict | None = None) -> dict[str, str]:
    """{step: why} for the steps to run now, in workflow order.

    redo (auto only) asks for named steps to run again today, with the steps that use them.
    extract_resume(now) and draft_resume(now) return a reason or None from stored waits and queues;
    notes, when given, receives why a resume was not planned (S0-B output).
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
    notes = {} if notes is None else notes
    if mode == "recover":
        return recover_detail(state, day, now, policy, required, draft_resume, extract_resume, notes)
    room = recovery_room(state.get("days", {}).get(day, {}), now, policy)
    why: dict[str, str] = {}
    for name in required:
        entry = steps.get(name, {})
        if name in redo:
            why[name] = "requested"
        elif name == "extract" and (extract_model_stopped(entry) or
                                    (entry.get("execution_status") == "success" and extract_recoverable(entry))):
            # Already tried today and stopped (or left partial) by the model: the same recovery
            # limits, spacing and waits as the six-hourly recovery (S0-B), counted the same way.
            if room is not None:
                notes["extract"] = room
            elif extract_resume is None or not extract_resume(now):
                notes["extract"] = "nothing to resume now"
            else:
                why[name] = "extract_resume"  # stored pending items only; no new collection
        elif entry.get("execution_status") != "success":
            why[name] = entry.get("execution_status") or "not_run"
        elif stale(steps, name):
            why[name] = "inputs_changed"
        elif retry_due(entry, now, policy, name):
            why[name] = "partial_retry"
        elif name == "context" and draft_resume is not None:
            if entry.get("draft_resumes", 0) >= policy["draft_resume_max"]:
                notes["context"] = "draft_resume_max used"
            elif room is not None:
                notes["context"] = room
            elif draft_resume(now):
                why[name] = "draft_resume"  # drafts only, from stored documents (Q2); no screen or SEC
    # A step recorded blocked runs again only when what blocks it runs again (else it is blocked again).
    for name in [n for n, reason in why.items() if reason == "blocked"]:
        dep = blocking(steps, name)
        if dep and dep[0] not in why:
            del why[name]
    for name in dependents(set(why), required) - set(why):
        why[name] = "dependency_rerun"
    return {name: why[name] for name in required if name in why}


def recover_detail(state: dict, day: str, now: datetime, policy: dict, required: list[str],
                   draft_resume, extract_resume, notes: dict) -> dict[str, str]:
    """The six-hourly schedule's limited plan (S0-B). Successful collection and screening are never
    rerun; a blocked step only runs as a user of a resumed step."""
    record = state.get("days", {}).get(day, {})
    if not record.get("runs"):
        notes["recover"] = "no daily run today"
        return {}
    steps = record.get("steps", {})
    runs = recovery_runs(record)
    unfinished = [name for name in required if steps.get(name, {}).get("planned_by") in runs
                  and steps[name].get("execution_status") in ("pending", "started")]
    if unfinished:
        return continue_recovery(steps, unfinished, now, required, draft_resume, extract_resume, notes)
    room = recovery_room(record, now, policy)
    if room:
        notes["recover"] = room
        return {}
    why: dict[str, str] = {}
    entry = steps.get("extract", {})
    if "extract" not in required or blocking(steps, "extract"):
        notes["extract"] = "collect not done today"
    elif not extract_recoverable(entry):
        notes["extract"] = f"not resumable ({entry.get('execution_status')}/{entry.get('quality_status')})"
    elif extract_resume is None or not extract_resume(now):
        notes["extract"] = "nothing to resume now"
    else:
        why["extract"] = "extract_resume"
    entry = steps.get("context", {})
    if "context" not in required or entry.get("execution_status") != "success":
        notes["context"] = "context not done today"
    elif entry.get("draft_resumes", 0) >= policy["draft_resume_max"]:
        notes["context"] = "draft_resume_max used"
    elif draft_resume is None or not draft_resume(now):
        notes["context"] = "no drafts to resume now"
    else:
        why["context"] = "draft_resume"
    for name in dependents(set(why), required) - set(why):
        why[name] = "dependency_rerun"
    return {name: why[name] for name in required if name in why}


def continue_recovery(steps: dict, unfinished: list[str], now: datetime, required: list[str],
                      draft_resume, extract_resume, notes: dict) -> dict[str, str]:
    """The steps a stopped recovery left pending/started, under the same day's slot (none consumed).
    Model steps check their waits again; a model step that must wait holds its users with it."""
    checks = {"extract": extract_resume, "context": draft_resume}
    held = set()
    for name in unfinished:
        if name in checks and (checks[name] is None or not checks[name](now)):
            held.add(name)
            notes[name] = "continuation waits"
    held = dependents(held, required) & set(unfinished) if held else set()
    why = {}
    for name in unfinished:
        if name in held:
            continue
        reason = steps[name].get("plan_reason")
        why[name] = CONTINUES.get(reason, "recovery_continue")
    for name in dependents(set(why), required) - set(why) - held:
        why[name] = "dependency_rerun"
    if not why:
        notes["recover"] = "interrupted recovery waits"
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
        if why == "draft_resume":
            entry["draft_resumes"] = entry.get("draft_resumes", 0) + 1
    # Stored with the plan, before any step runs: a restart never resets the day's count.
    resumed = [name for name, why in detail.items() if why in RESUMES]
    if resumed:
        record.setdefault("recoveries", []).append(
            {"run_id": run_id, "mode": mode, "started_at": stamp, "steps": resumed})
    elif record.get("recoveries") and any(why in CONTINUES.values() or why == "recovery_continue"
                                          for why in detail.values()):
        record["recoveries"][-1].setdefault("continued_by", []).append(run_id)  # same slot
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


def incomplete(state: dict, day: str) -> dict[str, str]:
    """Required steps whose latest execution did not succeed (failed/blocked/pending/started/not run).

    A partial result waiting for, or past, its top-up is a quality gap, not an execution failure.
    """
    steps = day_steps(state, day)
    return {name: steps.get(name, {}).get("execution_status") or "not_run" for name in required_steps(day)
            if steps.get(name, {}).get("execution_status") != "success"}


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


def context_quality(run_id: str) -> str:
    """partial when some documents could not be reached; waiting or budget stops are not failures."""
    status = c.read_json(c.DATA_DIR / "run_status.json", {}).get("candidate_context", {}).get("status")
    return {"success": "complete", "held": "unavailable", "degraded": "partial"}.get(status, "unknown")


def extract_quality(run_id: str) -> str:
    """complete only when this run's extract left nothing waiting; partial when items still wait
    (503 wait, budget, 429). A status written by another run is never read as this run's."""
    entry = c.read_json(c.DATA_DIR / "run_status.json", {}).get("extract", {})
    if not run_id or entry.get("run_id") != run_id:
        return "unknown"
    if entry.get("status") == "partial":
        return "partial"
    if entry.get("status") == "success":
        return "partial" if entry.get("pending") else "complete"
    return "unknown"


QUALITY_PROBES = {"screen": screen_quality, "context": context_quality, "extract": extract_quality}


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
    resume = extract_resume = None
    checks: dict[str, str] = {}
    if mode in ("auto", "recover"):
        def resume(at):
            # A broken or missing input file must never stop the daily plan: no resume then.
            try:
                import candidate_context
                return candidate_context.draft_resume_due(at)
            except Exception as error:  # noqa: BLE001
                print(f"[daily] draft resume check skipped: {type(error).__name__}", file=sys.stderr)
                return None

        def extract_resume(at):
            try:
                import extract
                why, note = extract.extract_resume_check(at)
            except Exception as error:  # noqa: BLE001
                why, note = None, f"check skipped: {type(error).__name__}"
            checks["extract_wait"] = note
            return why
    notes: dict[str, str] = {}
    detail = plan_detail(state, day, mode, now, run_policy(), names if mode == "auto" else frozenset(),
                         resume, extract_resume, notes)
    run_id = (f"{os.environ['GITHUB_RUN_ID']}-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}"
              if os.environ.get("GITHUB_RUN_ID") else f"local-{uuid.uuid4().hex[:8]}")
    if detail:  # A commands-only run leaves no daily run record.
        save(apply_plan(state, day, run_id, mode, event, detail, now, code_version(), policy_hash()))
    for name in STEPS:
        print(f"{env_name(name)}={'true' if name in detail else 'false'}")
    print(f"CONTEXT_DRAFTS_ONLY={'true' if detail.get('context') in DRAFTS_ONLY else 'false'}")
    print(f"DAILY_DAY={day}")
    print(f"DAILY_RUN_ID={run_id}")
    reasons = " ".join(f"{name}({why})" for name, why in detail.items()) or "none"
    print(f"DAILY_STEPS={reasons}", file=sys.stderr)
    if mode == "recover":
        done = len(state.get("days", {}).get(day, {}).get("recoveries", []))
        print(f"[recover] {day} planned={reasons} recoveries_today={done}/{run_policy().get('recover_max', DEFAULT_POLICY['recover_max'])} "
              f"waiting={ {**notes, **checks} or 'none'}", file=sys.stderr)
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
    unfinished = incomplete(state, day)
    print(f"[daily] {day} execution={'complete' if not unfinished else unfinished} "
          f"quality_gaps={quality_summary(state, day) or 'none'} "
          f"auto_plan_now={plan(state, day, 'auto', policy=run_policy()) or 'none'}")
    if os.environ.get("DAILY_MODE") == "commands":
        return 0  # a commands run never owes the daily steps
    if os.environ.get("DAILY_MODE") == "recover":
        # A recovery owes only what it planned; a failed or blocked planned step fails it.
        run = next((r for r in state.get("days", {}).get(day, {}).get("runs", []) if r["run_id"] == run_id), None)
        steps = day_steps(state, day)
        failed = [name for name in (run or {}).get("planned", [])
                  if steps.get(name, {}).get("execution_status") != "success"]
        print(f"[recover] {day} unfinished={failed or 'none'}")
        return 1 if failed else 0
    return 1 if unfinished else 0


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
