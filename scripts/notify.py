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
REVIEW_ID_COLUMN = "idea_id"
REVIEW_SUBJECT_COLUMN = "종목/업종"
REVIEW_SECTOR_ID_COLUMN = "sector_id"
REVIEW_JUDGMENT_COLUMN = "당시 판단"
REVIEW_STAGE_COLUMN = "현재 단계"
REVIEW_STRENGTH_COLUMN = "근거 강도"
SECTOR_ID_COLUMN = "sector_id"
SECTOR_NAME_COLUMN = "섹터명"
SECTOR_THEME_COLUMN = "상위테마"
ACTIVE_REVIEW_STAGES = tuple(stage for stage in c.ENUMS["현재 단계"] if stage != "제외")
REPORT_STAGE_ORDER = ACTIVE_REVIEW_STAGES


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


def load_state() -> dict:
    data = c.read_json(STATE_PATH, {"pushed": [], "sent": {}})
    if not isinstance(data, dict) or not isinstance(data.get("pushed"), list) or not isinstance(data.get("sent", {}), dict):
        raise ValueError("invalid notification state; restore state before sending")
    data.setdefault("sent", {})
    return data


def save_state(state: dict) -> None:
    c.atomic_json(STATE_PATH, state)


def within_lookback(value: Any, today: date, days: int) -> bool:
    """Only valid, non-future dates qualify."""
    try:
        parsed = date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return False
    return today - timedelta(days=days) <= parsed <= today


def select_signals(
    rows: list[dict[str, str]],
    pushed: set[str],
    min_tier: str,
    include_all: bool,
) -> list[dict[str, str]]:
    maximum_rank = TIER_ORDER[min_tier]
    today = date.fromisoformat(c.today())
    tracked = {r.get("entity_id") for r in c.active_ideas() if r.get("entity_id")}
    candidates = []
    risks = []
    for row in rows:
        if row.get("data_quality") != "live" or not row.get("evidence_quote"):
            continue
        if not within_lookback(row.get(PUBLISHED_AT_COLUMN, ""), today, NOTIFY_LOOKBACK_DAYS):
            continue
        if not row.get(PUBLISHED_AT_COLUMN) or (not include_all and row.get(SIGNAL_ID_COLUMN) in pushed):
            continue
        if row.get('signal_direction') == "negative" and row.get("entity_id") in tracked:
            risks.append(row)
        elif (row.get(TIER_COLUMN) in PUSH_TIERS and TIER_ORDER[row[TIER_COLUMN]] <= maximum_rank
              and row.get("source_role") != "demand_evidence"
              and row.get('event_state') in {"contracted", "realized"}
              and row.get(SUBJECT_COLUMN, "").strip() not in {"", "미분류"}):
            candidates.append(row)
    candidates.sort(key=lambda row: (TIER_ORDER[row[TIER_COLUMN]], -as_int(row.get(SCORE_COLUMN)), row.get(SIGNAL_ID_COLUMN, "")))
    return risks + candidates[:c.policy()["daily_candidate_limit"]]


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
    source_url = escaped(row.get("document_url") or row.get(SOURCE_URL_COLUMN, ""))
    source = escaped(row.get(SOURCE_COLUMN, ""))
    published_at = escaped(row.get(PUBLISHED_AT_COLUMN, ""))
    published_suffix = f" ({published_at})" if published_at else ""
    tier = row.get(TIER_COLUMN, "")
    lines = [
        f"<b>{TIER_EMOJI.get(tier, '')} {escaped(row.get(SUBJECT_COLUMN))} · "
        f"{escaped(row.get(SCORE_COLUMN))}/12점</b>",
        f"{escaped(row.get(SIGNAL_ID_COLUMN))} · 검토 우선순위 {escaped(tier)} · {escaped(row.get(THEME_COLUMN))}",
        f"근거: {escaped(row.get('event_state'))} · 변화 방향: {escaped(row.get('signal_direction'))}",
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
    header = f"📡 발굴 신호 {len(rows)}건 · {c.today()}"
    chunks: list[tuple[str, list[str]]] = []
    blocks: list[str] = []
    signal_ids: list[str] = []

    for row in rows:
        block = render_block(row)
        if len(compose_message(header, [block])) > limit:
            # Escape after truncation, so HTML entities/tags cannot be cut in half.
            block = escaped(f"{row.get(SIGNAL_ID_COLUMN, '')} {row.get(SUBJECT_COLUMN, '')}"[:100])
            block += "\n" + escaped(str(row.get(SUMMARY_COLUMN, ""))[:max(0, (limit - len(header) - 700) // 6)])
            block += "\n상세 근거는 signal_log에서 해당 ID로 확인하세요."
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
    import review
    check = review.inspect_idea(row)
    return (f"· {escaped(str(row.get(REVIEW_SUBJECT_COLUMN, ''))[:60])} | {escaped(row.get('사업 단계', '미확인'))} | "
            f"{escaped(row.get('근거 수준', '가설'))}\n"
            f"  최근 점검 {escaped(row.get('최근 점검일'))} / 다음 {escaped(check['due_date'])}\n"
            f"  변화: {escaped(row.get('판단 변화'))} · {escaped(row.get('변경 사유', '')[:300])}\n"
            f"  부족 지표: {escaped((', '.join(check['missing']) or '없음')[:100])} · "
            f"반증: {escaped(('; '.join(k + ': ' + v for k, v in check['rules']) or '규칙 미등록')[:150])}")


def build_report_chunks(
    rows: list[dict[str, str]], limit: int = MESSAGE_LIMIT
) -> list[str]:
    header = f"<b>추적 현황 {c.today()}</b>"
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
    rows = c.active_ideas()
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
        console("[error] Telegram credentials missing; report FAILED")
        return 1

    failures = 0
    for index, message in enumerate(chunks, 1):
        if not send_message(token, chat_id, message):
            failures += 1
            console(f"[warn] report chunk {index}/{len(chunks)} failed")
            continue
        console(f"[sent] report chunk {index}/{len(chunks)}")
    if failures:
        console(f"[error] {failures}/{len(chunks)} report chunk(s) failed")
        return 1
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
        console(f"[warn] Telegram send failed: {type(error).__name__}")
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

    try:
        state = load_state()
    except (ValueError, OSError):
        console("[error] notification state unreadable; restore state before sending")
        return 1
    pushed = set(state["pushed"])
    rows = c.read_rows("signal_log")
    selected = select_signals(rows, pushed, args.min_tier, args.all)

    if not args.all:
        used = sum(1 for record in state["sent"].values()
                   if record.get("date") == c.today() and record.get("kind") == "candidate")
        allowance = max(0, c.policy()["daily_candidate_limit"] - used)
        risks = [r for r in selected if r.get("signal_direction") == "negative"]
        selected = risks + [r for r in selected if r.get("signal_direction") != "negative"][:allowance]
    if not selected:
        console("전송 조건을 충족하는 신규 신호 0건")
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
        console("[error] Telegram credentials missing; notification FAILED")
        return 1

    failures = 0
    for index, (message, signal_ids) in enumerate(chunks, 1):
        if not send_message(token, chat_id, message):
            failures += 1
            console(f"[warn] chunk {index}/{len(chunks)} not recorded; retry on next run")
            continue
        pushed.update(signal_id for signal_id in signal_ids if signal_id)
        state["pushed"] = sorted(pushed)
        for signal_id in signal_ids:
            row = next(r for r in selected if r[SIGNAL_ID_COLUMN] == signal_id)
            state["sent"][signal_id] = {"date": c.today(), "kind": "risk" if row.get("signal_direction") == "negative" else "candidate"}
        save_state(state)
        console(f"[sent] chunk {index}/{len(chunks)}: {len(signal_ids)} signals")
    if failures:
        # 미전송분은 날짜 재시도로 복구되지만, 지속 장애는 Actions 빨간불로 노출한다.
        console(f"[error] {failures}/{len(chunks)} chunk(s) failed to send")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
