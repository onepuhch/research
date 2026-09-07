"""Investment research system shared helpers.

All table and enum definitions come from config/schema.json.
CSV files are read and written as UTF-8-SIG for Excel/Google Sheets compatibility.
"""
from __future__ import annotations

import csv
import json
import os
import re
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("RESEARCH_DATA_DIR", str(ROOT / "data" / "processed")))
CONFIG_PATH = ROOT / "config" / "schema.json"
ENCODING = "utf-8-sig"

MEGA_CAP_TICKERS = {
    "NVDA", "GOOGL", "GOOG", "MSFT", "AMZN", "AAPL", "META", "TSLA",
    "AVGO", "AMD", "TSM", "ORCL", "NFLX", "INTC", "QCOM", "TXN", "CSCO",
    "IBM", "ADBE", "CRM", "MU", "ASML", "SMCI", "DELL", "ARM",
}
MEGA_CAP_NAMES = {
    "alphabet", "google", "microsoft", "amazon", "apple", "meta", "tesla",
    "nvidia", "broadcom", "oracle", "netflix", "intel", "qualcomm", "cisco",
    "advanced micro devices", "micron", "asml", "taiwan semiconductor",
}


def load_dotenv_value(key: str) -> str:
    """Read a value from the process environment, then the project .env file."""
    value = os.environ.get(key, "").strip()
    if value:
        return value

    env_path = ROOT / ".env"
    if not env_path.exists():
        return ""

    for raw_line in env_path.read_text(encoding=ENCODING).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, raw_value = line.split("=", 1)
        name = name.strip()
        if name.startswith("export "):
            name = name[7:].strip()
        if name != key:
            continue
        parsed = raw_value.strip()
        if len(parsed) >= 2 and parsed[0] == parsed[-1] and parsed[0] in {"'", '"'}:
            parsed = parsed[1:-1]
        return parsed.strip()
    return ""


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def is_megacap(subject: str) -> bool:
    """Return True for large, already well-followed companies."""
    if not subject:
        return False
    upper = subject.upper()
    for ticker in MEGA_CAP_TICKERS:
        if re.search(rf"\b{re.escape(ticker)}\b", upper):
            return True
    lowered = subject.lower()
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", lowered)
        for name in MEGA_CAP_NAMES
    )


def load_schema() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"schema file not found: {CONFIG_PATH}")
    with CONFIG_PATH.open(encoding=ENCODING) as file:
        return json.load(file)


SCHEMA = load_schema()
TABLES = SCHEMA["tables"]
ENUMS = SCHEMA.get("enums", {})


def table_def(table: str) -> dict[str, Any]:
    if table not in TABLES:
        valid = ", ".join(TABLES)
        raise ValueError(f"unknown table '{table}' (valid: {valid})")
    return TABLES[table]


def csv_path(table: str) -> Path:
    return DATA_DIR / f"{table}.csv"


def read_rows(table: str) -> list[dict[str, str]]:
    recover_tables()
    path = csv_path(table)
    if not path.exists():
        return []
    with path.open(encoding=ENCODING, newline="") as file:
        return list(csv.DictReader(file))


def write_rows(table: str, rows: list[dict[str, str]]) -> None:
    columns = table_def(table)["columns"]
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = csv_path(table)
    unknown = set().union(*(set(row) for row in rows)) - set(columns) if rows else set()
    if unknown:
        raise ValueError(f"unknown columns for {table}: {sorted(str(x) for x in unknown)}")
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding=ENCODING, newline="") as file:
            writer = csv.DictWriter(file, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows({column: row.get(column, "") for column in columns} for row in rows)
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def next_id(table: str) -> str:
    definition = table_def(table)
    prefix = definition.get("id_prefix", "ID")
    key = definition["key"]
    max_id = 0
    for row in read_rows(table):
        value = (row.get(key) or "").strip()
        if value.startswith(prefix):
            number = value[len(prefix) :].lstrip("-_")
            if number.isdigit():
                max_id = max(max_id, int(number))
    return f"{prefix}-{max_id + 1:04d}"


def validate_enums(record: dict[str, str]) -> list[str]:
    problems: list[str] = []
    for column, allowed in ENUMS.items():
        value = str(record.get(column, "")).strip()
        if value and value not in allowed:
            problems.append(
                f"  - '{column}' value '{value}' is not allowed. "
                f"Allowed: {', '.join(allowed)}"
            )
    return problems


def ensure_table(table: str) -> None:
    path = csv_path(table)
    if not path.exists() or path.stat().st_size == 0:
        write_rows(table, [])


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today() -> str:
    return datetime.now(timezone(timedelta(hours=9))).date().isoformat()


def policy() -> dict[str, Any]:
    return json.loads((ROOT / "config" / "research_policy.json").read_text(encoding="utf-8"))


def read_live_rows(table: str) -> list[dict[str, str]]:
    return [row for row in read_rows(table) if row.get("data_quality") not in {"example", "quarantine"}]


def active_ideas() -> list[dict[str, str]]:
    return [row for row in read_live_rows("investment_review_log")
            if row.get("현재 단계") != "제외" and row.get("검토 상태") != "종료"]


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def record_run(component: str, status: str, **details: Any) -> None:
    path = DATA_DIR / "run_status.json"
    state = read_json(path, {})
    previous = state.get(component, {})
    state[component] = {"checked_at": utc_now(), "status": status,
                        "last_success_at": utc_now() if status == "success" else previous.get("last_success_at"),
                        **details}
    atomic_json(path, state)


def recover_tables() -> None:
    journal = DATA_DIR / "pending_tables.json"
    if journal.exists():
        for table, rows in read_json(journal, {}).items():
            write_rows(table, rows)
        journal.unlink()


def commit_tables(changes: dict[str, list[dict[str, str]]]) -> None:
    """Recoverable multi-file commit. Callers must use the single-writer workflow."""
    for table, rows in changes.items():
        columns = set(table_def(table)["columns"])
        if any(set(row) - columns for row in rows):
            raise ValueError(f"unknown columns for {table}")
    atomic_json(DATA_DIR / "pending_tables.json", changes)
    recover_tables()


def resolve_entity(entity_id: str, ticker: str = "") -> tuple[str, str]:
    registry = read_json(ROOT / "config" / "entities.json", {})
    for symbol, item in registry.items():
        identities = [item["entity_id"], *item.get("aliases", [])]
        if entity_id in identities or (not entity_id and ticker == symbol):
            if ticker and ticker != symbol:
                raise ValueError("ticker conflicts with registered entity")
            return item["entity_id"], symbol
    return entity_id, ticker
