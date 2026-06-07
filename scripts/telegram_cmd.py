"""Poll Telegram commands and update the investment tracking log."""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402
import notify  # noqa: E402
import promote  # noqa: E402

OFFSET_PATH = c.DATA_DIR / "telegram_offset.json"
TELEGRAM_TIMEOUT = 20
SIGNAL_ID_PATTERN = re.compile(r"^SIG-\d+$", re.IGNORECASE)

SIGNAL_TABLE = c.table_def("signal_log")
SIGNAL_ID_COLUMN = SIGNAL_TABLE["key"]
(
    _SIGNAL_ID,
    SIGNAL_DATE_COLUMN,
    SIGNAL_SUBJECT_COLUMN,
    *_SIGNAL_REMAINING_COLUMNS,
) = SIGNAL_TABLE["columns"]

HELP_TEXT = """지원 명령어
/track ALGM - 오늘의 최신 종목 신호를 추적 등록
/track SIG-0001 - 지정한 신호를 추적 등록
/list - 활성 아이디어 목록
/help - 명령어 목록"""


def console(value: Any) -> None:
    encoding = sys.stdout.encoding or "utf-8"
    safe = str(value).encode(encoding, errors="backslashreplace").decode(encoding)
    print(safe)


def parse_args(args: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="render one command locally without Telegram or file changes",
    )
    parser.add_argument(
        "--command",
        help="command text for --dry-run (example: /help)",
    )
    parser.add_argument(
        "--poll-timeout",
        type=int,
        default=0,
        help="Telegram long-poll timeout in seconds (default: 0)",
    )
    parsed = parser.parse_args(args)
    if parsed.command and not parsed.dry_run:
        parser.error("--command requires --dry-run")
    if parsed.dry_run and not parsed.command:
        parser.error("--dry-run requires --command")
    if parsed.poll_timeout < 0 or parsed.poll_timeout > 50:
        parser.error("--poll-timeout must be between 0 and 50")
    return parsed


def load_offset() -> int:
    if not OFFSET_PATH.exists():
        return 0
    try:
        data = json.loads(OFFSET_PATH.read_text(encoding="utf-8"))
        return max(0, int(data.get("offset", 0)))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        console(f"[warn] telegram offset unreadable; starting at 0: {error}")
        return 0


def save_offset(offset: int) -> None:
    OFFSET_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = OFFSET_PATH.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"offset": max(0, int(offset))}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(OFFSET_PATH)


def telegram_request(token: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
    endpoint = f"https://api.telegram.org/bot{token}/{method}"
    request = Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=TELEGRAM_TIMEOUT + int(payload.get("timeout", 0))) as response:
        result = json.loads(response.read().decode("utf-8"))
    if result.get("ok") is not True:
        raise RuntimeError(result.get("description", f"Telegram {method} failed"))
    return result


def get_updates(token: str, offset: int, poll_timeout: int) -> list[dict[str, Any]]:
    result = telegram_request(
        token,
        "getUpdates",
        {
            "offset": offset,
            "timeout": poll_timeout,
            "allowed_updates": ["message"],
        },
    )
    updates = result.get("result", [])
    return updates if isinstance(updates, list) else []


def send_reply(token: str, chat_id: str, message: str) -> None:
    telegram_request(
        token,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
    )


def subject_matches(subject: str, query: str) -> bool:
    subject_text = str(subject or "").strip()
    query_text = str(query or "").strip()
    if not subject_text or not query_text:
        return False
    if subject_text.casefold() == query_text.casefold():
        return True
    pattern = rf"(?<![A-Z0-9]){re.escape(query_text.upper())}(?![A-Z0-9])"
    return re.search(pattern, subject_text.upper()) is not None


def find_signal(target: str) -> dict[str, str] | None:
    normalized = target.strip().upper()
    if SIGNAL_ID_PATTERN.fullmatch(normalized):
        return promote.find_signal(normalized)

    today = date.today().isoformat()
    for row in reversed(c.read_rows("signal_log")):
        if row.get(SIGNAL_DATE_COLUMN, "") != today:
            continue
        if subject_matches(row.get(SIGNAL_SUBJECT_COLUMN, ""), target):
            return row
    return None


def active_review_messages() -> list[str]:
    rows = [
        row
        for row in c.read_rows("investment_review_log")
        if row.get(notify.REVIEW_STAGE_COLUMN, "") in notify.ACTIVE_REVIEW_STAGES
    ]
    if not rows:
        return ["추적 중인 아이디어 없음"]
    return notify.build_report_chunks(rows)


def handle_track(target: str, dry_run: bool) -> list[str]:
    signal = find_signal(target)
    if signal is None:
        return [f"SIG를 찾을 수 없습니다: {html.escape(target, quote=True)}"]
    signal_id = (signal.get(SIGNAL_ID_COLUMN) or "").strip()
    if dry_run:
        return [f"[dry-run] {html.escape(target, quote=True)} → {signal_id} 승격 예정"]
    idea_id = promote.promote_signal(signal)
    return [f"{html.escape(target, quote=True)} → {idea_id} 등록됨"]


def handle_command(text: str, dry_run: bool = False) -> list[str]:
    command_text = str(text or "").strip()
    if not command_text:
        return []
    parts = command_text.split(maxsplit=1)
    command = parts[0].split("@", 1)[0].lower()
    argument = parts[1].strip() if len(parts) > 1 else ""

    if command == "/help":
        return [HELP_TEXT]
    if command == "/list":
        return active_review_messages()
    if command == "/track":
        if not argument:
            return ["사용법: /track ALGM 또는 /track SIG-0001"]
        return handle_track(argument, dry_run)
    if command.startswith("/"):
        return [f"지원하지 않는 명령어입니다.\n\n{HELP_TEXT}"]
    return []


def process_updates(token: str, allowed_chat_id: str, updates: list[dict[str, Any]]) -> int:
    processed = 0
    for update in sorted(updates, key=lambda item: int(item.get("update_id", -1))):
        update_id = int(update.get("update_id", -1))
        if update_id < 0:
            continue
        try:
            message = update.get("message", {})
            chat_id = str(message.get("chat", {}).get("id", ""))
            text = message.get("text", "")
            if chat_id != allowed_chat_id:
                console(f"[ignored] unauthorized chat_id={chat_id}")
                continue
            processed += 1
            for reply in handle_command(text):
                send_reply(token, allowed_chat_id, reply)
        except (FileNotFoundError, ValueError) as error:
            console(f"[warn] command failed for update {update_id}: {error}")
            try:
                send_reply(token, allowed_chat_id, f"명령 처리 실패: {html.escape(str(error))}")
            except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError, RuntimeError):
                pass
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError, RuntimeError) as error:
            console(f"[warn] Telegram reply failed for update {update_id}: {error}")
        finally:
            save_offset(update_id + 1)
    return processed


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or [])
    if args.dry_run:
        replies = handle_command(args.command, dry_run=True)
        for reply in replies:
            console(reply)
        return 0

    token = c.load_dotenv_value("TELEGRAM_BOT_TOKEN")
    chat_id = c.load_dotenv_value("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        console("[warn] Telegram credentials missing; command polling skipped")
        return 0

    offset = load_offset()
    try:
        updates = get_updates(token, offset, args.poll_timeout)
        processed = process_updates(token, chat_id, updates)
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError, RuntimeError) as error:
        console(f"[error] Telegram polling failed: {error}")
        return 1
    console(f"[telegram] updates={len(updates)}, authorized_messages={processed}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
