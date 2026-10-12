"""Poll Telegram commands and update the investment tracking log."""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402
import candidate_feedback as fb  # noqa: E402
import candidates  # noqa: E402
import notify  # noqa: E402
import promote  # noqa: E402

OFFSET_PATH = c.DATA_DIR / "telegram_offset.json"
TELEGRAM_TIMEOUT = 20
SIGNAL_ID_PATTERN = re.compile(r"^SIG-\d+$", re.IGNORECASE)

SIGNAL_TABLE = c.table_def("signal_log")
SIGNAL_ID_COLUMN = SIGNAL_TABLE["key"]
SIGNAL_DATE_COLUMN = "날짜"
SIGNAL_SUBJECT_COLUMN = "종목/티커"


HELP_TEXT = """지원 명령어
/screen - 최신 EPS 상향 발굴 후보 상위 5개
/candidate CAN-0123456789ABCDEF - 후보 카드 상세
/track ALGM - 최근 14일의 최신 종목 신호를 추적 등록
/track SIG-0001 - 지정한 신호를 추적 등록
/track CAN-0123456789ABCDEF - 발굴 후보를 추적 등록
/list - 활성 아이디어 목록
/history CRDO - 같은 정의의 날짜별 숫자 관측
/data - 데이터 누적 현황
/help - 명령어 목록

후보 알림에 답장: 추적 · 관심없음 · 보류 · 자세히 (한 낱말만)"""

REPLY_GUIDE = ("후보 알림 메시지(🆕 새 발굴 후보 등)에 답장으로 '추적', '관심없음', '보류', '자세히' 중 "
               "한 낱말만 보내 주세요.")


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
        "--reply-to",
        type=int,
        help="with --dry-run: treat --command as a reply to this alert message_id",
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
    if parsed.reply_to is not None and not parsed.dry_run:
        parser.error("--reply-to requires --dry-run")
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
    if os.environ.get("RESEARCH_DISABLE_SEND") == "1":
        raise RuntimeError("sending disabled for this run")
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

    today = date.fromisoformat(c.today())
    for row in reversed(c.read_signals()):
        if not notify.within_lookback(row.get(SIGNAL_DATE_COLUMN), today, c.policy()["signal_lookback_days"]):
            continue
        if subject_matches(row.get(SIGNAL_SUBJECT_COLUMN, ""), target):
            return row
    return None


def active_review_messages() -> list[str]:
    rows = c.active_ideas()
    if not rows:
        return ["추적 중인 아이디어 없음"]
    return notify.build_report_chunks(rows)


def track_result(cand: dict, tracked_before=promote.UNKNOWN) -> dict:
    """promote.track_candidate. Every input refusal is already a rejected result with its code; any
    other ValueError (a damaged cell, a ledger or schema the write refuses) is a state error, kept for
    retry instead of being answered as a rejection."""
    try:
        return promote.track_candidate(cand, tracked_before=tracked_before)
    except ValueError as error:
        raise promote.TrackStateError(f"tracking state unreadable: {type(error).__name__}") from error


def track_text(cand: dict, state: str, result: dict) -> str:
    ticker = html.escape(cand["identity"]["ticker"])
    if result["outcome"] == "rejected":
        if result["reason_code"] == "observation_too_old":
            return f"{ticker} 후보 관측이 오래됐습니다. /screen으로 최신 결과를 본 뒤 다시 등록해 주세요."
        if result["reason_code"] == "capacity":
            return f"활성 추적이 {c.policy()['max_active_ideas']}개로 가득 찼습니다. 기존 추적을 정리한 뒤 다시 등록해 주세요."
        if result["reason_code"] in ("invalid_record", "observation_in_future"):
            return f"{ticker} 후보 카드의 관측 시각이 올바르지 않아 등록하지 않았습니다. /screen으로 최신 결과를 확인해 주세요."
        return f"{ticker} 후보는 식별·통화 확인이 부족해 등록하지 않았습니다. 다음 스크린 후 다시 시도해 주세요."
    idea_id = result["idea_id"]
    note = " (최신 목록에는 없는 후보)" if state == "not_current" else ""
    if os.environ.get("DAILY_MODE") in ("auto", "daily"):
        when = "이번 일간 실행에서 EPS 예상·주가·분기 숫자 수집을 시작합니다."
    else:
        when = "다음 auto 일간 실행(09:17 KST 무렵)에서 EPS 예상·주가·분기 숫자 수집을 시작합니다."
    return (f"추적 등록 완료: {ticker} → {html.escape(idea_id)}{note}\n{when} "
            "자료 확보 여부는 /data로 확인하세요. 추적 선택은 검증 완료나 매수 추천이 아닙니다.")


def handle_track_candidate(cid: str, dry_run: bool) -> list[str]:
    cand, state = candidates.find(cid)
    if state == "unknown":
        return [f"없는 후보 ID입니다: {html.escape(cid)}. /screen으로 최신 목록을 확인해 주세요."]
    ticker = html.escape(cand["identity"]["ticker"])
    if dry_run:
        return [f"[dry-run] {html.escape(cid)} ({ticker}) 추적 등록 예정"]
    return [track_text(cand, state, track_result(cand))]


def handle_reply(item: dict, update_id: int, dry_run: bool = False) -> list[str]:
    """A fixed-word reply to a candidate alert (candidate_feedback.py). The judgment is stored before
    anything else; a track reply stores its result as a separate event; nothing is guessed."""
    action = item.get("action")
    if action not in fb.LABELS:
        return [HELP_TEXT]
    # The CLI dry-run has no bot mark or times: its lookup is diagnostic and never records.
    target = (fb.lookup_unverified(item.get("reply_to_message_id")) if dry_run else
              fb.resolve(item.get("reply_to_message_id"), item.get("reply_to_date"), item.get("reply_to_from_bot")))
    if target["state"] in ("not_alert", "ambiguous"):
        return [f"후보 알림에 대한 답장이 아니어서 판단을 기록하지 않았습니다. {REPLY_GUIDE}"]
    if target["state"] == "unverified":
        return ["답장 대상 메시지의 발신·시각 정보를 확인하지 못해 판단을 기록하지 않았습니다. "
                "알림에 적힌 /candidate 또는 /track 명령을 후보 ID와 함께 그대로 보내 주세요."]
    if target["state"] == "no_candidate":
        return ["후보 ID가 없는 알림(뉴스 신호 등)이라 답장 판단을 기록하지 않았습니다. "
                "알림에 적힌 /track 명령을 그대로 보내 주세요."]
    if target["state"] == "unconfirmed":
        return ["이 알림은 발송 확인이 끝나지 않은 상태라 답장으로 처리하지 않았습니다. "
                "알림에 적힌 /candidate 또는 /track 명령을 그대로 보내 주세요."]
    key, event = target["key"], target["event"]
    cid = event["candidate_id"]
    ticker = html.escape(key.split("|", 1)[0].rsplit(":", 1)[-1])
    disputed = fb.disputed(key)
    cand, state = candidates.find(cid)
    label = fb.LABELS[action]
    if dry_run:
        return [f"[dry-run·진단: 봇·시각 미검증 조회] {ticker} 알림({html.escape(key)}) 답장 '{label}' 기록 예정"
                + (f" · 제공처 값 불일치 {', '.join(disputed)}" if disputed else "")]
    stored, _ = fb.append_once({
        "kind": "reply", "scope": fb.SCOPE, "update_id": update_id,
        "message_at": fb.iso(item.get("message_date")), "received_at": item.get("received_at"),
        "event_key": key, "candidate_id": cid, "candidate_version": event.get("candidate_version"),
        "reply_to_message_id": item["reply_to_message_id"], "action": action, "source": fb.SOURCE,
        "disputed_source": disputed,
        "tracked_before": promote.active_candidate_idea(cand) if action == "track" and cand else None})
    if action == "detail":
        if cand is None:
            return [f"없는 후보 ID입니다: {html.escape(cid)}. /screen으로 최신 목록을 확인해 주세요."]
        # A version covers description, sources and context too, and not every price move: say only
        # whether the card is the same, never that the numbers did or did not change.
        same = cand.get("candidate_version") == event.get("candidate_version")
        note = (f"ℹ️ 알림 당시 버전 {html.escape(str(event.get('candidate_version')))} · 최신 카드 버전 "
                f"{html.escape(str(cand.get('candidate_version')))} "
                + ("(알림 당시와 같은 카드 버전입니다)" if same else "(알림 이후 카드 내용이 변경되었습니다)"))
        if disputed:
            note += f"\n⚠️ 제공처 값 불일치로 표시된 알림입니다({html.escape(', '.join(disputed))})."
        replies = candidates.telegram_candidate(cid)
        return notify.split_lines([note + "\n\n" + replies[0], *replies[1:]])
    if action in ("dismiss", "hold"):
        return [f"판단 기록: {ticker} · {label}. 추적 등록과 알림 예약은 바꾸지 않습니다."
                + (f" (제공처 값 불일치 알림: {html.escape(', '.join(disputed))})" if disputed else "")
                + " 관심 기록이며 투자 판단의 정답으로 쓰지 않습니다."]
    # track: the result is its own event; a stored result is reused, so a retry never registers twice.
    operation = fb.operation_key(update_id)
    done = fb.find(fb.load(), "track_result", operation_key=operation)
    if done is None:
        if disputed:
            result = {"outcome": "rejected", "reason_code": "disputed_source", "idea_id": None}
        elif cand is None:
            result = {"outcome": "rejected", "reason_code": "unknown_candidate", "idea_id": None}
        else:
            result = track_result(cand, stored.get("tracked_before"))
        done, _ = fb.append_once({
            "kind": "track_result", "scope": fb.SCOPE, "update_id": update_id, "operation_key": operation,
            "event_key": key, "candidate_id": cid, **result,
            "processed_version": (cand or {}).get("candidate_version"), "candidate_state": state,
            "at": c.utc_now()})
    if done["reason_code"] == "disputed_source":
        return [f"{ticker} 알림은 제공처 값 불일치({html.escape(', '.join(disputed))})로 표시되어 답장으로는 추적 "
                f"등록하지 않았습니다. 최신 상세 <code>/candidate {html.escape(cid)}</code>를 확인한 뒤 "
                f"<code>/track {html.escape(cid)}</code>로 직접 선택해 주세요."]
    if done["reason_code"] == "unknown_candidate":
        return [f"없는 후보 ID입니다: {html.escape(cid)}. /screen으로 최신 목록을 확인해 주세요."]
    if done["outcome"] == "already_tracked":
        return [f"이미 추적 중입니다: {ticker} → {html.escape(done['idea_id'])}. 새로 등록하지 않았습니다."]
    return [track_text(cand, state, done)]


def handle_track(target: str, dry_run: bool) -> list[str]:
    cid = candidates.normalize_id(target)
    if cid:
        return handle_track_candidate(cid, dry_run)
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
    if command == "/screen":
        return notify.split_lines(candidates.telegram_screen())
    if command == "/candidate":
        return notify.split_lines(candidates.telegram_candidate(argument))
    if command == "/list":
        return active_review_messages()
    if command == "/data":
        import data_history
        return data_history.telegram()
    if command == "/history":
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9.-]{0,9}", argument):
            return ["사용법: /history CRDO"]
        import data_history
        return data_history.telegram(argument.upper())
    if command == "/track":
        if not argument:
            return ["사용법: /track ALGM, /track SIG-0001 또는 /track CAN-0123456789ABCDEF"]
        return handle_track(argument, dry_run)
    if command.startswith("/"):
        return [f"지원하지 않는 명령어입니다.\n\n{HELP_TEXT}"]
    return []


def process_updates(token: str, allowed_chat_id: str, updates: list[dict[str, Any]]) -> int:
    # Persist incoming commands before acknowledging Telegram offsets. Retrying uses stable IDs.
    path = c.DATA_DIR / "command_queue.json"
    queue = c.read_json(path, {})
    highest = load_offset()
    for update in updates:
        update_id = int(update.get("update_id", -1))
        if update_id < 0:
            continue
        highest = max(highest, update_id + 1)
        message = update.get("message", {})
        if str(message.get("chat", {}).get("id", "")) != allowed_chat_id:
            continue
        key = str(update_id)
        if key not in queue:
            raw = str(message.get("text", "")).strip()
            replied = message.get("reply_to_message")
            action = fb.reply_action(raw) if isinstance(replied, dict) else None
            if action and isinstance(replied.get("message_id"), int):
                # A reply keeps only the action and the replied message's reference (no text of either).
                sender = replied.get("from") or {}
                queue[key] = {"text": "/reply", "action": action, "reply_to_message_id": replied["message_id"],
                              "reply_to_date": replied.get("date") if isinstance(replied.get("date"), int) else None,
                              "reply_to_from_bot": sender.get("is_bot") if isinstance(sender.get("is_bot"), bool) else None,
                              "message_date": message.get("date") if isinstance(message.get("date"), int) else None,
                              "status": "pending", "received_at": c.utc_now()}
                continue
            parts = raw.split(maxsplit=1)
            command = parts[0].split("@", 1)[0].lower() if parts else ""
            arg = parts[1].strip().upper() if len(parts) > 1 else ""
            if command == "/track" and candidates.normalize_id(arg):
                safe_command = f"/track {candidates.normalize_id(arg)}"
            elif command == "/track" and re.fullmatch(r"(?:SIG-\d{1,12}|[A-Z][A-Z0-9.-]{0,9})", arg):
                safe_command = f"/track {arg}"
            elif command == "/history" and re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", arg):
                safe_command = f"/history {arg}"
            elif command == "/candidate":
                # A malformed ID is kept only as a marker, so the reply can say the format is wrong.
                safe_command = f"/candidate {candidates.normalize_id(arg) or '?'}"
            elif command in {"/list", "/help", "/data", "/screen"}:
                safe_command = command
            else:
                safe_command = "/help"
            # Only the supported command vocabulary is persisted, never arbitrary chat text.
            queue[key] = {"text": safe_command, "status": "pending", "received_at": c.utc_now()}
    c.atomic_json(path, queue)
    save_offset(highest)
    processed = 0
    failures = 0
    for key, item in sorted(queue.items(), key=lambda pair: int(pair[0])):
        if item.get("status") == "done":
            continue
        try:
            if item.get("status") != "reply_pending":
                try:
                    if item.get("text") == "/reply":
                        replies = handle_reply(item, int(key))
                    else:
                        replies = handle_command(item.get("text", ""))
                except json.JSONDecodeError:
                    raise  # a damaged state file is kept for retry, never answered as an input error
                except ValueError as error:
                    # A permanent user-input error is a reply, not a poison retry loop.
                    replies = ["명령을 처리할 수 없습니다. 신호 ID와 추적 제한을 확인해주세요."]
                item.update(status="reply_pending", replies=replies)
                c.atomic_json(path, queue)
            while item.get("replies"):
                send_reply(token, allowed_chat_id, item["replies"][0])
                item["replies"].pop(0)
                c.atomic_json(path, queue)
            item.update(status="done", completed_at=c.utc_now())
            # Completed text and replies are not needed in the repository.
            item.pop("text", None)
            item.pop("action", None)
            processed += 1
        except (OSError, RuntimeError, TimeoutError, json.JSONDecodeError) as error:
            item["last_error_type"] = type(error).__name__
            failures += 1
        c.atomic_json(path, queue)
    c.record_run("commands", "degraded" if failures else "success", processed=processed, failed=failures)
    if failures:
        raise RuntimeError("commands retained for retry")
    return processed


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or [])
    if args.dry_run and args.reply_to is not None:
        action = fb.reply_action(args.command)
        replies = (handle_reply({"action": action, "reply_to_message_id": args.reply_to}, 0, dry_run=True)
                   if action else [HELP_TEXT])
        for reply in replies:
            console(reply)
        return 0
    if args.dry_run:
        replies = handle_command(args.command, dry_run=True)
        for reply in replies:
            console(reply)
        return 0

    token = c.load_dotenv_value("TELEGRAM_BOT_TOKEN")
    chat_id = c.load_dotenv_value("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        c.record_run("commands", "unavailable", reason="credentials_missing")
        console("[error] Telegram credentials missing")
        return 1

    offset = load_offset()
    try:
        updates = get_updates(token, offset, args.poll_timeout)
        processed = process_updates(token, chat_id, updates)
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError, RuntimeError) as error:
        c.record_run("commands", "failed", error_type=type(error).__name__)
        console(f"[error] Telegram polling failed: {type(error).__name__}")
        return 1
    console(f"[telegram] updates={len(updates)}, authorized_messages={processed}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
