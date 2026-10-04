"""Offline evaluation of automatic drafts on fixed, verified inputs (M4). No network, no state writes.

    python scripts/draft_eval.py run --fixture data/eval/l4_2026-10-04 --lock data/eval/m_2026-10-04/fixture_lock.json \
        --expected data/eval/m_2026-10-04/expected.json --out data/eval/m_2026-10-04/results.json

- Inputs are checked before anything is produced: the archive, the manifest and every stage
  validator against a lock of byte hashes, and every record against its normalized-content hash,
  run, KST day, candidate, ticker and outcome. Counts, order and duplicates must match: nothing is
  dropped by zipping two lists of different length.
- Each answer item is scored on its own key (run, attempt, candidate, section, position, quote and
  figures hashes), so two items with the same quote but another metric or period are two items.
- Accuracy comes from a separately written expectation table (a person's reading of the source),
  never from the validator that accepted the item: an accepted item the table rejects, or a figure
  shown in a role the table does not allow, is a critical error; an item the table did not review is
  counted as unreviewed, not as correct. The table covers what was reviewed; it is a regression
  baseline, not a general accuracy figure.
"""
import argparse
import copy
import gzip
import hashlib
import importlib.util
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
CAPS = {"claims": 5, "limitations": 3}  # what validate_draft reads per section
RATE_TEXT = __import__("re").compile(r"%|percent|basis point|percentage point")


class IntegrityError(ValueError):
    """The fixed inputs are not the ones the lock describes."""


def canonical_sha(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def file_sha(path: pathlib.Path) -> str:
    """Line endings normalized: a Windows checkout (CRLF) and the CI runner (LF) hash one file alike."""
    return hashlib.sha256(pathlib.Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def kst_day(stamp: str) -> str:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(KST).date().isoformat()


def read_fixture(directory: pathlib.Path) -> tuple[list, list]:
    with gzip.open(directory / "audits.json.gz", "rt", encoding="utf-8") as handle:
        records = json.load(handle)
    return records, json.loads((directory / "manifest.json").read_text(encoding="utf-8"))


def row_of(record: dict) -> dict:
    return {"run_id": record.get("run_id"), "attempt_id": record.get("attempt_id"),
            "candidate_id": record.get("candidate_id"), "ticker": record.get("ticker"),
            "outcome": record.get("outcome"), "kst_day": kst_day(record["started_at"])}


def make_lock(directory: pathlib.Path) -> dict:
    """The lock written once from inputs that were checked by hand (L4: artifacts, manifest)."""
    directory = pathlib.Path(directory)
    records, manifest = read_fixture(directory)
    if len(records) != len(manifest):
        raise IntegrityError(f"{len(records)} records but {len(manifest)} manifest rows")
    rows = []
    for record, listed in zip(records, manifest):
        row = {**row_of(record), "file": listed["file"], "original_bytes_sha256": listed["sha256"],
               "record_sha256": canonical_sha(record)}
        if (row["run_id"], row["kst_day"], row["ticker"], row["outcome"]) != \
                (listed["run_id"], listed["kst_day"], listed["ticker"], listed["outcome"]):
            raise IntegrityError(f"manifest row does not describe record {row['attempt_id']}")
        rows.append(row)
    stages = sorted((directory / "stage_validators").glob("*.py"))
    return {"schema_version": 1, "audits_gz_sha256": file_sha(directory / "audits.json.gz"),
            "manifest_sha256": file_sha(directory / "manifest.json"), "records": rows,
            "stage_validators": {p.name: file_sha(p) for p in stages}}


def load_fixture(directory: pathlib.Path, lock: dict) -> list[dict]:
    """The records, only after every check passes; otherwise IntegrityError and nothing else."""
    directory = pathlib.Path(directory)
    problems = []
    if file_sha(directory / "audits.json.gz") != lock["audits_gz_sha256"]:
        problems.append("archive bytes changed")
    if file_sha(directory / "manifest.json") != lock["manifest_sha256"]:
        problems.append("manifest bytes changed")
    for name, sha in lock["stage_validators"].items():
        path = directory / "stage_validators" / name
        if not path.exists() or file_sha(path) != sha:
            problems.append(f"stage validator {name} changed")
    records, manifest = read_fixture(directory)
    if not len(records) == len(manifest) == len(lock["records"]):
        problems.append(f"counts differ: {len(records)} records, {len(manifest)} manifest rows, "
                        f"{len(lock['records'])} locked")
    attempts = [r.get("attempt_id") for r in records]
    if len(set(attempts)) != len(attempts):
        problems.append("duplicate attempt")
    for position, (record, listed, locked) in enumerate(zip(records, manifest, lock["records"])):
        row = row_of(record)
        if any(row[k] != locked[k] for k in row):
            problems.append(f"record {position} is not {locked['attempt_id']}")
        if canonical_sha(record) != locked["record_sha256"]:
            problems.append(f"record {position} content changed")
        if listed.get("sha256") != locked["original_bytes_sha256"] or listed.get("file") != locked["file"]:
            problems.append(f"manifest row {position} changed")
    if problems:
        raise IntegrityError("; ".join(problems[:5]) + (f" (+{len(problems) - 5})" if len(problems) > 5 else ""))
    return records


def sha(text) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()[:16]


def item_key(record: dict, section: str, position: int, item: dict) -> str:
    return "|".join([record["run_id"], record["attempt_id"], record["candidate_id"], section, str(position),
                     sha(item.get("quote")), sha(json.dumps(item.get("figures"), ensure_ascii=False))])


def load_validator(path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(f"draft_eval_{sha(path)}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_stage(validator, records: list[dict]) -> dict[str, dict]:
    """{item key: outcome} for every answer item; each item is checked on its own (check_item has no
    cross-item state), so an outcome always belongs to exactly one item."""
    outcomes = {}
    for record in records:
        answer = record.get("answer")
        if not isinstance(answer, dict):
            continue
        for section, cap in CAPS.items():
            for position, item in enumerate(answer.get(section) or []):
                if not isinstance(item, dict):
                    continue
                key = item_key(record, section, position, item)
                if position >= cap:
                    outcomes[key] = {"accepted": False, "reason": "over_cap"}
                    continue
                result = validator.validate_draft({section: [copy.deepcopy(item)], "link": "unconfirmed"},
                                                  record["blocks"], record["issuer"])
                if result[section]:
                    checked = result[section][0]
                    outcomes[key] = {"accepted": True, "metric": checked.get("metric"), "period": checked.get("period"),
                                     "subject": checked.get("subject"), "kind": checked.get("kind"),
                                     "roles": checked.get("figure_roles") or ["level"] * len(checked["figures"]),
                                     "text_ko": checked["text_ko"]}
                else:
                    outcomes[key] = {"accepted": False, "reason": result["rejected"][0]["reason"]
                                     if result["rejected"] else "dropped"}
    return outcomes


def score(outcomes: dict[str, dict], expected: list[dict]) -> dict:
    """Counts against the expectation table. A wrong acceptance or a role outside the allowed ones is
    critical; another field outside the table is a field mismatch; an item the table expects but
    the validator refused is an over-refusal; an accepted item not in the table is unreviewed."""
    table = {e["key"]: e for e in expected}
    result = {"critical": [], "field_mismatch": [], "over_refusal": [], "correct": 0, "unreviewed_accepted": [],
              "expected_items": len(table)}
    for key, entry in table.items():
        got = outcomes.get(key)
        if got is None:
            result["over_refusal"].append({"key": key, "reason": "item_missing"})
            continue
        if not entry["accept"]:
            if got["accepted"]:
                result["critical"].append({"key": key, "why": "accepted_but_should_be_refused",
                                           "text_ko": got["text_ko"]})
            else:
                result["correct"] += 1
            continue
        if not got["accepted"]:
            result["over_refusal"].append({"key": key, "reason": got["reason"]})
            continue
        allowed = entry["roles"]
        if len(got["roles"]) != len(allowed):
            result["critical"].append({"key": key, "why": "figure_count", "got": got["roles"], "allowed": allowed,
                                       "text_ko": got["text_ko"]})
            continue
        off = [i for i, (role, options) in enumerate(zip(got["roles"], allowed)) if role not in options]
        # An amount in the wrong role (a change or an effect read as a value) is critical; a rate change
        # shown without its change label is a display gap, counted apart.
        amounts = [i for i in off if not RATE_TEXT.search(str(entry["figures"][i]))]
        if amounts:
            result["critical"].append({"key": key, "why": "figure_role", "got": got["roles"], "allowed": allowed,
                                       "text_ko": got["text_ko"]})
            continue
        wrong = [f for f in ("metric", "period", "subject", "kind") if f in entry and entry[f] != got.get(f)]
        wrong += ["rate_label"] if off else []
        if wrong:
            result["field_mismatch"].append({"key": key, "fields": wrong, "text_ko": got["text_ko"]})
        else:
            result["correct"] += 1
    result["unreviewed_accepted"] = [k for k, v in outcomes.items() if v["accepted"] and k not in table]
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="action", required=True)
    lock = sub.add_parser("lock", help="write the lock for a fixture directory (once, after checking it by hand)")
    lock.add_argument("--fixture", required=True)
    lock.add_argument("--out", required=True)
    run = sub.add_parser("run")
    run.add_argument("--fixture", required=True)
    run.add_argument("--lock", required=True)
    run.add_argument("--expected", required=True)
    run.add_argument("--out", required=True)
    run.add_argument("--current", default=str(pathlib.Path(__file__).resolve().parent / "candidate_context.py"))
    args = parser.parse_args(argv)
    if args.action == "lock":
        pathlib.Path(args.out).write_text(json.dumps(make_lock(pathlib.Path(args.fixture)), ensure_ascii=False, indent=1),
                                          encoding="utf-8")
        return 0
    fixture = pathlib.Path(args.fixture)
    locked = json.loads(pathlib.Path(args.lock).read_text(encoding="utf-8"))
    records = load_fixture(fixture, locked)  # raises before any output
    expected = json.loads(pathlib.Path(args.expected).read_text(encoding="utf-8"))["items"]
    stages = {name.removesuffix(".py"): fixture / "stage_validators" / name for name in sorted(locked["stage_validators"])}
    stages["s5_current"] = pathlib.Path(args.current)
    report = {"inputs": {"records": len(records), "answered": sum(isinstance(r.get("answer"), dict) for r in records),
                         "failed": sum(not isinstance(r.get("answer"), dict) for r in records),
                         "lock_sha256": file_sha(pathlib.Path(args.lock)),
                         "expected_sha256": file_sha(pathlib.Path(args.expected)),
                         "current_validator_sha256": file_sha(stages["s5_current"])},
              "stages": {}}
    for name, path in stages.items():
        validator = load_validator(path)
        outcomes = run_stage(validator, records)
        scored = score(outcomes, expected)
        report["stages"][name] = {
            "parser_version": getattr(validator, "PARSER_VERSION", None),
            "accepted": sum(v["accepted"] for v in outcomes.values()),
            "critical": scored["critical"], "field_mismatch": scored["field_mismatch"],
            "over_refusal": scored["over_refusal"], "correct": scored["correct"],
            "expected_items": scored["expected_items"], "unreviewed_accepted": len(scored["unreviewed_accepted"]),
        }
        print(name, {k: (len(v) if isinstance(v, list) else v) for k, v in report["stages"][name].items()})
    pathlib.Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    raise SystemExit(main())
