"""Render a short discovery digest from signal_log.csv."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

TIER_ORDER = {"A": 0, "B": 1, "관망": 2}


def as_int(value: str) -> int:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return 0


def sort_signals(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            TIER_ORDER.get(row.get("티어", ""), 99),
            -as_int(row.get("upside_score", "")),
            row.get("날짜", ""),
            row.get("signal_id", ""),
        ),
    )


def render_digest(rows: list[dict[str, str]], top: int) -> str:
    ranked = sort_signals(rows)[:top]
    output = [f"# Discovery Digest ({date.today().isoformat()})", ""]
    output.append("개인 리서치 기록이며 투자 권유가 아닙니다.")
    output.append("")
    output.append(f"상위 후보 {len(ranked)}건 / 전체 signal_log {len(rows)}건")
    output.append("")

    if not ranked:
        output.append("- 신호 없음")
        return "\n".join(output)

    for index, row in enumerate(ranked, 1):
        output.append(
            f"## {index}. {row.get('종목/티커', '미분류')} "
            f"| {row.get('티어', '')} | {row.get('upside_score', '')}/12 | {row.get('신호유형', '')}"
        )
        output.append(f"- 테마: {row.get('테마', '')}")
        output.append(f"- 단계 추정: {row.get('단계 추정', '')}")
        output.append(f"- 특이값: {row.get('특이값 요약', '')}")
        if row.get("용어 풀이"):
            output.append(f"- 용어 풀이: {row['용어 풀이']}")
        output.append(f"- 출처: {row.get('출처', '')} {row.get('출처URL', '')}".rstrip())
        output.append("")
    return "\n".join(output)


def save(content: str) -> Path:
    output_dir = c.ROOT / "reports" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"discovery_digest_{date.today().isoformat()}.md"
    path.write_text(content, encoding="utf-8")
    return path


def parse_top(args: list[str]) -> int:
    top = 10
    if not args:
        return top
    if len(args) == 2 and args[0] == "--top":
        try:
            top = int(args[1])
        except ValueError as error:
            raise ValueError("--top requires an integer.") from error
        if top < 1:
            raise ValueError("--top must be 1 or greater.")
        return top
    raise ValueError("Usage: python scripts/digest.py [--top N]")


def main(argv: list[str]) -> int:
    try:
        top = parse_top(argv[1:])
    except ValueError as error:
        print(f"[error] {error}")
        return 1

    rows = c.read_rows("signal_log")
    content = render_digest(rows, top)
    print(content)
    path = save(content)
    print(f"\n[saved] {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
