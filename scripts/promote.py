"""Promote one discovery signal into the investment review log.

Usage:
    python scripts/promote.py SIG-0015
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import add_entry  # noqa: E402
import common as c  # noqa: E402


SIGNAL_TABLE = "signal_log"
REVIEW_TABLE = "investment_review_log"
DEFAULT_IDEA_TYPE = "병목 확산형"
DEFAULT_STRENGTH = "2"


def parser() -> argparse.ArgumentParser:
    idea_types = c.ENUMS.get("아이디어 유형", [])
    strengths = c.ENUMS.get("근거 강도", [])
    argument_parser = argparse.ArgumentParser(
        description="signal_log의 신호를 investment_review_log로 승격합니다."
    )
    argument_parser.add_argument("signal_id", help="승격할 signal_id (예: SIG-0015)")
    argument_parser.add_argument(
        "--type",
        dest="idea_type",
        choices=idea_types,
        default=DEFAULT_IDEA_TYPE,
        help=f"아이디어 유형 (기본값: {DEFAULT_IDEA_TYPE})",
    )
    argument_parser.add_argument(
        "--strength",
        choices=strengths,
        default=DEFAULT_STRENGTH,
        help=f"근거 강도 (기본값: {DEFAULT_STRENGTH})",
    )
    argument_parser.add_argument(
        "--trigger",
        default="",
        help="다음 단계 트리거 (기본값: 빈 문자열)",
    )
    return argument_parser


def find_signal(signal_id: str) -> dict[str, str] | None:
    key = c.table_def(SIGNAL_TABLE)["key"]
    wanted = signal_id.strip()
    for row in c.read_rows(SIGNAL_TABLE):
        if (row.get(key) or "").strip() == wanted:
            return row
    return None


def build_review_data(
    signal: dict[str, str], idea_type: str, strength: str, trigger: str
) -> dict[str, str]:
    theme = (signal.get("테마") or "").strip()
    summary = (signal.get("특이값 요약") or "").strip()
    discovery_context = " | ".join(
        part
        for part in (
            f"테마: {theme}" if theme else "",
            f"발굴 경위: {summary}" if summary else "",
        )
        if part
    )
    return {
        "대상유형": "종목",
        "종목/업종": (signal.get("종목/티커") or "").strip(),
        "당시 판단": discovery_context,
        "현재 단계": (signal.get("단계 추정") or "").strip(),
        "아이디어 유형": idea_type,
        "근거 강도": strength,
        "핵심 근거": summary,
        "다음 단계 트리거": trigger.strip(),
    }


def promote_signal(
    signal: dict[str, str],
    idea_type: str = DEFAULT_IDEA_TYPE,
    strength: str = DEFAULT_STRENGTH,
    trigger: str = "",
) -> str:
    idea_id = c.next_id(REVIEW_TABLE)
    payload = {
        "target_table": REVIEW_TABLE,
        "data": build_review_data(signal, idea_type, strength, trigger),
    }
    add_entry.process(payload)
    return idea_id


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    signal = find_signal(args.signal_id)
    if signal is None:
        print(f"[error] signal_id를 찾을 수 없습니다: {args.signal_id}", file=sys.stderr)
        return 1

    try:
        idea_id = promote_signal(signal, args.idea_type, args.strength, args.trigger)
    except (FileNotFoundError, ValueError) as error:
        print(f"[error] 승격 실패: {error}", file=sys.stderr)
        return 1

    print(f"[promoted] {args.signal_id} -> {idea_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
