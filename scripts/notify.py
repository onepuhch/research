"""Push today's new tier A/B discovery signals to Telegram."""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

STATE_PATH = c.DATA_DIR / "notify_state.json"
TELEGRAM_TIMEOUT = 20
MESSAGE_LIMIT = 3500
# 미전송 A/B는 '오늘'이 아니어도 이 기간 안이면 재시도(날짜경계 누락 방지).
# 중복방지(pushed)가 이미 있어 같은 신호가 두 번 가지는 않는다.
NOTIFY_LOOKBACK_DAYS = 14

SIGNAL_TABLE = c.table_def("signal_log")
SIGNAL_ID_COLUMN = SIGNAL_TABLE["key"]
_SIGNAL_COLUMNS = set(SIGNAL_TABLE["columns"])


def _signal_col(name: str) -> str:
    """컬럼을 '이름'으로 잡는다(위치 의존 금지 — schema 순서 바뀌어도 안전)."""
    if name not in _SIGNAL_COLUMNS:
        raise ValueError(f"signal_log에 '{name}' 컬럼이 없음 (schema.json 확인)")
    return name


DATE_COLUMN = _signal_col("날짜")
PUBLISHED_AT_COLUMN = _signal_col("published_at")
SUBJECT_COLUMN = _signal_col("종목/티커")
THEME_COLUMN = _signal_col("테마")
SIGNAL_TYPE_COLUMN = _signal_col("신호유형")
SUMMARY_COLUMN = _signal_col("특이값 요약")
SCORE_COLUMN = _signal_col("upside_score")
TIER_COLUMN = _signal_col("티어")
STAGE_COLUMN = _signal_col("단계 추정")
GLOSSARY_COLUMN = _signal_col("용어 풀이")
SOURCE_COLUMN = _signal_col("출처")
SOURCE_URL_COLUMN = _signal_col("출처URL")
TIER_VALUES = tuple(c.ENUMS["티어"])
if len(TIER_VALUES) < 2:
    raise ValueError("signal tier enum must define at least A and B tiers.")
PUSH_TIERS = TIER_VALUES[:2]
DEFAULT_MIN_TIER = PUSH_TIERS[-1]
TIER_ORDER = {tier: index for index, tier in enumerate(TIER_VALUES)}
TIER_EMOJI = {PUSH_TIERS[0]: "🅰️", PUSH_TIERS[1]: "🅱️"}
BLOCK_SEPARATOR = "──────────"

REVIEW_TABLE = c.table_def("investment_review_log")
(
    REVIEW_ID_COLUMN,
    _REVIEW_DATE_COLUMN,
    _REVIEW_CHECKED_COLUMN,
    _REVIEW_TARGET_TYPE_COLUMN,
    REVIEW_SUBJECT_COLUMN,
    REVIEW_SECTOR_ID_COLUMN,
    REVIEW_JUDGMENT_COLUMN,
    REVIEW_STAGE_COLUMN,
    _REVIEW_IDEA_TYPE_COLUMN,
    REVIEW_STRENGTH_COLUMN,
    *_REVIEW_REMAINING_COLUMNS,
) = REVIEW_TABLE["columns"]
SECTOR_TABLE = c.table_def("sectors")
(
    SECTOR_ID_COLUMN,
    SECTOR_NAME_COLUMN,
    SECTOR_THEME_COLUMN,
    *_SECTOR_REMAINING_COLUMNS,
) = SECTOR_TABLE["columns"]
ACTIVE_REVIEW_STAGES = tuple(c.ENUMS[REVIEW_STAGE_COLUMN][:-1])
REPORT_STAGE_ORDER = tuple(reversed(ACTIVE_REVIEW_STAGES))


def console(text: str) -> None:
    """Print without crashing on Windows cp949 consoles."""
    encoding = sys.stdout.encoding or "utf-8"
    safe = str(text).encode(encoding, errors="backslashreplace").decode(encoding)
    print(safe)


def as_int(value: Any) -> int:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return 0


def parse_args(args: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="render messages without sending or saving state")
    parser.add_argument("--all", action="store_true", help="ignore duplicate prevention and resend eligible signals")
    parser.add_argument(
        "--report",
        action="store_true",
        help="send the investment review status report",
    )
    parser.add_argument(
        "--min-tier",
        choices=PUSH_TIERS,
        default=DEFAULT_MIN_TIER,
        help=f"minimum tier to send (default: {DEFAULT_MIN_TIER})",
    )
    return parser.parse_args(args)


def load_state() -> dict[str, list[str]]:
    if not STATE_PATH.exists():
        return {"pushed": []}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        console(f"[warn] notify state unreadable; starting empty: {error}")
        return {"pushed": []}
    pushed = data.get("pushed", []) if isinstance(data, dict) else []
    if not isinstance(pushed, list):
        console("[warn] notify state has invalid pushed value; starting empty")
        return {"pushed": []}
    return {"pushed": [str(signal_id) for signal_id in pushed if str(signal_id).strip()]}


def save_state(state: dict[str, list[str]]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_PATH.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(STATE_PATH)


def within_lookback(value: Any, today: date, days: int) -> bool:
    """True if the signal date is missing/recent enough to (re)send."""
    raw = str(value or "").strip()
    if not raw:
        # 날짜 없는 신호도 미전송이면 보낸다(놓치는 것보다 낫다).
        return True
    try:
        parsed = datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except ValueError:
        return True
    return today - timedelta(days=days) <= parsed <= today


def select_signals(
    rows: list[dict[str, str]],
    pushed: set[str],
    min_tier: str,
    include_all: bool,
) -> list[dict[str, str]]:
    maximum_rank = TIER_ORDER[min_tier]
    today = date.today()
    selected = [
        row
        for row in rows
        if within_lookback(row.get(DATE_COLUMN, ""), today, NOTIFY_LOOKBACK_DAYS)
        and row.get(TIER_COLUMN, "") in PUSH_TIERS
        and TIER_ORDER[row[TIER_COLUMN]] <= maximum_rank
        and row.get(SUBJECT_COLUMN, "").strip() not in {"", "미분류"}
        and (include_all or row.get(SIGNAL_ID_COLUMN, "") not in pushed)
    ]
    return sorted(
        selected,
        key=lambda row: (
            TIER_ORDER[row[TIER_COLUMN]],
            -as_int(row.get(SCORE_COLUMN, "")),
            row.get(SIGNAL_ID_COLUMN, ""),
        ),
    )


def escaped(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def summary_lines(value: Any) -> list[str]:
    summary = str(value or "").strip()
    summary = re.sub(r"\s*[|｜]\s*6축:\s*.*$", "", summary).strip()
    if not summary:
        return []
    parts = [part.strip() for part in summary.split("｜") if part.strip()]
    return [f"· {escaped(part)}" for part in parts]


def render_block(row: dict[str, str]) -> str:
    source_url = escaped(row.get(SOURCE_URL_COLUMN, ""))
    source = escaped(row.get(SOURCE_COLUMN, ""))
    published_at = escaped(row.get(PUBLISHED_AT_COLUMN, ""))
    published_suffix = f" ({published_at})" if published_at else ""
    tier = row.get(TIER_COLUMN, "")
    lines = [
        f"<b>{TIER_EMOJI.get(tier, '')} {escaped(row.get(SUBJECT_COLUMN))} · "
        f"{escaped(row.get(SCORE_COLUMN))}/12점</b>",
        f"테마 {escaped(row.get(THEME_COLUMN))} · 단계 {escaped(row.get(STAGE_COLUMN))}",
        "",
        *summary_lines(row.get(SUMMARY_COLUMN)),
    ]
    glossary = str(row.get(GLOSSARY_COLUMN, "") or "").strip()
    if glossary:
        lines.append(f"· 용어: {escaped(glossary)}")
    if source_url and source:
        lines.append(f'출처: <a href="{source_url}">{source}</a>{published_suffix}')
    elif source_url:
        lines.append(f'<a href="{source_url}">출처 보기</a>{published_suffix}')
    elif source:
        lines.append(f"출처: {source}{published_suffix}")
    return "\n".join(lines)


def compose_message(header: str, blocks: list[str]) -> str:
    separator = f"\n\n{BLOCK_SEPARATOR}\n\n"
    return f"{header}\n\n{separator.join(blocks)}"


def build_chunks(rows: list[dict[str, str]], limit: int = MESSAGE_LIMIT) -> list[tuple[str, list[str]]]:
    header = f"📡 발굴 신호 {len(rows)}건 · {date.today().isoformat()}"
    chunks: list[tuple[str, list[str]]] = []
    blocks: list[str] = []
    signal_ids: list[str] = []

    for row in rows:
        block = render_block(row)
        candidate = compose_message(header, [*blocks, block])
        if blocks and len(candidate) > limit:
            chunks.append((compose_message(header, blocks), signal_ids))
            blocks = []
            signal_ids = []
        blocks.append(block)
        signal_ids.append(row.get(SIGNAL_ID_COLUMN, ""))

    if blocks:
        chunks.append((compose_message(header, blocks), signal_ids))
    return chunks


def sector_themes() -> dict[str, str]:
    themes: dict[str, str] = {}
    for row in c.read_rows("sectors"):
        sector_id = (row.get(SECTOR_ID_COLUMN) or "").strip()
        theme = (row.get(SECTOR_THEME_COLUMN) or row.get(SECTOR_NAME_COLUMN) or "").strip()
        if sector_id and theme:
            themes[sector_id] = theme
    return themes


def review_theme(row: dict[str, str], themes: dict[str, str]) -> str:
    judgment = row.get(REVIEW_JUDGMENT_COLUMN, "") or ""
    match = re.search(r"(?:^|\|)\s*테마:\s*([^|]+)", judgment)
    if match:
        return match.group(1).strip()
    sector_id = (row.get(REVIEW_SECTOR_ID_COLUMN) or "").strip()
    return themes.get(sector_id, "미분류")


def report_line(row: dict[str, str], themes: dict[str, str]) -> str:
    return (
        f"· {escaped(row.get(REVIEW_SUBJECT_COLUMN))} | "
        f"{escaped(review_theme(row, themes))} | "
        f"근거강도 {escaped(row.get(REVIEW_STRENGTH_COLUMN))}"
    )


def build_report_chunks(
    rows: list[dict[str, str]], limit: int = MESSAGE_LIMIT
) -> list[str]:
    header = f"<b>추적 현황 {date.today().isoformat()}</b>"
    themes = sector_themes()
    grouped = {
        stage: sorted(
            [row for row in rows if row.get(REVIEW_STAGE_COLUMN, "") == stage],
            key=lambda row: (
                row.get(REVIEW_SUBJECT_COLUMN, ""),
                row.get(REVIEW_ID_COLUMN, ""),
            ),
        )
        for stage in REPORT_STAGE_ORDER
    }
    chunks: list[str] = []
    lines = [header]

    for stage in REPORT_STAGE_ORDER:
        stage_rows = grouped[stage]
        if not stage_rows:
            continue
        stage_header = f"<b>{escaped(stage)} ({len(stage_rows)})</b>"
        first_entry = report_line(stage_rows[0], themes)
        if len("\n".join([*lines, "", stage_header, first_entry])) > limit and len(lines) > 1:
            chunks.append("\n".join(lines))
            lines = [header]
        lines.extend(["", stage_header])

        for row in stage_rows:
            entry = report_line(row, themes)
            if len("\n".join([*lines, entry])) > limit and len(lines) > 3:
                chunks.append("\n".join(lines))
                lines = [header, "", stage_header]
            lines.append(entry)

    if len(lines) > 1:
        chunks.append("\n".join(lines))
    return chunks


def run_report(dry_run: bool) -> int:
    rows = [
        row
        for row in c.read_rows("investment_review_log")
        if row.get(REVIEW_STAGE_COLUMN, "") in ACTIVE_REVIEW_STAGES
    ]
    if not rows:
        console("추적 중인 아이디어 없음")
        return 0

    chunks = build_report_chunks(rows)
    if dry_run:
        console(f"[dry-run] {len(rows)} ideas in {len(chunks)} message(s)")
        for index, message in enumerate(chunks, 1):
            console(f"\n--- report {index}/{len(chunks)} ---")
            console(message)
        return 0

    token = c.load_dotenv_value("TELEGRAM_BOT_TOKEN")
    chat_id = c.load_dotenv_value("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        console("[warn] Telegram credentials missing; report skipped")
        return 0

    for index, message in enumerate(chunks, 1):
        if not send_message(token, chat_id, message):
            console(f"[warn] report chunk {index}/{len(chunks)} failed")
            continue
        console(f"[sent] report chunk {index}/{len(chunks)}")
    return 0


def send_message(token: str, chat_id: str, message: str) -> bool:
    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
    body = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    request = Request(
        endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=TELEGRAM_TIMEOUT) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        console(f"[warn] Telegram send failed: {error}")
        return False
    if result.get("ok") is not True:
        description = result.get("description", "unknown Telegram error")
        console(f"[warn] Telegram rejected message: {description}")
        return False
    return True


def main(argv: list[str]) -> int:
    args = parse_args(argv[1:])
    if args.report:
        return run_report(args.dry_run)

    state = load_state()
    pushed = set(state["pushed"])
    rows = c.read_rows("signal_log")
    selected = select_signals(rows, pushed, args.min_tier, args.all)

    if not selected:
        suffix = " (이미 전송됨)" if not args.all else ""
        console(f"신규 0건{suffix}")
        return 0

    chunks = build_chunks(selected)
    if args.dry_run:
        console(f"[dry-run] {len(selected)} signals in {len(chunks)} message(s)")
        for index, (message, _signal_ids) in enumerate(chunks, 1):
            console(f"\n--- message {index}/{len(chunks)} ---")
            console(message)
        return 0

    token = c.load_dotenv_value("TELEGRAM_BOT_TOKEN")
    chat_id = c.load_dotenv_value("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        console("[warn] Telegram credentials missing; notification skipped")
        return 0

    for index, (message, signal_ids) in enumerate(chunks, 1):
        if not send_message(token, chat_id, message):
            console(f"[warn] chunk {index}/{len(chunks)} not recorded; retry on next run")
            continue
        pushed.update(signal_id for signal_id in signal_ids if signal_id)
        state["pushed"] = sorted(pushed)
        save_state(state)
        console(f"[sent] chunk {index}/{len(chunks)}: {len(signal_ids)} signals")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
