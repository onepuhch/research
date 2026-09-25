"""New-candidate alerts: news signals and screener candidates share one KST daily budget.

Selection is a slot order, not a combined investment score:
  1. human-approved recommendations (screen channel, one per approved version)
  2. then news and screener candidates alternate; the first channel alternates by
     date, and an empty channel leaves its slots to the other
  news keeps its existing priority; the screener keeps A1/B1/A2/B2 order.

Duplicates: the logical key is entity | thesis_key | event_type; that event is never
sent twice. Rank, collection date and fiscal-year roll never make a new event. A company
gets at most one alert a day (either channel), and a new-discovery alert for another
thesis or channel waits entity_new_cooldown_days (14) after that company's last
new-discovery alert. A human-approved recommendation is exempt from the 14 days only.
Entities are compared after the registry mapping (CIK and exchange:ticker of one
registered company are the same); names are never matched by similarity.

Delivery ledger (data/processed/candidate_alerts.json), per alert:
  prepare + reserve (payload hash, observation, event key, run attempt)
  -> push the reservation to the remote; if that push fails, nothing is sent and
     the reservation is released
  -> send -> record the receipt -> push the receipts.
A reservation found by a later run (the run that made it stopped, or its receipt
push failed) becomes "uncertain" and is never sent automatically: missing an alert is
preferred to sending it twice. Reserved and uncertain count toward the daily limit.
Only a confirmed failure is retried, as the same event. Exactly-once delivery is not
guaranteed. Real sends run only in the CI single-writer job.

First run: at most bootstrap_max screener candidates are sent; the other current
candidates are stored as the bootstrap set and never announced as new later.
Tracked-company risk alerts are sent by notify.py, not here, and do not use this budget.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402
import candidates  # noqa: E402
import notify  # noqa: E402

NEW = "new_discovery"
RECOMMENDATION = "recommendation"
COUNTED = ("reserved", "sent", "uncertain")
RETRYABLE = ("failed", "released")
DEFAULTS = {"bootstrap_max": 1, "entity_new_cooldown_days": 14}


def ledger_path() -> Path:
    return c.DATA_DIR / "candidate_alerts.json"


def settings() -> dict:
    return {**DEFAULTS, **c.policy().get("candidate_alerts", {})}


def load_ledger() -> dict:
    ledger = c.read_json(ledger_path(), {"events": {}, "bootstrap": None})
    if not isinstance(ledger, dict) or not isinstance(ledger.get("events"), dict):
        raise ValueError("invalid candidate alert ledger; restore it before sending")
    ledger.setdefault("bootstrap", None)
    return ledger


def logical_key(entity: str, thesis: str, event: str, detail: str = "") -> str:
    return "|".join(x for x in (entity, thesis, event, detail) if x)


def used_today(ledger: dict, notify_state: dict, day: str) -> int:
    """Slots already taken today, including legacy news candidates sent by notify.py."""
    events = sum(1 for e in ledger["events"].values() if e.get("day") == day and e.get("status") in COUNTED)
    legacy = sum(1 for signal_id, record in notify_state.get("sent", {}).items()
                 if record.get("date") == day and record.get("kind") == "candidate"
                 and not any(e.get("signal_id") == signal_id for e in ledger["events"].values()))
    return events + legacy


# ------------------------------------------------------------------ channels

def news_items(rows: list[dict], notify_state: dict) -> list[dict]:
    import promote
    pushed = set(notify_state.get("pushed", []))
    items = []
    # Every eligible signal: duplicates are removed before the daily limit, not after a top-3 cut.
    for row in notify.eligible_signals(rows, pushed, notify.DEFAULT_MIN_TIER, False)[1]:
        entity = news_entity(row)
        if not entity:
            continue
        thesis = re.sub(r"\s+", " ", (row.get("bottleneck_id") or row.get("테마") or "unclassified").casefold()).strip()
        items.append({"channel": "news", "event": NEW, "entity_id": entity, "thesis_key": thesis,
                      "key": logical_key(entity, thesis, NEW), "signal_id": row["signal_id"], "row": row})
    return items


def news_entity(row: dict) -> str | None:
    import promote
    try:
        return promote.identity(row)[0]
    except ValueError:
        return None


def recent_new_alerts(ledger: dict, notify_state: dict, signal_rows: list[dict]) -> tuple[dict[str, str], int]:
    """entity -> latest day of a new-discovery alert (sent, reserved or uncertain), and
    how many legacy notify.py sends could not be tied to a company (left unknown)."""
    recent: dict[str, str] = {}

    def note(entity, day):
        if entity and day and day > recent.get(entity, ""):
            recent[entity] = day

    for e in ledger["events"].values():
        if e.get("event") == NEW and e.get("status") in COUNTED:
            note(e.get("entity_id"), e.get("day"))
    tracked = {e.get("signal_id") for e in ledger["events"].values() if e.get("signal_id")}
    by_id = {r.get("signal_id"): r for r in signal_rows}
    unknown = 0
    for signal_id, record in notify_state.get("sent", {}).items():
        if record.get("kind") != "candidate" or signal_id in tracked:
            continue
        entity = news_entity(by_id[signal_id]) if signal_id in by_id else None
        if entity:
            note(entity, record.get("date"))
        else:
            unknown += 1
    return recent, unknown


def screen_items(index: dict) -> tuple[list[dict], list[dict]]:
    """(recommendation events, new-discovery events) that meet the data conditions."""
    if not index.get("candidates") or index.get("stale") or index.get("run_status") != "success":
        return [], []  # stale or partial collection: no new automatic alerts
    recommended, new = [], []
    for cand in index["candidates"]:
        if not cand.get("candidate_id") or cand.get("missing") or cand.get("run_quality") != "complete":
            continue
        base = {"channel": "screen", "entity_id": cand["identity"]["entity_id"], "thesis_key": cand["thesis_key"],
                "candidate_id": cand["candidate_id"], "candidate_version": cand["candidate_version"],
                "observation_id": cand.get("observation_id"), "cand": cand}
        if cand["classification"] == "recommended" and cand.get("approval"):
            version = cand["approval"]["candidate_version"]
            recommended.append({**base, "event": RECOMMENDATION,
                                "key": logical_key(base["entity_id"], base["thesis_key"], RECOMMENDATION, version)})
        if cand["classification"] in ("found", "recommended"):
            new.append({**base, "event": NEW, "key": logical_key(base["entity_id"], base["thesis_key"], NEW)})
    return recommended, new


def blocked_keys(ledger: dict) -> set[str]:
    """Keys that must not be sent again: sent, uncertain, or reserved (unknown outcome)."""
    return {k for k, e in ledger["events"].items() if e.get("status") in COUNTED}


def select(ledger: dict, news: list[dict], recommended: list[dict], screen: list[dict], slots: int,
           day: str, screen_cap: int | None = None, recent: dict[str, str] | None = None,
           cooldown_days: int = 14) -> list[dict]:
    blocked = blocked_keys(ledger)
    bootstrap = set((ledger.get("bootstrap") or {}).get("keys", []))
    recent = dict(recent or {})
    alerted_today = {e["entity_id"] for e in ledger["events"].values()
                     if e.get("day") == day and e.get("status") in COUNTED}
    alerted_today |= {entity for entity, last in recent.items() if last == day}
    chosen: list[dict] = []
    screen_used = 0

    def cooling(item) -> bool:
        last = recent.get(item["entity_id"])
        return (item["event"] == NEW and last is not None
                and (date.fromisoformat(day) - date.fromisoformat(last)).days < cooldown_days)

    def take(item) -> bool:
        nonlocal screen_used
        if len(chosen) >= slots or item["key"] in blocked or item["entity_id"] in alerted_today or cooling(item):
            return False
        if item["channel"] == "screen":
            if item["event"] == NEW and item["key"] in bootstrap:
                return False
            if screen_cap is not None and screen_used >= screen_cap:
                return False
            screen_used += 1
        chosen.append(item)
        alerted_today.add(item["entity_id"])
        if item["event"] == NEW:
            recent[item["entity_id"]] = day
        return True

    for item in recommended:
        take(item)
    queues = {"news": list(news), "screen": list(screen)}
    order = ["news", "screen"] if date.fromisoformat(day).toordinal() % 2 == 0 else ["screen", "news"]
    while len(chosen) < slots and any(queues.values()):
        for channel in order:
            while queues[channel]:
                if take(queues[channel].pop(0)):
                    break
    return chosen


# ------------------------------------------------------------------ messages

def screen_message(item: dict) -> str:
    cand = item["cand"]
    eps, price = cand["eps"], cand["price"]
    esc = candidates.esc
    title = "✅ 추적 추천 승인" if item["event"] == RECOMMENDATION else "🆕 새 발굴 후보"
    desc = cand["explanations"]["company_description_ko"]["text"] or f"회사 설명 확인 중 ({cand['identity']['ticker']})"
    price_text = (f"주가 {price['price_start_date']} → {price['price_end_date']} {price['price_pct_90']:+.1f}%"
                  if price.get("price_status") == "success" else "주가 비교 미확보")
    unknown = ("원문으로 확인한 근거를 카드에서 확인하세요" if item["event"] == RECOMMENDATION
               else "EPS 예상 상향의 사업 원인(원문 미확인)")
    return "\n".join([
        f"<b>{title} · {esc(cand['identity']['ticker'])} {esc(cand.get('name') or '')}</b>",
        esc(desc),
        f"내년 EPS 예상({esc(eps['eps_target_period'])} 회계연도 말) {esc(candidates.money(eps['eps_90d']))} → "
        f"{esc(candidates.money(eps['eps_now']))} ({esc(candidates.eps_change(eps))}), 최근 30일 상향 {eps['up30']}/하향 {eps['down30']}",
        esc(price_text),
        f"핵심 미확인: {esc(unknown)}",
        f"상세 <code>/candidate {esc(cand['candidate_id'])}</code> · 추적 <code>/track {esc(cand['candidate_id'])}</code>",
        "추적 여부를 고르기 위한 후보이며 투자 권유가 아닙니다."])


def news_message(item: dict) -> str:
    row = item["row"]
    track = f"추적 <code>/track {candidates.esc(item['signal_id'])}</code>"
    full = f"📡 새 발굴 신호 · {c.today()}\n\n{notify.render_block(row)}\n\n{track}"
    if len(full) <= notify.MESSAGE_LIMIT:
        return full
    # Too long: an explicit summary that keeps the source and the command, never a silent cut.
    esc = candidates.esc
    url = row.get("document_url") or row.get("출처URL", "")
    source = f'<a href="{esc(url)}">원문</a>' if candidates.safe_url(url) else esc(row.get("출처", ""))
    summary = str(row.get("특이값 요약", ""))[:600]
    return (f"📡 새 발굴 신호 · {c.today()} (요약본: 원문이 길어 줄임)\n\n"
            f"<b>{esc(row.get('종목/티커'))} · {esc(row.get('signal_id'))} · {esc(row.get('티어'))}</b>\n"
            f"{esc(summary)}\n출처: {source} ({esc(row.get('published_at'))})\n\n{track}")


def message(item: dict) -> str:
    return screen_message(item) if item["channel"] == "screen" else news_message(item)


# ------------------------------------------------------------------ run

def attempt_id() -> str:
    if os.environ.get("GITHUB_RUN_ID"):
        return f"{os.environ['GITHUB_RUN_ID']}-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}"
    return f"local-{uuid.uuid4().hex[:8]}"


def persist_remote(message: str) -> bool:
    """Push the ledger with the other named state. Outside the CI writer job nothing is pushed,
    so a local run can never send (its reservations are released)."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        print("[candidate_alerts] not in the CI writer job: reservations are not persisted, nothing is sent")
        return False
    import persist_state
    return persist_state.persist(message)


def quarantine(ledger: dict, me: str, now: str) -> int:
    """Reservations from another run have an unknown outcome: mark them uncertain, never resend."""
    moved = 0
    for event in ledger["events"].values():
        if event.get("status") == "reserved" and event.get("reserved_by") != me:
            event["status"] = "uncertain"
            event.setdefault("attempts", []).append({"at": now, "status": "uncertain", "message_id": None,
                                                     "error": "reservation_without_receipt"})
            moved += 1
    return moved


def event_record(item: dict, day: str) -> dict:
    return {k: item.get(k) for k in ("channel", "event", "entity_id", "thesis_key", "candidate_id",
                                     "candidate_version", "observation_id", "signal_id")} | {"day": day, "status": "reserved",
                                                                          "attempts": []}


def run(dry_run: bool = False) -> dict:
    day = c.today()
    me = attempt_id()
    ledger = load_ledger()
    quarantined = 0 if dry_run else quarantine(ledger, me, c.utc_now())
    if quarantined:
        c.atomic_json(ledger_path(), ledger)
    notify_state = notify.load_state()
    index = candidates.load_index()
    signal_rows = c.read_rows("signal_log")
    news = news_items(signal_rows, notify_state)
    recent, unknown_legacy = recent_new_alerts(ledger, notify_state, signal_rows)
    recommended, screen = screen_items(index)
    slots = max(0, c.policy()["daily_candidate_limit"] - used_today(ledger, notify_state, day))
    bootstrap = ledger["bootstrap"] is None and bool(screen)
    cap = settings()["bootstrap_max"] if bootstrap else None
    # A confirmed failure keeps its key and is eligible again; it never becomes a second event.
    retry = [e for e in ledger["events"].values() if e.get("status") in RETRYABLE]
    chosen = select(ledger, news, recommended, screen, slots, day, cap, recent,
                    settings()["entity_new_cooldown_days"])
    report = {"slots": slots, "selected": [x["key"] for x in chosen], "bootstrap": bootstrap,
              "legacy_unknown_entity": unknown_legacy,
              "retry_pending": len(retry), "quarantined": quarantined, "sent": 0, "failed": 0, "uncertain": 0}
    if dry_run:
        for item in chosen:
            print(f"--- {item['channel']} {item['key']}\n{message(item)}\n")
        return report
    if bootstrap:
        # Every candidate on today's list, alertable or not, is "already seen" from now on.
        sent_keys = {x["key"] for x in chosen}
        current = {logical_key(x["identity"]["entity_id"], x["thesis_key"], NEW)
                   for x in index["candidates"] if x.get("candidate_id")}
        ledger["bootstrap"] = {"date": day, "source_snapshot": index.get("source_snapshot"),
                               "keys": sorted(current - sent_keys)}
        c.atomic_json(ledger_path(), ledger)
    if not chosen:
        return report
    token, chat_id = c.load_dotenv_value("TELEGRAM_BOT_TOKEN"), c.load_dotenv_value("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise ValueError("Telegram credentials missing")
    texts = {item["key"]: message(item) for item in chosen}
    for item in chosen:
        record = ledger["events"].get(item["key"])
        attempts = (record or {}).get("attempts", [])
        record = {**event_record(item, day), "attempts": attempts}
        record.update(status="reserved", reserved_by=me, reserved_at=c.utc_now(),
                      payload_sha256=hashlib.sha256(texts[item["key"]].encode("utf-8")).hexdigest())
        ledger["events"][item["key"]] = c.validate_record("candidate_alert_event", record)
    c.atomic_json(ledger_path(), ledger)
    if not persist_remote(f"chore: reserve candidate alerts {day}"):
        # The remote never saw these reservations: nothing is sent and they are released.
        for item in chosen:
            record = ledger["events"][item["key"]]
            record["status"] = "released"
            record["attempts"].append({"at": c.utc_now(), "status": "not_sent", "message_id": None,
                                       "error": "reservation_not_persisted"})
        c.atomic_json(ledger_path(), ledger)
        report["reservation_persisted"] = False
        return report
    report["reservation_persisted"] = True
    for item in chosen:
        record = ledger["events"][item["key"]]
        delivery = notify.deliver(token, chat_id, texts[item["key"]])
        record["attempts"].append({"at": c.utc_now(), "status": delivery.status,
                                   "message_id": delivery.message_id, "error": delivery.error})
        record.update(status=delivery.status, message_id=delivery.message_id)
        c.atomic_json(ledger_path(), ledger)
        report[delivery.status] += 1
        if item["channel"] == "news" and delivery.status in ("sent", "uncertain"):
            # Keep the legacy notify ledger consistent so no path resends this signal.
            notify_state["pushed"] = sorted(set(notify_state["pushed"]) | {item["signal_id"]})
            notify_state["sent"][item["signal_id"]] = {"date": day, "kind": "candidate"}
            notify.save_state(notify_state)
    # If this push fails, the remote still holds the reservations, so no later run resends them.
    report["receipts_persisted"] = persist_remote(f"chore: candidate alert receipts {day}")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print the selection; send and write nothing")
    args = parser.parse_args(argv)
    try:
        report = run(args.dry_run)
    except (ValueError, OSError) as error:
        if not args.dry_run:
            c.record_run("candidate_alerts", "failed", error_type=type(error).__name__)
        print(f"[candidate_alerts] failed: {type(error).__name__}: {error}")
        return 1
    print(f"[candidate_alerts] {json.dumps(report, ensure_ascii=False)}")
    if args.dry_run:
        return 0
    trouble = report["failed"] or report["uncertain"] or report["quarantined"]
    unsaved = report.get("reservation_persisted") is False or report.get("receipts_persisted") is False
    status = "degraded" if trouble or unsaved else "success"
    c.record_run("candidate_alerts", status, **{k: v for k, v in report.items() if k != "selected"},
                 selected=len(report["selected"]))
    return 1 if report["failed"] or unsaved else 0


if __name__ == "__main__":
    raise SystemExit(main())
