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
import hashlib
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402
import metrics


def today() -> str:
    return c.today()


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


def preprocess_metric_log(data: dict[str, str], rows: list[dict[str, str]]) -> None:
    metrics.prepare(data, rows)


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

    if "최근 점검일" in columns and "최근 점검일" not in data and data.get("변경 사유"):
        data["최근 점검일"] = today()


def process(raw: dict) -> str:
    table, data = extract(raw)
    definition = c.table_def(table)
    columns = definition["columns"]
    table_type = definition["type"]
    key = definition["key"]

    validate_unknown_columns(table, data, columns)
    supplied_date = "날짜" in data
    apply_default_dates(data, columns)
    if table_type == "tracked" and data.get(key) and not supplied_date:
        data.pop("날짜", None)
    rows = c.read_rows(table)
    if "data_quality" in columns and not data.get("data_quality"):
        existing = next((r for r in rows if data.get(key) and r.get(key) == data[key]), {})
        data["data_quality"] = existing.get("data_quality") or "live"

    if table == "metric_log":
        preprocess_metric_log(data, rows)
        duplicate = next((r for r in rows if r.get("observation_key") == data["observation_key"]), None)
        if duplicate:
            if metrics.number(duplicate.get("현재값")) != metrics.number(data.get("현재값")):
                raise ValueError("same observation key has a different value; use a distinct as_of timestamp")
            return duplicate[key]

    problems = c.validate_enums(data)
    for column, enum_name in definition.get("enum_aliases", {}).items():
        if data.get(column) and data[column] not in c.ENUMS[enum_name]:
            problems.append(f"invalid {column}: {data[column]}")
    if problems:
        raise ValueError("enum validation failed:\n" + "\n".join(problems))
    for unique in definition.get("unique_nonempty", []):
        if data.get(unique):
            previous = next((r for r in rows if r.get(unique) == data[unique]), None)
            if previous:
                return previous[key]

    if table_type == "master":
        key_value = data.get(key)
        if not key_value:
            raise ValueError(f"master table '{table}' requires key '{key}'.")
        for row in rows:
            if row.get(key) == key_value:
                row.update({k: v for k, v in data.items() if k in columns})
                c.write_rows(table, rows)
                print(f"[updated] {table}: {key}={key_value}")
                return row[key]
        rows.append(data)
        c.write_rows(table, rows)
        print(f"[added] {table}: {key}={key_value}")
        return data[key]

    if table_type == "log":
        data[key] = c.next_id(table)
        rows.append(data)
        c.write_rows(table, rows)
        print(f"[added] {table}: {key}={data[key]}")
        return data[key]

    if table_type == "tracked":
        key_value = (data.get(key) or "").strip()
        if key_value:
            for row in rows:
                if row.get(key) == key_value:
                    if table == "investment_review_log" and row.get("data_quality") == "live" and not data.get("변경 사유"):
                        raise ValueError("provide a new 변경 사유 for each review update")
                    before = dict(row)
                    row.update({k: v for k, v in data.items() if k in columns})
                    if table == "investment_review_log":
                        commit_review(rows, before, row)
                    else:
                        c.write_rows(table, rows)
                    print(f"[updated] {table}: {key}={key_value}")
                    return row[key]
            raise ValueError(
                f"{key}={key_value} was not found. Leave '{key}' empty to create a new row."
            )
        data[key] = c.next_id(table)
        rows.append(data)
        if table == "investment_review_log":
            commit_review(rows, {}, data)
        else:
            c.write_rows(table, rows)
        print(f"[added] {table}: {key}={data[key]}")
        return data[key]

    raise ValueError(f"unknown table type: {table_type}")


def commit_review(rows, before, after):
    if before == after:
        return
    if after.get("data_quality") == "live":
        if not after.get("entity_id") or not after.get("thesis_key"):
            raise ValueError("live ideas require entity_id and thesis_key")
        if not after.get("변경 사유"):
            raise ValueError("review changes require 변경 사유")
        if after.get("검토 상태") == "추적":
            needed = ["출처URL", "모니터링 지표", "종료 조건(정량)", "다음 점검일", "추적 지표 정의"]
            missing = [key for key in needed if not after.get(key)]
            if missing:
                raise ValueError(f"tracking definition incomplete: {missing}")
        if after.get("다음 점검일"):
            date.fromisoformat(after["다음 점검일"])
        if after.get("추적 지표 정의"):
            spec = json.loads(after["추적 지표 정의"])
            if not isinstance(spec, dict) or not isinstance(spec.get("metrics", []), list):
                raise ValueError("추적 지표 정의 must contain a metrics array")
        if after.get("근거 수준") == "시계열 검증" or after.get("현재 단계") == "중기":
            groups = {}
            for observation in c.read_live_rows("metric_log"):
                if observation.get("entity_id") == after.get("entity_id") and observation.get("metric_kind") == "consensus":
                    groups.setdefault(metrics.series_key(observation), []).append(observation)
            if not any(metrics.revision_stats(group)["up_months"] >= 2 and
                       metrics.revision_stats(group)["age_days"] <= c.policy()["metric_stale_days"] for group in groups.values()):
                raise ValueError("time-series stage requires same-definition consensus increases across at least 2 month transitions")
    history = c.read_rows("review_history")
    event = {"review_id": c.next_id("review_history"), "idea_id": after["idea_id"],
             "reviewed_at": c.utc_now(), "이전 상태": before.get("검토 상태", ""),
             "이후 상태": after.get("검토 상태", ""), "판단 변화": after.get("판단 변화", "자료 부족"),
             "변경 사유": after.get("변경 사유", "legacy update"),
             "evidence_ids": after.get("origin_signal_ids", "[]"),
             "before_json": json.dumps(before, ensure_ascii=False, sort_keys=True),
             "after_json": json.dumps(after, ensure_ascii=False, sort_keys=True),
             "data_quality": after.get("data_quality", "legacy")}
    event["event_key"] = hashlib.sha256((event["before_json"] + event["after_json"]).encode()).hexdigest()
    if not any(r.get("event_key") == event["event_key"] for r in history):
        history.append(event)
    c.commit_tables({"investment_review_log": rows, "review_history": history})


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
