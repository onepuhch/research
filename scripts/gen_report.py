"""Generate markdown reports from CSV data.

Usage:
    python scripts/gen_report.py board
    python scripts/gen_report.py weekly
    python scripts/gen_report.py sector "메모리 반도체"
    python scripts/gen_report.py share
    python scripts/gen_report.py metric
    python scripts/gen_report.py metric "메모리 반도체"
    python scripts/gen_report.py metric --min 3
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

STALE_DAYS = 14
STAGE_ORDER = {stage: idx for idx, stage in enumerate(c.ENUMS.get("현재 단계", []))}


def active(row: dict[str, str]) -> bool:
    return (row.get("현재 단계") or "").strip() != "제외"


def strength(row: dict[str, str]) -> int:
    value = (row.get("근거 강도") or "").strip()
    return int(value) if value.isdigit() else 0


def days_since(value: str) -> int | None:
    try:
        y, m, d = (int(part) for part in value.split("-"))
        return (date.today() - date(y, m, d)).days
    except Exception:
        return None


def sector_name_map() -> dict[str, str]:
    return {
        row["sector_id"]: row.get("섹터명", "")
        for row in c.read_rows("sectors")
        if row.get("sector_id")
    }


def sort_ideas(ideas: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        ideas,
        key=lambda row: (
            -strength(row),
            STAGE_ORDER.get((row.get("현재 단계") or "").strip(), 99),
            row.get("날짜", ""),
        ),
    )


def render_board() -> str:
    ideas = sort_ideas([row for row in c.read_rows("investment_review_log") if active(row)])
    output = [f"# 추적 아이디어 상태판 ({date.today().isoformat()})", ""]
    output.append(f"활성 아이디어 {len(ideas)}건, 정체 기준 {STALE_DAYS}일")
    output.append("")
    output.append("| 종목/업종 | 현재 단계 | 근거 강도 | 최근 점검일 | 다음 단계 트리거 | 종료 조건 | 정체 |")
    output.append("| --- | --- | --- | --- | --- | --- | --- |")
    if not ideas:
        output.append("| (없음) |  |  |  |  |  |  |")
    for row in ideas:
        checked_days = days_since(row.get("최근 점검일", ""))
        stale = f"{checked_days}일" if checked_days is not None and checked_days >= STALE_DAYS else ""
        output.append(
            f"| {row.get('종목/업종', '')} | {row.get('현재 단계', '')} | {strength(row)}/5 "
            f"| {row.get('최근 점검일', '')} | {row.get('다음 단계 트리거', '')} "
            f"| {row.get('종료 조건(정량)', '')} | {stale} |"
        )
    output.append("")
    return "\n".join(output)


def render_weekly() -> str:
    ideas = [row for row in c.read_rows("investment_review_log") if active(row)]
    bottlenecks = c.read_rows("bottleneck_log")
    sector_names = sector_name_map()

    output = [f"# 주간 리서치 브리프 ({date.today().isoformat()})", ""]
    output.append(f"활성 아이디어 {len(ideas)}건, 병목 후보 {len(bottlenecks)}건")
    output.append("")
    output.append("## 활성 아이디어")
    if not ideas:
        output.append("- (없음)")
    for row in sort_ideas(ideas):
        sector = sector_names.get(row.get("sector_id", ""), row.get("sector_id", "")) or "-"
        output.append(
            f"- **{row.get('종목/업종', '?')}** [{sector}] "
            f"{row.get('현재 단계', '')}, {row.get('아이디어 유형', '')}, 근거 강도 {strength(row)}/5"
        )
        if row.get("핵심 촉매"):
            output.append(f"  - 촉매: {row['핵심 촉매']}")
        if row.get("내 견해와의 차이"):
            output.append(f"  - 차이: {row['내 견해와의 차이']}")
        if row.get("다음 단계 트리거"):
            output.append(f"  - 다음 단계 트리거: {row['다음 단계 트리거']}")
        if row.get("종료 조건(정량)"):
            output.append(f"  - 종료 조건: {row['종료 조건(정량)']}")
    output.append("")

    output.append("## 병목 후보 최근 5건")
    if not bottlenecks:
        output.append("- (없음)")
    for row in bottlenecks[-5:]:
        output.append(
            f"- {row.get('날짜', '')} {row.get('섹터/메인 테마', '')}: "
            f"{row.get('병목 후보', '')} ({row.get('현재 단계', '')})"
        )
    output.append("")
    return "\n".join(output)


def render_sector(name: str) -> str:
    sector_names = sector_name_map()
    sector_ids = {sid for sid, sector_name in sector_names.items() if name in (sector_name, sid)}
    ideas = [
        row
        for row in c.read_rows("investment_review_log")
        if row.get("sector_id") in sector_ids or name in (row.get("종목/업종") or "")
    ]
    output = [f"# 섹터 비교: {name} ({date.today().isoformat()})", ""]
    if not ideas:
        output.append("- 해당 섹터의 아이디어가 없습니다.")
        return "\n".join(output)

    output.append("| 종목/업종 | 단계 | 유형 | 근거 강도 | 촉매 | 종료 조건 |")
    output.append("| --- | --- | --- | --- | --- | --- |")
    for row in sort_ideas(ideas):
        output.append(
            f"| {row.get('종목/업종', '')} | {row.get('현재 단계', '')} | "
            f"{row.get('아이디어 유형', '')} | {strength(row)}/5 | "
            f"{row.get('핵심 촉매', '')} | {row.get('종료 조건(정량)', '')} |"
        )
    output.append("")
    return "\n".join(output)


def render_share() -> str:
    ideas = sort_ideas([row for row in c.read_rows("investment_review_log") if active(row)])
    output = [f"# 투자 아이디어 요약 ({date.today().isoformat()})", ""]
    if not ideas:
        output.append("(활성 아이디어 없음)")
    for row in ideas:
        output.append(
            f"## {row.get('종목/업종', '?')} | {row.get('현재 단계', '')} | "
            f"{row.get('아이디어 유형', '')} | 근거 강도 {strength(row)}/5"
        )
        if row.get("핵심 촉매"):
            output.append(f"- 촉매: {row['핵심 촉매']}")
        if row.get("종료 조건(정량)"):
            output.append(f"- 종료 조건: {row['종료 조건(정량)']}")
        output.append("")
    output.append("개인 리서치 기록이며 투자 권유가 아닙니다.")
    return "\n".join(output)


def metric_sort_key(row: dict[str, str]) -> tuple[str, str]:
    return (row.get("날짜", ""), row.get("metric_id", ""))


def group_metric_rows() -> dict[tuple[str, str], list[dict[str, str]]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in c.read_rows("metric_log"):
        subject = row.get("종목/업종", "")
        metric_name = row.get("지표명", "")
        if subject and metric_name:
            groups[(subject, metric_name)].append(row)
    for rows in groups.values():
        rows.sort(key=metric_sort_key)
    return groups


def consecutive_up_count(rows: list[dict[str, str]]) -> int:
    count = 0
    for row in reversed(rows):
        if (row.get("방향") or "").strip() != "상향":
            break
        count += 1
    return count


def metric_summary(groups: dict[tuple[str, str], list[dict[str, str]]]) -> list[dict[str, str | int]]:
    summaries: list[dict[str, str | int]] = []
    for (subject, metric_name), rows in groups.items():
        if not rows:
            continue
        latest = rows[-1]
        summaries.append(
            {
                "종목/업종": subject,
                "지표명": metric_name,
                "최신 현재값": latest.get("현재값", ""),
                "연속 상향 횟수": consecutive_up_count(rows),
                "최근 변화율": latest.get("변화율", ""),
                "최근 날짜": latest.get("날짜", ""),
                "출처": latest.get("출처", ""),
            }
        )
    return summaries


def render_metric_board(min_count: int) -> str:
    summaries = [
        row
        for row in metric_summary(group_metric_rows())
        if int(row["연속 상향 횟수"]) >= min_count
    ]
    summaries.sort(
        key=lambda row: (
            -int(row["연속 상향 횟수"]),
            str(row["종목/업종"]),
            str(row["지표명"]),
        )
    )

    output = [f"# 지표 발굴 보드 ({date.today().isoformat()})", ""]
    output.append(f"노출 기준: 연속 상향 {min_count}회 이상")
    output.append("")
    output.append("| 종목/업종 | 지표명 | 연속 상향 횟수 | 최근 변화율 | 최근 날짜 | 출처 |")
    output.append("| --- | --- | --- | --- | --- | --- |")
    if not summaries:
        output.append("| (없음) |  |  |  |  |  |")
    for row in summaries:
        output.append(
            f"| {row['종목/업종']} | {row['지표명']} | {row['연속 상향 횟수']} "
            f"| {row['최근 변화율']} | {row['최근 날짜']} | {row['출처']} |"
        )
    output.append("")
    return "\n".join(output)


def render_metric_detail(subject: str) -> str:
    summaries = [
        row for row in metric_summary(group_metric_rows()) if row["종목/업종"] == subject
    ]
    summaries.sort(key=lambda row: (-int(row["연속 상향 횟수"]), str(row["지표명"])))

    output = [f"# 지표 상세: {subject} ({date.today().isoformat()})", ""]
    output.append("| 지표명 | 최신 현재값 | 연속 상향 횟수 | 최근 변화율 | 최근 날짜 | 출처 |")
    output.append("| --- | --- | --- | --- | --- | --- |")
    if not summaries:
        output.append("| (없음) |  |  |  |  |  |")
    for row in summaries:
        output.append(
            f"| {row['지표명']} | {row['최신 현재값']} | {row['연속 상향 횟수']} "
            f"| {row['최근 변화율']} | {row['최근 날짜']} | {row['출처']} |"
        )
    output.append("")
    return "\n".join(output)


def parse_metric_args(args: list[str]) -> tuple[str | None, int]:
    subject: str | None = None
    min_count = 2
    index = 0
    while index < len(args):
        value = args[index]
        if value == "--min":
            if index + 1 >= len(args):
                raise ValueError("--min requires a number.")
            try:
                min_count = int(args[index + 1])
            except ValueError as error:
                raise ValueError("--min requires an integer.") from error
            if min_count < 1:
                raise ValueError("--min must be 1 or greater.")
            index += 2
            continue
        if subject is not None:
            raise ValueError("metric accepts at most one subject argument.")
        subject = value
        index += 1
    return subject, min_count


def save(name: str, content: str) -> Path:
    output_dir = c.ROOT / "reports" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name}_{date.today().isoformat()}.md"
    path.write_text(content, encoding="utf-8")
    return path


def print_usage() -> None:
    print("Usage: python scripts/gen_report.py <board|weekly|sector|share|metric> [args]")
    print('       python scripts/gen_report.py sector "메모리 반도체"')
    print('       python scripts/gen_report.py metric "메모리 반도체"')
    print("       python scripts/gen_report.py metric --min 3")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print_usage()
        return 1

    command = argv[1]
    try:
        if command == "board":
            content, name = render_board(), "board"
        elif command == "weekly":
            content, name = render_weekly(), "weekly_brief"
        elif command == "share":
            content, name = render_share(), "share_digest"
        elif command == "sector":
            if len(argv) < 3:
                print('Usage: python scripts/gen_report.py sector "메모리 반도체"')
                return 1
            content, name = render_sector(argv[2]), "sector_compare"
        elif command == "metric":
            subject, min_count = parse_metric_args(argv[2:])
            if subject:
                content, name = render_metric_detail(subject), "metric_detail"
            else:
                content, name = render_metric_board(min_count), "metric_board"
        else:
            print(f"[error] unknown command: {command}")
            print_usage()
            return 1
    except ValueError as error:
        print(f"[error] {error}")
        return 1

    print(content)
    path = save(name, content)
    print(f"\n[saved] {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
