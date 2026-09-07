"""Idempotently add v2 fields; preserve originals and isolate exact demo records."""
import csv
import hashlib
import json
from pathlib import Path
import common as c


def migrate() -> None:
    backup = c.DATA_DIR.parent / "archive" / "pre_v2"
    backup.mkdir(parents=True, exist_ok=True)
    manifest = c.read_json(backup / "manifest.json", {})
    examples = {
        "investment_review_log": ("종목/업종", "메모리 반도체"),
        "metric_log": ("종목/업종", "메모리 반도체"),
        "bottleneck_log": ("log_id", "BTL-0001"),
        "industry_indicators": ("업종", "메모리 반도체"),
        "sectors": ("sector_id", "SEC-0001"),
    }
    for table, definition in c.TABLES.items():
        path = c.csv_path(table)
        if path.exists() and table not in manifest:
            original = path.read_bytes()
            target = backup / path.name
            if not target.exists():
                target.write_bytes(original)
            manifest[table] = hashlib.sha256(target.read_bytes()).hexdigest()
            c.atomic_json(backup / "manifest.json", manifest)
        rows = c.read_rows(table)
        changed = not path.exists()
        if path.exists():
            with path.open(encoding=c.ENCODING, newline="") as handle:
                changed = next(csv.reader(handle), []) != definition["columns"]
        for row in rows:
            if row.get("data_quality"):
                continue
            changed = True
            field, expected = examples.get(table, ("", ""))
            demo = bool(field and row.get(field) == expected and
                        (row.get("날짜", row.get("마지막 업데이트")) == "2026-06-03"))
            row["data_quality"] = "example" if demo else "legacy"
            if table == "signal_log":
                row["extraction_method"] = "legacy"
            if table == "investment_review_log" and not demo:
                row.update({"사업 단계": "미확인", "근거 수준": "가설", "검토 상태": "재검토"})
        if changed:
            c.write_rows(table, rows)
    print("[migration] v2 ready; originals retained in data/archive/pre_v2")


if __name__ == "__main__":
    migrate()
