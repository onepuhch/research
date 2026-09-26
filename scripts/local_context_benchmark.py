#!/usr/bin/env python3
"""J3: test a local Ollama model on stored official documents, apart from the pipeline.

    prepare  build the experiment from a fixed copy of the documents (no network)
    run      ask the local model, loopback only, and keep every raw answer (resumable)
    revalidate  re-check the kept answers with the current validator into a new folder (no network)
    report   score the kept answers against the review labels (no network)

The pipeline's pure functions (relevant_blocks, draft_prompt, validate_draft) are reused; nothing
that writes research state, cards, ledgers or messages is called, and no key or .env is read.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import http.client
import json
import os
import re
import socket
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import candidate_context as ctx  # noqa: E402
import company_filings as cf  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "reports" / "generated" / "local_model"
FORBIDDEN_OUT = ("data", "config", "templates", ".github", "scripts", "tests")
MAX_RESPONSE_BYTES = 512 * 1024
LOOPBACK = {"127.0.0.1", "::1", "localhost"}
OPTIONS = {"num_ctx": 16384, "num_predict": 3072, "temperature": 0, "seed": 42}
FAILURES = ("connection_refused", "timeout", "oom", "busy", "http_error", "bad_api_json", "truncated",
            "bad_json", "schema_error", "too_large")


def sha256(data: bytes | str) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


def canonical(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def safe_output(path: Path) -> Path:
    """Experiment output never lands in pipeline data, config or code."""
    path = Path(path).resolve()
    for name in FORBIDDEN_OUT:
        guarded = (ROOT / name).resolve()
        if path == guarded or guarded in path.parents:
            raise ValueError(f"output path not allowed: {path}")
    return path


def answer_schema() -> dict:
    """The structure draft_prompt asks for, as an Ollama `format` schema (shape only, not truth)."""
    text = {"type": "string"}
    claim = {"type": "object", "properties": {
        "kind": {"type": "string", "enum": list(ctx.KINDS)},
        "subject": {"type": "string", "enum": list(ctx.SUBJECTS)},
        "subject_name": text, "metric": text, "figures": {"type": "array", "items": text},
        "period": text, "gaap": {"type": "string", "enum": ["GAAP", "non-GAAP", "unknown"]},
        "note_ko": text, "quote": text, "document_id": text, "block_id": text,
        "drivers": {"type": "array", "items": {"type": "string", "enum": list(ctx.DRIVERS)}},
        "direction": {"type": "string", "enum": list(ctx.DIRECTIONS)}},
        "required": ["kind", "subject", "metric", "figures", "period", "gaap", "note_ko", "quote",
                     "document_id", "block_id", "drivers", "direction"]}
    limitation = {"type": "object", "properties": {
        "subject": {"type": "string", "enum": list(ctx.SUBJECTS)}, "metric": text,
        "figures": {"type": "array", "items": text}, "period": text, "note_ko": text, "quote": text,
        "document_id": text, "block_id": text},
        "required": ["note_ko", "quote", "document_id", "block_id"]}
    return {"type": "object", "properties": {
        "claims": {"type": "array", "items": claim, "maxItems": 5},
        "limitations": {"type": "array", "items": limitation, "maxItems": 3},
        "next_check": {"type": "array", "items": text, "maxItems": 2},
        "link": {"type": "string", "enum": list(ctx.LINKS)}},
        "required": ["claims", "limitations", "next_check", "link"]}


SCHEMA_TYPES = {"object": dict, "array": list, "string": str}


def schema_errors(value, schema: dict, path: str = "$") -> list[str]:
    """Every place the parsed answer breaks answer_schema: type, enum, required field, maxItems
    (no content check). JSON syntax is a separate question, answered before this."""
    kind = schema.get("type")
    if kind and not isinstance(value, SCHEMA_TYPES[kind]):
        return [f"{path}:type"]
    if "enum" in schema and value not in schema["enum"]:
        return [f"{path}:enum"]
    errors = []
    if kind == "object":
        errors += [f"{path}.{k}:required" for k in schema.get("required", []) if k not in value]
        for key, sub in schema.get("properties", {}).items():
            if key in value:
                errors += schema_errors(value[key], sub, f"{path}.{key}")
    if kind == "array":
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}:maxItems")
        for i, item in enumerate(value):
            errors += schema_errors(item, schema.get("items", {}), f"{path}[{i}]")
    return errors


def schema_problem(answer) -> str | None:
    errors = schema_errors(answer, answer_schema())
    return errors[0] if errors else None


# ------------------------------------------------------------------ prepare (no network)

def load_snapshot_document(source: Path, document_id: str) -> dict | None:
    path = Path(source) / "company_documents" / f"{document_id}.json.gz"
    if not path.exists():
        return None
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, EOFError, ValueError):
        return {"unreadable": True}


def prepare(source: Path, manifest_path: Path, output: Path | None) -> Path:
    manifest = read_json(manifest_path)
    manifest_sha = sha256(Path(manifest_path).read_bytes())
    experiment_id = f"j3-{manifest_sha[:10]}-{ctx.PARSER_VERSION}"
    out = safe_output(output or DEFAULT_OUT / experiment_id)
    docs, missing = {}, {}
    for entry in manifest["documents"]:
        doc = load_snapshot_document(source, entry["document_id"])
        file = Path(source) / "company_documents" / f"{entry['document_id']}.json.gz"
        problem = None
        if doc is None:
            problem = "file_missing"
        elif sha256(file.read_bytes()) != entry["file_sha256"]:  # checked before the content is trusted
            problem = "file_hash_mismatch"
        elif doc.get("raw_sha256") != entry["raw_sha256"]:
            problem = "raw_hash_mismatch"
        elif sha256(canonical(doc["blocks"])) != entry["blocks_sha256"]:
            problem = "blocks_hash_mismatch"
        if problem:
            missing[entry["document_id"]] = problem  # dataset_missing: never fetched again from SEC
        else:
            docs[entry["document_id"]] = (entry, doc)
    schema = answer_schema()
    cases = []
    for case in manifest["cases"]:
        record = {**case}
        if case["document_id"] in missing:
            record.update(status="dataset_missing", reason=missing[case["document_id"]])
        else:
            entry, doc = docs[case["document_id"]]
            if case["blocks"] == "relevant_blocks":
                blocks, coverage = ctx.relevant_blocks([doc])
            else:
                by_id = {b["id"]: b for b in doc["blocks"]}
                blocks = [{"document_id": doc["document_id"], "block_id": b, "text": cf.block_text(by_id[b])}
                          for b in case["blocks"]]
                coverage = "narrow"
            target = {"candidate_id": entry["candidate_id"], "ticker": entry["ticker"],
                      "eps_target_period": entry["eps_target_period"], "issuer_name": entry["issuer_name"]}
            prompt = ctx.draft_prompt(target, [doc], blocks)
            record.update(status="ready", target=target, blocks=blocks, source_coverage=coverage,
                          issuer={"ticker": entry["ticker"], "name": entry["issuer_name"]},
                          prompt=prompt, prompt_sha256=sha256(prompt))
            record["input_sha256"] = sha256(canonical({"blocks": blocks, "prompt": prompt, "target": target}))
        write_json(out / "cases" / f"{case['case_id']}.json", record)
        cases.append({k: record.get(k) for k in ("case_id", "group", "split", "status", "input_sha256")})
    experiment = {"experiment_id": experiment_id, "prepared_at": now(), "manifest_sha256": manifest_sha,
                  "source": str(Path(source).resolve()), "parser_version": ctx.PARSER_VERSION,
                  "prompt_version": ctx.PROMPT_VERSION, "schema": schema, "schema_sha256": sha256(canonical(schema)),
                  "stability_cases": manifest.get("stability_cases", []), "limits": manifest.get("limits", {}),
                  "cases": cases, "dataset_missing": missing}
    write_json(out / "experiment.json", experiment)
    return out


# ------------------------------------------------------------------ run (loopback only)

class Loopback:
    """A plain HTTP client for a loopback Ollama: no proxy, no redirect, no remote host."""

    def __init__(self, endpoint: str):
        parts = urlsplit(endpoint)
        if parts.scheme != "http" or parts.hostname not in LOOPBACK or parts.path not in ("", "/"):
            raise ValueError(f"only a loopback http endpoint is allowed: {endpoint}")
        self.host = "127.0.0.1" if parts.hostname == "localhost" else parts.hostname
        self.port = parts.port or 11434

    def request(self, method: str, path: str, body: dict | None = None, timeout: float = 30) -> tuple[int, bytes]:
        conn = http.client.HTTPConnection(self.host, self.port, timeout=timeout)
        try:
            data = json.dumps(body).encode("utf-8") if body is not None else None
            conn.request(method, path, body=data, headers={"Content-Type": "application/json"})
            response = conn.getresponse()
            if 300 <= response.status < 400:
                raise ValueError("redirect refused")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            return response.status, raw
        finally:
            conn.close()


def gpu_memory_mib() -> int | None:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5)
        return int(out.stdout.strip().splitlines()[0])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


class PeakGpu:
    """Polls GPU memory during one request; None when it cannot be measured."""

    def __init__(self, interval: float = 0.5, probe=gpu_memory_mib):
        self.interval, self.probe, self.values = interval, probe, []
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True)

    def loop(self):
        while not self.stop.is_set():
            value = self.probe()
            if value is not None:
                self.values.append(value)
            self.stop.wait(self.interval)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join(timeout=2)

    @property
    def peak(self):
        return max(self.values) if self.values else None


def model_info(client: Loopback, model: str) -> dict:
    """Server version, full digest and quantization: the tag name alone is not reproducible."""
    info = {"model": model}
    status, raw = client.request("GET", "/api/version")
    info["ollama_version"] = json.loads(raw).get("version") if status == 200 else None
    status, raw = client.request("GET", "/api/tags")
    for entry in (json.loads(raw).get("models") if status == 200 else []) or []:
        if entry.get("name") == model or entry.get("model") == model:
            info.update(digest=entry.get("digest"), size=entry.get("size"), details=entry.get("details"))
    if not info.get("digest"):
        raise ValueError(f"model not installed locally: {model}")
    return info


def classify(status: int | None, raw: bytes, error: Exception | None) -> tuple[str | None, dict | None]:
    """(failure kind or None, API body)."""
    if error is not None:
        if isinstance(error, ConnectionRefusedError):
            return "connection_refused", None
        if isinstance(error, (socket.timeout, TimeoutError)):
            return "timeout", None
        return "http_error", None
    if len(raw) > MAX_RESPONSE_BYTES:
        return "too_large", None
    text = raw.decode("utf-8", "replace").lower()
    if status != 200:
        if "out of memory" in text or "cuda error" in text or "cudamalloc" in text:
            return "oom", None
        return ("busy" if status == 503 else "http_error"), None
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        return "bad_api_json", None
    if body.get("done_reason") == "length" or not body.get("done", True):
        return "truncated", body
    return None, body


def result_key(case: dict, info: dict, options: dict, schema_sha: str) -> str:
    """The inference key: what the model saw and how it was asked. The validator is not part of it,
    so a new validator re-checks kept answers (revalidate) instead of asking the model again."""
    return sha256(canonical({"input": case["input_sha256"], "prompt": case["prompt_sha256"], "digest": info["digest"],
                             "options": options, "schema": schema_sha}))


def legacy_key(case: dict, info: dict, options: dict, schema_sha: str, parser: str | None) -> str:
    """J3 records keyed the inference together with the validator of the day."""
    return sha256(canonical({"input": case["input_sha256"], "prompt": case["prompt_sha256"], "digest": info["digest"],
                             "options": options, "schema": schema_sha, "parser": parser}))


def ledger(experiment: Path) -> list[dict]:
    path = experiment / "requests.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_case(client: Loopback, case: dict, model: str, options: dict, schema: dict, timeout: float) -> dict:
    body = {"model": model, "messages": [{"role": "user", "content": case["prompt"]}], "stream": False,
            "think": False, "format": schema, "options": options, "keep_alive": "10m"}
    started, status, raw, error = time.monotonic(), None, b"", None
    with PeakGpu() as gpu:
        try:
            status, raw = client.request("POST", "/api/chat", body, timeout=timeout)
        except (OSError, http.client.HTTPException, ValueError) as exc:
            error = exc
    elapsed = time.monotonic() - started
    failure, api = classify(status, raw, error)
    result = {"failure": failure, "http_status": status, "error_type": type(error).__name__ if error else None,
              "elapsed_s": round(elapsed, 3), "gpu_peak_mib": gpu.peak, "raw_api_bytes": len(raw),
              "raw_api_sha256": sha256(raw) if raw else None,
              "raw_api": raw[:MAX_RESPONSE_BYTES].decode("utf-8", "replace") if raw else None}
    if api is not None:
        message = (api.get("message") or {}).get("content", "")
        result["raw_content"] = message
        result["stats"] = {k: api.get(k) for k in ("done_reason", "total_duration", "load_duration", "prompt_eval_count",
                                                   "prompt_eval_duration", "eval_count", "eval_duration")}
    if failure is None:
        try:
            answer = json.loads(result["raw_content"])  # never repaired
        except (json.JSONDecodeError, TypeError):
            result["failure"] = "bad_json"
            return result
        result["answer"] = answer
        result["schema_errors"] = schema_errors(answer, answer_schema())
        if not isinstance(answer, dict):
            result["failure"] = "schema_error"
            return result
        result["validation"] = ctx.validate_draft(json.loads(json.dumps(answer)), case["blocks"], case["issuer"])
    return result


def unload(client: Loopback, model: str) -> None:
    """After a timeout, stop any work the server still holds instead of queueing behind it."""
    try:
        client.request("POST", "/api/generate", {"model": model, "keep_alive": 0}, timeout=30)
    except (OSError, http.client.HTTPException, ValueError):
        pass


def run(experiment: Path, model: str, endpoint: str, label: str, cases: list[str] | None, resume: bool,
        timeout: float = 120, max_requests: int | None = None, max_seconds: float | None = None,
        options: dict | None = None, client: Loopback | None = None) -> dict:
    experiment = safe_output(experiment)
    meta = read_json(experiment / "experiment.json")
    limits = meta.get("limits", {})
    max_requests = max_requests if max_requests is not None else limits.get("max_requests", 26)
    max_seconds = max_seconds if max_seconds is not None else limits.get("total_inference_s", 2700)
    options = {**OPTIONS, **(options or {})}
    client = client or Loopback(endpoint)
    info = model_info(client, model)
    write_json(experiment / "runs" / label / "environment.json",
               {**info, "options": options, "timeout_s": timeout, "recorded_at": now(),
                "gpu_before_mib": gpu_memory_mib(), "endpoint": f"http://{client.host}:{client.port}"})
    wanted = cases or [c["case_id"] for c in meta["cases"]]
    summary = {"ran": 0, "skipped": 0, "failed": 0, "stopped": None}
    for case_id in wanted:
        case = read_json(experiment / "cases" / f"{case_id}.json")
        path = experiment / "runs" / label / f"{case_id}.json"
        if case["status"] != "ready":
            write_json(path, {"case_id": case_id, "status": case["status"], "reason": case.get("reason")})
            continue
        key = result_key(case, info, options, meta["schema_sha256"])
        if path.exists():
            # A kept answer is never overwritten: the same inference is skipped, another setting
            # under the same label is refused and needs a new label.
            old = read_json(path)
            same = old.get("inference_key") == key or old.get("key") == legacy_key(
                case, info, options, meta["schema_sha256"], old.get("parser_version"))
            if same:
                summary["skipped"] += 1
            else:
                summary.setdefault("kept_other_setting", []).append(case_id)
            continue
        done = ledger(experiment)
        if len(done) >= max_requests:
            summary["stopped"] = "max_requests"
            break
        if sum(x.get("elapsed_s", 0) for x in done) >= max_seconds:
            summary["stopped"] = "max_seconds"
            break
        result = run_case(client, case, model, options, meta["schema"], timeout)
        record = {"case_id": case_id, "label": label, "inference_key": key, "model": model, "digest": info["digest"],
                  "options": options, "parser_version": ctx.PARSER_VERSION, "input_sha256": case["input_sha256"],
                  "prompt_sha256": case["prompt_sha256"], "finished_at": now(), **result}
        write_json(path, record)
        with (experiment / "requests.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"case_id": case_id, "label": label, "failure": result["failure"],
                                     "elapsed_s": result["elapsed_s"], "at": record["finished_at"]}) + "\n")
        summary["ran"] += 1
        summary["failed"] += bool(result["failure"])
        if result["failure"] in ("timeout", "oom"):
            unload(client, model)
    return summary


# ------------------------------------------------------------------ revalidate (no network)

SCORING_VERSION = "j3-score-v2"


def revalidate(experiment: Path, labels: tuple[str, ...] = ("final", "stability")) -> Path:
    """Re-check the kept answers with the current validator, without asking any model. Results go
    to revalidated/<validator>/<label>/, never over runs/; a version already written is kept."""
    experiment = Path(experiment)
    root = safe_output(experiment / "revalidated" / ctx.PARSER_VERSION)
    written = kept = 0
    for label in labels:
        source = experiment / "runs" / label
        if not source.is_dir():
            continue
        for path in sorted(source.glob("*.json")):
            out = root / label / path.name
            if out.exists():
                kept += 1
                continue
            record = read_json(path)
            if path.name == "environment.json":
                write_json(out, record)
                continue
            new = {**record, "revalidation": {
                "kind": "기존 표본에 대한 회귀 재검증", "validator": ctx.PARSER_VERSION,
                "validator_at_run": record.get("parser_version"), "scoring_version": SCORING_VERSION,
                "source": f"runs/{label}/{path.name}", "source_sha256": sha256(path.read_bytes()), "at": now()}}
            if isinstance(record.get("answer"), dict) and record.get("failure") in (None, "schema_error"):
                case = read_json(experiment / "cases" / path.name)
                new["validation_at_run"] = record.get("validation")
                new["validation"] = ctx.validate_draft(json.loads(json.dumps(record["answer"])), case["blocks"],
                                                       case["issuer"])
            write_json(out, new)
            written += 1
    write_json(root / "revalidation.json", {"validator": ctx.PARSER_VERSION, "labels": list(labels),
                                            "written": written, "kept": kept, "at": now(),
                                            "note": "no model or network request; answers are the stored ones"})
    return root


# ------------------------------------------------------------------ report (no network)

def norm(text) -> str:
    return " ".join(str(text or "").replace("–", "-").replace("—", "-").split()).casefold()


def metric_hit(metric: str, rule: dict) -> bool:
    m = norm(metric)
    return (any(norm(t) in m for t in rule.get("metric_terms", []))
            and not any(norm(t) in m for t in rule.get("exclude_terms", [])))


def figure_hit(figures, wanted) -> bool:
    got = {norm(f) for f in figures or [] if isinstance(f, str)}
    return bool(got & {norm(f) for f in wanted})


def label_check(claim: dict, facts: list[dict]) -> tuple[dict | None, list[str], bool]:
    """(fact, wrong attributes, fully labelled). A claim is about a label fact when its metric and
    one figure match; it is correct only if every labelled attribute matches too. A figure the
    label does not hold leaves the claim unreviewed, never correct."""
    for fact in facts:
        if not (metric_hit(claim.get("metric") or "", fact) and figure_hit(claim.get("figures"), fact["figures"])):
            continue
        wrong = []
        if fact.get("subject") and (claim.get("subject") or "issuer") != fact["subject"]:
            wrong.append("subject")
        if fact.get("period") and norm(fact["period"]) not in norm(claim.get("period")):
            wrong.append("period")
        if fact.get("kind") and (claim.get("kind") or "fact") != fact["kind"]:
            wrong.append("kind")
        if fact.get("gaap") and (claim.get("gaap") or "unknown") not in ("unknown", fact["gaap"]):
            wrong.append("gaap")
        if fact.get("direction") and claim.get("direction") not in (None, "unknown", fact["direction"]):
            wrong.append("direction")
        labelled = {norm(f) for f in fact["figures"]}
        complete = all(isinstance(f, str) and norm(f) in labelled for f in claim.get("figures") or [])
        return fact, wrong, complete
    return None, [], False


def mentioned(claim: dict, fact: dict) -> bool:
    """Loose: the metric and one figure appear together (a mention rate, not a correct recall)."""
    return metric_hit(claim.get("metric") or "", fact) and figure_hit(claim.get("figures"), fact["figures"])


def critical_hits(claim: dict, rules: list[dict]) -> list[str]:
    hits = []
    for rule in rules:
        if rule.get("subject_rule"):
            if (claim.get("subject") or "issuer") == "issuer" and figure_hit(claim.get("figures"), rule["figures"]):
                hits.append(rule["id"])
            continue
        if not (metric_hit(claim.get("metric") or "", rule) and figure_hit(claim.get("figures"), rule["figures"])):
            continue
        if rule.get("period_terms") and not any(norm(t) in norm(claim.get("period")) for t in rule["period_terms"]):
            continue
        if rule.get("direction") and claim.get("direction") != rule["direction"]:
            continue
        hits.append(rule["id"])
    return hits


def claim_key(item: dict) -> str:
    figures = item.get("figures") if isinstance(item.get("figures"), list) else []
    return f"{item.get('block_id')}|{str(item.get('metric') or '').strip()}|{'/'.join(str(f) for f in figures)}"


def manual_verdicts(raw: dict) -> dict:
    """{case: {key: {verdict, severity, reason, evidence, reviewed_at}}}; a bare 'correct'/'wrong'
    string (the J3 form) keeps severity unset."""
    out = {}
    for case_id, entries in (raw or {}).items():
        if case_id.startswith("_") or not isinstance(entries, dict):
            continue
        out[case_id] = {}
        for key, value in entries.items():
            if isinstance(value, str):
                value = {"verdict": value}
            if isinstance(value, dict) and value.get("verdict") in ("correct", "wrong"):
                out[case_id][key] = {k: value.get(k) for k in ("verdict", "severity", "reason", "evidence",
                                                               "reviewed_at")}
    return out


def block_ids(case: dict) -> set[str]:
    return {b["block_id"] for b in case.get("blocks") or []}


def critical_of(item: dict, company: dict, facts: list[dict], manual: dict) -> list[str]:
    """Every reason one claim is a critical error: label rules, a GAAP label against the source,
    and a hand verdict marked critical. One claim is one error however many reasons it has."""
    hits = critical_hits(item, company["critical"])
    fact, wrong, _ = label_check(item, facts)
    if fact and "gaap" in wrong:
        hits.append(f"gaap_mislabel:{fact['id']}")
    verdict = manual.get(claim_key(item))
    if verdict and verdict["verdict"] == "wrong" and verdict.get("severity") == "critical":
        hits.append(f"manual:{verdict.get('reason') or 'critical'}")
    return hits


def row_base(case: dict, labels: dict) -> dict:
    company = labels["companies"].get(case.get("ticker"), {})
    return {"case_id": case["case_id"], "group": case.get("group"), "split": case.get("split"),
            "ticker": case.get("ticker"), "sufficient_evidence": company.get("sufficient_evidence", True)}


def score_case(case: dict, result: dict, labels: dict, manual: dict) -> dict:
    company = labels["companies"][case["ticker"]]
    manual = manual.get(case["case_id"], {})
    visible = block_ids(case)
    facts = list(company["facts"])
    important = [f for f in facts if f.get("important")]
    shown = [f for f in important if f["block"] in visible]
    counters = [x for x in company["counter"] if x["block"] in visible]
    answer = result.get("answer") if isinstance(result.get("answer"), dict) else None
    out = {**row_base(case, labels), "failure": result.get("failure"), "elapsed_s": result.get("elapsed_s"),
           "validator": (result.get("revalidation") or {}).get("validator") or result.get("parser_version"),
           "json_ok": answer is not None, "schema_errors": schema_errors(answer, answer_schema()) if answer else None,
           "important_in_input": len(shown), "important_not_in_input": len(important) - len(shown),
           "counter_in_input": len(counters)}
    if result.get("failure") or "validation" not in result:
        return {**out, "claims": 0, "accepted": 0, "correct": 0, "wrong_accepted": [], "unreviewed": [],
                "critical_accepted": [], "critical_emitted": [], "critical_rejected": 0, "recall_model": 0,
                "recall_accepted": 0, "mention_model": 0, "counter_model": 0, "counter_accepted": 0,
                "core_draft": False, "status": None}
    checked = result["validation"]
    emitted = [x for x in answer.get("claims") or [] if isinstance(x, dict)]
    accepted = checked.get("claims") or []
    correct, wrong, unreviewed, crit_acc = 0, [], [], []
    for item in accepted:
        key = claim_key(item)
        hits = critical_of(item, company, facts, manual)
        fact, wrong_fields, complete = label_check(item, facts)
        verdict = manual.get(key)
        if hits:
            crit_acc.append({"key": key, "rules": hits})
            wrong.append({"key": key, "why": hits})
        elif verdict:
            if verdict["verdict"] == "wrong":
                wrong.append({"key": key, "why": [f"manual:{verdict.get('reason') or 'wrong'}"]})
            else:
                correct += 1
        elif fact and wrong_fields:
            wrong.append({"key": key, "why": [f"label:{fact['id']}:{'/'.join(wrong_fields)}"]})
        elif fact and complete:
            correct += 1
        else:
            unreviewed.append(key)
    crit_emit = [{"key": claim_key(x), "rules": r} for x in emitted
                 if (r := critical_of(x, company, facts, manual))]
    accepted_keys = {x["key"] for x in crit_acc}
    crit_rejected = len({x["key"] for x in crit_emit} - accepted_keys)

    def recalled(items):
        return {f["id"] for f in shown for item in items
                if (m := label_check(item, [f]))[0] and not m[1] and m[2]}

    def counter_found(items):
        quotes = " ".join(norm(x.get("quote")) for x in items if isinstance(x, dict))
        return {x["id"] for x in counters if any(norm(a) in quotes for a in x["anchors"])}

    kept_limits = checked.get("limitations") or []
    return {**out, "claims": len(emitted), "accepted": len(accepted), "correct": correct, "wrong_accepted": wrong,
            "unreviewed": unreviewed, "critical_accepted": crit_acc, "critical_emitted": crit_emit,
            "critical_rejected": crit_rejected, "recall_model": len(recalled(emitted)),
            "recall_accepted": len(recalled(accepted)),
            "mention_model": len({f["id"] for f in shown for item in emitted if mentioned(item, f)}),
            "counter_model": len(counter_found((answer.get("limitations") or []) + emitted)),
            "counter_accepted": len(counter_found(kept_limits + accepted)),
            "core_draft": checked.get("context_status") == "draft_ready", "status": checked.get("context_status")}


def pct(n, d):
    return None if not d else round(100 * n / d, 1)


def percentile(values, q):
    if not values:
        return None
    values = sorted(values)
    return values[min(len(values) - 1, max(0, int(round(q * (len(values) - 1)))))]


def report(experiment: Path, labels_path: Path, output: Path, label: str = "final",
           stability_label: str = "stability", runs_root: Path | None = None) -> dict:
    """Scores the kept answers; runs_root=<experiment>/revalidated/<validator> scores a revalidation.
    Never asks a model: a new validator is applied only by the separate revalidate step."""
    experiment = Path(experiment)
    runs_root = Path(runs_root) if runs_root else experiment / "runs"
    labels = read_json(labels_path)
    manual_path = experiment / "manual_review.json"
    manual = manual_verdicts(read_json(manual_path) if manual_path.exists() else {})
    meta = read_json(experiment / "experiment.json")
    rows = []
    for entry in meta["cases"]:
        path = runs_root / label / f"{entry['case_id']}.json"
        case = read_json(experiment / "cases" / f"{entry['case_id']}.json")
        if case["status"] != "ready":
            rows.append({**row_base(case, labels), "failure": case["status"]})  # split/group kept
            continue
        if not path.exists():
            rows.append({**row_base(case, labels), "failure": "not_run"})
            continue
        rows.append(score_case(case, read_json(path), labels, manual))
    summary = summarize(rows)
    stability = []
    for case_id in meta.get("stability_cases", []):
        first, again = (runs_root / x / f"{case_id}.json" for x in (label, stability_label))
        if first.exists() and again.exists():
            a, b = read_json(first), read_json(again)
            case = read_json(experiment / "cases" / f"{case_id}.json")
            scored = score_case(case, b, labels, manual)
            stability.append({"case_id": case_id, "same_content": a.get("raw_content") == b.get("raw_content"),
                              "critical_accepted": scored.get("critical_accepted", []),
                              "failure": b.get("failure")})
    env_path = runs_root / label / "environment.json"
    try:
        runs_name = str(runs_root.relative_to(experiment))
    except ValueError:
        runs_name = str(runs_root)
    result = {"scoring_version": SCORING_VERSION, "runs": runs_name,
              "validators": sorted({r.get("validator") for r in rows if r.get("validator")}),
              "summary": summary, "rows": rows, "stability": stability,
              "environment": read_json(env_path) if env_path.exists() else None}
    output = safe_output(output)
    write_json(output.with_suffix(".json"), result)
    output.with_suffix(".md").write_text(render(result), encoding="utf-8")
    return result


def render(result: dict) -> str:
    """Tables for the evaluation document (machine checks and hand review kept apart)."""
    lines = [f"채점 {result['scoring_version']}, 응답 {result['runs']}, 검증기 {', '.join(result['validators'])}", "",
             "| 구분 | 사례 | 실행 | 미실행/자료없음 | JSON | 스키마 | 모델 주장 | 기계 수용 | 원문 대조 정답 | "
             "수용됐지만 틀림 | 미검토 | 중대 오류 수용(주장) | 중대 오류 생성/그중 거부(주장) | 핵심 초안/가능 | "
             "근거 부족 보류 | 중요 사실 회수(모델/수용) | 언급률(참고) | 반대 근거(생성/표시) | 빈 답 | 중앙값/p95 초 |",
             "|" + "---|" * 20]
    for name in ("eval", "eval_A", "eval_B", "dev", "all"):
        s = result["summary"][name]
        lines.append(
            f"| {name} | {s['cases']} | {s['ran']} | {s['not_run']} | {s['json_ok']} ({s['json_rate']}%) | "
            f"{s['schema_ok']} | {s['claims']} | {s['accepted']} | {s['correct']} ({s['accepted_accuracy']}%, 검토 "
            f"{s['reviewed']}/{s['accepted']}) | {s['wrong_accepted']} | {s['unreviewed']} | {s['critical_accepted']} | "
            f"{s['critical_emitted']}/{s['critical_rejected']} | {s['core_draft']}/{s['core_draft_possible']} | "
            f"{s['insufficient_withheld']}/{s['insufficient_cases']} | {s['recall_model']}% / {s['recall_accepted']}% "
            f"(입력 {s['important_in_input']}, 입력 밖 {s['important_not_in_input']}) | {s['mention_model']}% | "
            f"{s['counter_model']}% / {s['counter_accepted']}% | {s['empty_answers']} | "
            f"{s['elapsed_median_s']} / {s['elapsed_p95_s']} |")
    lines += ["", "| 사례 | 구분 | 실패 | 초 | 주장 | 수용 | 정답 | 틀림 | 중대(수용) | 중대(생성) | 상태 |",
              "|" + "---|" * 11]
    for r in result["rows"]:
        lines.append(f"| {r['case_id']} | {r.get('split')}/{r.get('group')} | {r.get('failure') or '-'} | "
                     f"{r.get('elapsed_s')} | {r.get('claims', '-')} | {r.get('accepted', '-')} | {r.get('correct', '-')} | "
                     f"{'; '.join(x['key'] + ' ' + '/'.join(x['why']) for x in r.get('wrong_accepted') or []) or '-'} | "
                     f"{'; '.join(x['key'] + ' ' + '/'.join(x['rules']) for x in r.get('critical_accepted') or []) or '-'} | "
                     f"{len(r.get('critical_emitted') or [])} | {r.get('status') or '-'} |")
    return "\n".join(lines) + "\n"


def summarize(rows: list[dict]) -> dict:
    """Failures and cases not run stay in their group's denominators: a rate is over all cases
    that were meant to run (core drafts over every case with enough evidence)."""
    groups = {}
    for name, keep in (("all", lambda r: True), ("eval", lambda r: r.get("split") == "eval"),
                       ("dev", lambda r: r.get("split") == "dev"), ("A", lambda r: r.get("group") == "A"),
                       ("B", lambda r: r.get("group") == "B"),
                       ("eval_A", lambda r: r.get("split") == "eval" and r.get("group") == "A"),
                       ("eval_B", lambda r: r.get("split") == "eval" and r.get("group") == "B")):
        part = [r for r in rows if keep(r)]
        ran = [r for r in part if r.get("failure") not in ("dataset_missing", "not_run")]
        ok = [r for r in ran if not r.get("failure")]
        accepted = sum(r.get("accepted", 0) for r in ok)
        reviewed = sum(r.get("correct", 0) + len(r.get("wrong_accepted", [])) for r in ok)
        possible = [r for r in part if r.get("sufficient_evidence")]
        insufficient = [r for r in part if not r.get("sufficient_evidence")]
        warm = [r["elapsed_s"] for r in ok if r.get("elapsed_s") is not None]
        shown = sum(r.get("important_in_input", 0) for r in ok)
        counter_in = sum(r.get("counter_in_input", 0) for r in ok)
        groups[name] = {
            "cases": len(part), "ran": len(ran), "not_run": len(part) - len(ran),
            "json_ok": sum(bool(r.get("json_ok")) for r in ran),
            "json_rate": pct(sum(bool(r.get("json_ok")) for r in ran), len(part)),
            "schema_ok": sum(r.get("schema_errors") == [] for r in ran),
            "failures": {k: sum(r.get("failure") == k for r in part) for k in FAILURES + ("dataset_missing", "not_run")
                         if any(r.get("failure") == k for r in part)},
            "claims": sum(r.get("claims", 0) for r in ok), "accepted": accepted, "reviewed": reviewed,
            "correct": sum(r.get("correct", 0) for r in ok),
            "wrong_accepted": sum(len(r.get("wrong_accepted", [])) for r in ok),
            "unreviewed": sum(len(r.get("unreviewed", [])) for r in ok),
            "accepted_accuracy": pct(sum(r.get("correct", 0) for r in ok), reviewed),
            "critical_accepted": sum(len(r.get("critical_accepted", [])) for r in ok),
            "critical_emitted": sum(len(r.get("critical_emitted", [])) for r in ok),
            "critical_rejected": sum(r.get("critical_rejected", 0) for r in ok),
            "core_draft_possible": len(possible), "core_draft": sum(bool(r.get("core_draft")) for r in possible),
            "core_draft_rate": pct(sum(bool(r.get("core_draft")) for r in possible), len(possible)),
            "insufficient_cases": len(insufficient),
            "insufficient_withheld": sum(not r.get("core_draft") for r in insufficient),
            "important_in_input": shown,
            "important_not_in_input": sum(r.get("important_not_in_input", 0) for r in ok),
            "recall_model": pct(sum(r.get("recall_model", 0) for r in ok), shown),
            "recall_accepted": pct(sum(r.get("recall_accepted", 0) for r in ok), shown),
            "mention_model": pct(sum(r.get("mention_model", 0) for r in ok), shown),
            "counter_model": pct(sum(r.get("counter_model", 0) for r in ok), counter_in),
            "counter_accepted": pct(sum(r.get("counter_accepted", 0) for r in ok), counter_in),
            "empty_answers": sum(r.get("claims", 0) == 0 for r in ok),
            "elapsed_median_s": round(statistics.median(warm), 1) if warm else None,
            "elapsed_p95_s": percentile(warm, 0.95)}
    return groups


# ------------------------------------------------------------------ CLI

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--source-data", required=True, type=Path)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--output", type=Path)
    r = sub.add_parser("run")
    r.add_argument("--experiment", required=True, type=Path)
    r.add_argument("--model", required=True)
    r.add_argument("--endpoint", default="http://127.0.0.1:11434")
    r.add_argument("--label", default="final")
    r.add_argument("--cases", nargs="*")
    r.add_argument("--resume", action="store_true")
    r.add_argument("--timeout", type=float, default=120)
    r.add_argument("--num-ctx", type=int)
    r.add_argument("--num-predict", type=int)
    v = sub.add_parser("revalidate")
    v.add_argument("--experiment", required=True, type=Path)
    v.add_argument("--labels", nargs="*", default=["final", "stability"])
    q = sub.add_parser("report")
    q.add_argument("--experiment", required=True, type=Path)
    q.add_argument("--labels", required=True, type=Path)
    q.add_argument("--output", required=True, type=Path)
    q.add_argument("--label", default="final")
    q.add_argument("--runs", type=Path, help="default <experiment>/runs; or <experiment>/revalidated/<validator>")
    args = parser.parse_args(argv)
    if args.command == "prepare":
        print(prepare(args.source_data, args.manifest, args.output))
    elif args.command == "run":
        options = {k: v for k, v in (("num_ctx", args.num_ctx), ("num_predict", args.num_predict)) if v}
        print(json.dumps(run(args.experiment, args.model, args.endpoint, args.label, args.cases, args.resume,
                             timeout=args.timeout, options=options), ensure_ascii=False))
    elif args.command == "revalidate":
        print(revalidate(args.experiment, tuple(args.labels)))
    else:
        result = report(args.experiment, args.labels, args.output, label=args.label, runs_root=args.runs)
        print(json.dumps(result["summary"]["eval"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
