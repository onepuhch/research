"""CSV 의 마지막 N개 행을 구글시트 복붙용 TSV 로 출력하고 파일로도 저장한다.

사용법:
    python scripts/export_tsv.py investment_review_log --last 5
    python scripts/export_tsv.py bottleneck_log              # 전체
    python scripts/export_tsv.py sectors --no-header         # 헤더 빼고

출력 내용을 복사해 구글시트에 붙여넣으면 칸이 자동으로 나뉜다.
콘솔 한글이 깨지면 reports/generated/<table>_export.tsv 파일을 열어 복사하세요.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402


def clean(value) -> str:
    return str(value).replace("\t", " ").replace("\n", " ").replace("\r", " ").strip()


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("사용법: python scripts/export_tsv.py <table> [--last N] [--no-header]")
        print(f"테이블: {', '.join(c.TABLES)}")
        return 1

    table = argv[1]
    try:
        td = c.table_def(table)
    except ValueError as e:
        print(f"[오류] {e}")
        return 1

    last = None
    if "--last" in argv:
        i = argv.index("--last")
        try:
            last = int(argv[i + 1])
            if last < 1:
                raise ValueError
        except (IndexError, ValueError):
            print("[오류] --last 뒤에 1 이상의 정수를 주세요. 예: --last 5")
            return 1
    no_header = "--no-header" in argv

    cols = td["columns"]
    rows = c.read_rows(table)
    if last is not None:
        rows = rows[-last:]

    lines: list[str] = []
    if not no_header:
        lines.append("\t".join(cols))
    for r in rows:
        lines.append("\t".join(clean(r.get(col, "")) for col in cols))
    out = "\n".join(lines)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(out)

    outdir = c.ROOT / "reports" / "generated"
    outdir.mkdir(parents=True, exist_ok=True)
    fpath = outdir / f"{table}_export.tsv"
    fpath.write_text(out, encoding="utf-8-sig")
    print(f"\n[저장] {fpath}  ({len(rows)}행)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
