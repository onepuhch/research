"""Append or update CSV rows from JSON input.

Usage:
    python scripts/add_entry.py examples/memory_review.json

JSON formats:
    {"target_table": "...", "data": { ...columns... }}
    {"target_table": "...", "column1": "...", "column2": "..."}

Table behavior comes from config/schema.json:
    master  : upsert by key
    log     : always append with generated ID
    tracked : update by key when provided, otherwise create new ID
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402


def today() -> str:
    return date.today().isoformat()


def extract(record: dict) -> tuple[str, dict[str, str]]:
    table = record.get("target_table")
    if not isinstance(table, str) or not table.strip():
        raise ValueError("JSON must include a non-empty 'target_table' string.")

    data = record.get("data")
    if data is None:
        data = {key: value for key, value in record.items() if key != "target_table"}
    if not isinstance(data, dict):
        raise ValueError("'data' must be an object.")

    return table.strip(), {key: c.stringify(value) for key, value in data.items()}


def parse_number(value: str) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace(",", "").replace("%", "").strip()
    match = re.fullmatch(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(text)


def format_change_rate(previous: float, current: float) -> str | None:
    if previous == 0:
        return None
    rate = (current - previous) / abs(previous) * 100
    return f"{rate:.1f}%"


def direction_from_numbers(previous: float, current: float) -> str:
    if current > previous:
        return "상향"
    if current < previous:
        return "하향"
    return "유지"


def direction_from_change_rate(value: str) -> str | None:
    number = parse_number(value)
    if number is None:
        return None
    if number > 0:
        return "상향"
    if number < 0:
        return "하향"
    return "유지"


def latest_metric_row(rows: list[dict[str, str]], subject: str, metric_name: str) -> dict[str, str] | None:
    candidates = [
        row
        for row in rows
        if row.get("종목/업종") == subject and row.get("지표명") == metric_name
    ]
    if not candidates:
        return None
    return candidates[-1]


def preprocess_metric_log(data: dict[str, str], rows: list[dict[str, str]]) -> None:
    subject = (data.get("종목/업종") or "").strip()
    metric_name = (data.get("지표명") or "").strip()
    if not subject or not metric_name:
        raise ValueError("metric_log requires both '종목/업종' and '지표명'.")

    previous_row = latest_metric_row(rows, subject, metric_name)
    if not data.get("이전값") and previous_row:
        data["이전값"] = previous_row.get("현재값", "")

    previous = parse_number(data.get("이전값", ""))
    current = parse_number(data.get("현재값", ""))

    if not data.get("변화율") and previous is not None and current is not None:
        change_rate = format_change_rate(previous, current)
        if change_rate is not None:
            data["변화율"] = change_rate

    if not data.get("방향"):
        if previous is not None and current is not None:
            data["방향"] = direction_from_numbers(previous, current)
        elif data.get("변화율"):
            inferred = direction_from_change_rate(data["변화율"])
            if inferred:
                data["방향"] = inferred


def validate_unknown_columns(table: str, data: dict[str, str], columns: list[str]) -> None:
    unknown = [key for key in data if key not in columns]
    if unknown:
        raise ValueError(
            f"unknown column(s) for '{table}': {', '.join(unknown)}\n"
            f"  allowed columns: {', '.join(columns)}"
        )


def apply_default_dates(data: dict[str, str], columns: list[str]) -> None:
    for column in ("날짜", "마지막 업데이트"):
        if column in columns and not data.get(column):
            data[column] = today()

    if "최근 점검일" in columns:
        data["최근 점검일"] = today()


def process(raw: dict) -> None:
    table, data = extract(raw)
    definition = c.table_def(table)
    columns = definition["columns"]
    table_type = definition["type"]
    key = definition["key"]

    validate_unknown_columns(table, data, columns)
    apply_default_dates(data, columns)
    rows = c.read_rows(table)

    if table == "metric_log":
        preprocess_metric_log(data, rows)

    problems = c.validate_enums(data)
    if problems:
        raise ValueError("enum validation failed:\n" + "\n".join(problems))

    if table_type == "master":
        key_value = data.get(key)
        if not key_value:
            raise ValueError(f"master table '{table}' requires key '{key}'.")
        for row in rows:
            if row.get(key) == key_value:
                row.update({k: v for k, v in data.items() if k in columns})
                c.write_rows(table, rows)
                print(f"[updated] {table}: {key}={key_value}")
                return
        rows.append(data)
        c.write_rows(table, rows)
        print(f"[added] {table}: {key}={key_value}")
        return

    if table_type == "log":
        data[key] = c.next_id(table)
        rows.append(data)
        c.write_rows(table, rows)
        print(f"[added] {table}: {key}={data[key]}")
        return

    if table_type == "tracked":
        key_value = (data.get(key) or "").strip()
        if key_value:
            for row in rows:
                if row.get(key) == key_value:
                    row.update({k: v for k, v in data.items() if k in columns and v != ""})
                    c.write_rows(table, rows)
                    print(f"[updated] {table}: {key}={key_value}")
                    return
            raise ValueError(
                f"{key}={key_value} was not found. Leave '{key}' empty to create a new row."
            )
        data[key] = c.next_id(table)
        rows.append(data)
        c.write_rows(table, rows)
        print(f"[added] {table}: {key}={data[key]}")
        return

    raise ValueError(f"unknown table type: {table_type}")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: python scripts/add_entry.py <input.json>")
        return 1

    path = Path(argv[1])
    if not path.exists():
        print(f"[error] file not found: {path}")
        return 1

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        print(f"[error] failed to parse JSON: {error}")
        return 1

    records = payload if isinstance(payload, list) else [payload]
    for record in records:
        if not isinstance(record, dict):
            print(f"[error] each input item must be an object: {record!r}")
            return 1
        try:
            process(record)
        except ValueError as error:
            print(f"[error] {error}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
