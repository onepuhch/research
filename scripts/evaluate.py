"""Create a deterministic, tier-stratified review queue without invented verdicts."""
import argparse
import csv
import random
from pathlib import Path
import common as c


def sample_rows(rows, per_tier=20, seed=20260906):
    rng = random.Random(seed)
    result = []
    for tier in c.ENUMS["티어"]:
        unique = {}
        for row in rows:
            if row.get("티어") == tier and row.get("data_quality") not in {"example", "quarantine"}:
                unique.setdefault((row.get("entity_id") or row.get("종목/티커"), row.get("source_id") or row.get("출처URL")), row)
        pool = sorted(unique.values(), key=lambda r: r["signal_id"])
        result.extend(rng.sample(pool, min(per_tier, len(pool))))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-tier", type=int, default=20)
    parser.add_argument("--output", type=Path, default=c.ROOT / "reports" / "generated" / "evaluation_queue.csv")
    args = parser.parse_args()
    if args.per_tier < 1:
        parser.error("--per-tier must be positive")
    rows = sample_rows(c.read_rows("signal_log"), args.per_tier)
    columns = c.table_def("evaluation_log")["columns"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding=c.ENCODING, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({"signal_id": row["signal_id"], "평가 종류": "검토 가치", "판정": "미확인",
                             "사전 기준": "원문에서 기업·사건·기간 확인 후 추가 연구 가치 판단",
                             "출처URL": row.get("document_url") or row.get("출처URL"),
                             "메모": f"티어 {row['티어']}; {row.get('종목/티커')}; {row.get('특이값 요약')}",
                             "data_quality": "live"})
    print(f"[evaluation] {len(rows)} unlabelled cases: {args.output}")


if __name__ == "__main__":
    main()
