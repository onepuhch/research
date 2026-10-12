"""User reactions to candidate alerts (V1): a fixed-word reply to a sent alert, kept append-only.

A reply to a candidate alert with one exact word (spaces around it removed) is a reaction:
  추적 or /track (no argument)          -> track intent, then the existing /track rule; its result is
                                           a separate event (success / already_tracked / rejected)
  관심없음 or 패스                       -> dismiss
  보류                                   -> hold
  자세히 or /candidate (no argument)    -> detail: a lookup, not a judgment
Dismiss and hold change nothing else: tracking, alert slots and schedules stay as they are.

The replied-to message is matched only to a receipt in candidate_alerts.json: a sent event with a
candidate_id, exactly one event holding that message_id (in its receipt or attempts), a replied
message Telegram marks as sent by a bot, and the replied message's own time (not the reply's) within
MATCH_WINDOW_S of the receipt time, so a reply days later still links. If the bot mark, the replied
message's time or the receipt time is missing or unreadable, nothing is linked (unverified) and the
reply points to the ID commands; nothing is guessed. The window is a cross-check of the same message,
not proof of which bot sent it: receipts carry no chat ID; every alert goes to the one allowed chat,
kept here under the fixed alias SCOPE (the chat ID is never written), and after a chat or bot change
old receipts are not linked by this rule (a scope change is a checked migration). lookup_unverified
is the CLI dry-run's diagnostic lookup without these checks; it never records. Replies to anything else (command replies, correction notice 168, news
alerts without a candidate_id, ambiguous matches) record nothing and ask for a reply to the alert
itself. An event that is not 'sent' (uncertain, failed, reserved) is never changed by a reply and gets
no judgment or tracking; the reply points to the /candidate and /track commands. The alert's text and
ticker are never read to guess a candidate.

An alert listed in provider_inconsistencies.json keeps its judgment with disputed_source; a track
reply to it is not registered (reason_code disputed_source): the user checks the latest card and
uses /track with the ID.

Store (data/processed/candidate_feedback.json, events only added, never edited):
  reply        scope, update_id, message_at, received_at, event_key, candidate_id, candidate_version
               (at sending), reply_to_message_id, action, source, disputed_source, tracked_before
  track_result scope, update_id, operation_key, event_key, candidate_id, outcome, reason_code,
               idea_id, processed_version, candidate_state, at
One reply event per scope+update_id and one result per operation_key, so reading the same update
again adds nothing. No chat text, user name or key is stored. The latest judgment of an alert is its
track/dismiss/hold reply with the highest update_id; detail never replaces it.

A reaction is a measure of interest and use. It is not a label for market under-reaction, returns or
evidence accuracy, no reply is not a rejection, and nothing here changes card order, recommendations,
alert selection or any model.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import common as c

VERSION = 1
SCOPE = "telegram:primary"
SOURCE = "telegram_reply"
WORDS = {"추적": "track", "관심없음": "dismiss", "패스": "dismiss", "보류": "hold", "자세히": "detail"}
COMMAND_WORDS = {"/track": "track", "/candidate": "detail"}  # only without an argument, only as a reply
VERDICTS = ("track", "dismiss", "hold")
LABELS = {"track": "추적", "dismiss": "관심없음", "hold": "보류", "detail": "자세히"}
MATCH_WINDOW_S = 600


class FeedbackStoreError(RuntimeError):
    """The store or the alert ledger cannot be read: the command is kept for retry, never reset."""


def path() -> Path:
    return c.DATA_DIR / "candidate_feedback.json"


def reply_action(text: str) -> str | None:
    """The action of a reply text, or None: exact words only, no guessing from free text."""
    word = str(text or "").strip()
    if word in WORDS:
        return WORDS[word]
    return COMMAND_WORDS.get(word.split("@", 1)[0].lower()) if " " not in word else None


def load() -> dict:
    try:
        store = c.read_json(path(), None)
    except (OSError, ValueError) as error:
        raise FeedbackStoreError(f"candidate feedback unreadable: {type(error).__name__}") from error
    if store is None:
        return {"version": VERSION, "events": []}
    if not isinstance(store, dict) or not isinstance(store.get("events"), list):
        raise FeedbackStoreError("candidate feedback invalid; restore it before recording")
    return store


def event_id(event: dict) -> tuple:
    if event.get("kind") == "track_result":
        return ("track_result", event.get("operation_key"))
    return (event.get("kind"), event.get("scope"), event.get("update_id"))


def find(store: dict, kind: str, **match) -> dict | None:
    return next((e for e in store["events"] if e.get("kind") == kind
                 and all(e.get(k) == v for k, v in match.items())), None)


def append_once(event: dict) -> tuple[dict, bool]:
    """(stored event, added). An event already stored under the same key is returned unchanged."""
    store = load()
    key = event_id(event)
    for existing in store["events"]:
        if event_id(existing) == key:
            return existing, False
    store["events"].append(c.validate_record("candidate_feedback_event", event))
    c.atomic_json(path(), store)
    return event, True


def operation_key(update_id: int) -> str:
    return f"{SCOPE}:{update_id}:track"


def iso(unix: int | None) -> str | None:
    if not isinstance(unix, int) or isinstance(unix, bool):
        return None
    return datetime.fromtimestamp(unix, timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ the replied-to alert

def alert_ledger() -> dict:
    import candidate_alerts
    try:
        return candidate_alerts.load_ledger()
    except (OSError, ValueError) as error:
        raise FeedbackStoreError(f"candidate alert ledger unreadable: {type(error).__name__}") from error


def receipt_time(event: dict, message_id: int) -> str | None:
    attempt = next((a for a in event.get("attempts") or [] if a.get("message_id") == message_id), None)
    return (attempt or {}).get("at")


def matches(message_id: int) -> dict:
    """The receipt holding message_id: {"state": not_alert | ambiguous | None, "key", "event"}."""
    if not isinstance(message_id, int) or isinstance(message_id, bool):
        return {"state": "not_alert", "key": None, "event": None}
    hits = [(k, e) for k, e in alert_ledger()["events"].items()
            if e.get("message_id") == message_id
            or any(a.get("message_id") == message_id for a in e.get("attempts") or [])]
    if len(hits) != 1:
        return {"state": "ambiguous" if hits else "not_alert", "key": None, "event": None}
    return {"state": None, "key": hits[0][0], "event": hits[0][1]}


def linkable(found: dict) -> dict:
    event = found["event"]
    if event.get("status") != "sent":
        return {**found, "state": "unconfirmed"}
    if not event.get("candidate_id"):
        return {**found, "state": "no_candidate"}
    return {**found, "state": "ok"}


def parse_time(value: str | None) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None
    return parsed if parsed and parsed.tzinfo else None


def resolve(message_id: int, message_date: int | None = None, from_bot: bool | None = None) -> dict:
    """{"state": ok | not_alert | ambiguous | unverified | no_candidate | unconfirmed, "key", "event"}.

    Used for every real reply: the bot mark and both times are required, never assumed."""
    if from_bot is False:
        return {"state": "not_alert", "key": None, "event": None}
    found = matches(message_id)
    if found["state"]:
        return found
    sent_at = parse_time(receipt_time(found["event"], message_id))
    replied_at = parse_time(iso(message_date))
    if from_bot is not True or sent_at is None or replied_at is None:
        return {"state": "unverified", "key": None, "event": None}
    if abs((sent_at - replied_at).total_seconds()) > MATCH_WINDOW_S:
        return {"state": "ambiguous", "key": None, "event": None}  # same number, another message
    return linkable(found)


def lookup_unverified(message_id: int) -> dict:
    """CLI dry-run diagnostics only: the receipt by message_id alone, without the bot and time checks."""
    found = matches(message_id)
    return found if found["state"] else linkable(found)


def disputed(event_key: str) -> list[str]:
    """Ids of recorded provider inconsistencies that list this alert."""
    try:
        entries = c.read_json(c.DATA_DIR / "provider_inconsistencies.json", {}).get("entries", [])
    except (OSError, ValueError) as error:
        raise FeedbackStoreError(f"provider inconsistencies unreadable: {type(error).__name__}") from error
    return sorted({e["id"] for e in entries if any(a.get("key") == event_key for a in e.get("affected_alerts", []))})


# ------------------------------------------------------------------ views

def latest_by_alert(store: dict) -> dict[str, dict]:
    """event_key -> the latest track/dismiss/hold reply (highest update_id)."""
    latest: dict[str, dict] = {}
    for e in store["events"]:
        if e.get("kind") == "reply" and e.get("action") in VERDICTS:
            if e["event_key"] not in latest or e["update_id"] > latest[e["event_key"]]["update_id"]:
                latest[e["event_key"]] = e
    return latest


def card_note(cand: dict) -> str | None:
    """One card line: the latest judgment for this candidate (company + thesis), with its date and the
    version it was given on. An earlier version's judgment is not shown as one on this version."""
    cid = cand.get("candidate_id")
    if not cid:
        return None
    try:
        store = load()
    except FeedbackStoreError:
        return "사용자 판단 기록을 읽지 못했습니다(기록 파일 확인 필요)."
    replies = [e for e in latest_by_alert(store).values() if e.get("candidate_id") == cid]
    if not replies:
        return None
    last = max(replies, key=lambda e: e["update_id"])
    day = (last.get("message_at") or last.get("received_at") or "")[:10]
    same = last.get("candidate_version") == cand.get("candidate_version")
    version = "이 카드와 같은 버전" if same else f"알림 당시 버전 {last.get('candidate_version')}, 이 카드와 다른 버전"
    note = f"사용자 판단: {LABELS[last['action']]} ({day}, {version})"
    if last.get("disputed_source"):
        note += f" · 제공처 값 불일치 알림({', '.join(last['disputed_source'])})"
    return note + ". 관심 기록이며 검증 결과가 아닙니다."


def summary(store: dict | None = None, ledger: dict | None = None) -> dict:
    """Counts over the supported population: sent candidate alerts (with a candidate_id). Disputed
    alerts are counted apart. One alert with several replies counts once for its latest judgment."""
    store = store or load()
    ledger = ledger or alert_ledger()
    population = {k: e for k, e in ledger["events"].items() if e.get("status") == "sent" and e.get("candidate_id")}
    flagged = {k for k in population if disputed(k)}
    latest = latest_by_alert(store)
    details = [e for e in store["events"] if e.get("kind") == "reply" and e.get("action") == "detail"]
    detailed = {e["event_key"] for e in details}
    results = [e for e in store["events"] if e.get("kind") == "track_result"]

    def part(keys: set[str]) -> dict:
        verdicts = {v: 0 for v in VERDICTS}
        for k in keys:
            if k in latest:
                verdicts[latest[k]["action"]] += 1
        none = [k for k in keys if k not in latest]
        return {"alerts": len(keys), "companies": len({population[k]["entity_id"] for k in keys}),
                "latest": verdicts, "no_judgment": len(none),
                "detail_only": len([k for k in none if k in detailed]),
                "judged_companies": len({population[k]["entity_id"] for k in keys if k in latest})}

    outcomes: dict[str, int] = {}
    reasons: dict[str, int] = {}
    for r in results:
        outcomes[r["outcome"]] = outcomes.get(r["outcome"], 0) + 1
        if r.get("reason_code"):
            reasons[r["reason_code"]] = reasons.get(r["reason_code"], 0) + 1
    return {"normal": part(set(population) - flagged), "disputed": part(flagged),
            "detail_events": len(details),
            "track_requests": len([e for e in store["events"] if e.get("kind") == "reply" and e.get("action") == "track"]),
            "track_outcomes": outcomes, "track_reasons": reasons}


def render_lines() -> list[str]:
    try:
        s = summary()
    except FeedbackStoreError as error:
        return ["## 사용자 반응·활용", "", f"기록을 읽지 못했습니다: {error}", ""]
    n, d = s["normal"], s["disputed"]
    v = n["latest"]
    lines = ["## 사용자 반응·활용 (알림 답장 기록)", "",
             "모집단은 후보 ID가 있는 발송 완료 알림입니다. 판단은 관심·활용의 기록이며 정확도·적중률·시장 미반영의 "
             "정답이 아닙니다. 무응답은 거절로 세지 않습니다.", "",
             f"- 알림 {n['alerts']}건 (기업 {n['companies']}곳): 최신 판단 추적 {v['track']} · 관심없음 {v['dismiss']} · "
             f"보류 {v['hold']} · 무판단 {n['no_judgment']}(그중 상세 조회만 {n['detail_only']}) · 판단한 기업 {n['judged_companies']}곳",
             f"- 상세 조회 답장 {s['detail_events']}건(판단 아님)",
             f"- 추적 답장 {s['track_requests']}건 → 결과: "
             + (", ".join(f"{k} {v2}" for k, v2 in sorted(s["track_outcomes"].items())) or "없음")
             + (f" (거절 사유: {', '.join(f'{k} {v2}' for k, v2 in sorted(s['track_reasons'].items()))})"
                if s["track_reasons"] else "")]
    if d["alerts"]:
        dv = d["latest"]
        lines.append(f"- 제공처 값 불일치 알림(별도) {d['alerts']}건: 추적 {dv['track']} · 관심없음 {dv['dismiss']} · "
                     f"보류 {dv['hold']} · 무판단 {d['no_judgment']}")
    return lines + [""]
