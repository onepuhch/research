"""New-candidate alerts: news signals and screener candidates share one KST daily budget.

Selection is a slot order, not a combined investment score:
  1. human-approved recommendations (screen channel, one per approved version)
  2. then news and screener candidates alternate; the first channel alternates by
     date, and an empty channel leaves its slots to the other
  news keeps its existing priority; the screener keeps A1/B1/A2/B2 order.

Duplicates: the logical key is entity | thesis_key | event_type. Rank, collection
date and fiscal-year roll never make a new alert. A company already alerted today
(by either channel) is not alerted again that day.

Delivery ledger (data/processed/candidate_alerts.json): a slot is reserved before
sending and counts toward the daily limit while reserved or uncertain. Only a
confirmed failure is retried. A lost response is "uncertain" and never resent
automatically, because Telegram cannot guarantee exactly-once delivery.

First run: at most bootstrap_max screener candidates are sent; the other current
candidates are stored as the bootstrap set and never announced as new later.
Tracked-company risk alerts are sent by notify.py, not here, and do not use this budget.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402
import candidates  # noqa: E402
import notify  # noqa: E402

NEW = "new_discovery"
RECOMMENDATION = "recommendation"
COUNTED = ("reserved", "sent", "uncertain")
DEFAULTS = {"bootstrap_max": 1}


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
    for row in notify.select_signals(rows, pushed, notify.DEFAULT_MIN_TIER, False):
        if row.get("signal_direction") == "negative":
            continue  # risk alerts belong to notify.py
        try:
            entity, _ = promote.identity(row)
        except ValueError:
            continue
        thesis = re.sub(r"\s+", " ", (row.get("bottleneck_id") or row.get("테마") or "unclassified").casefold()).strip()
        items.append({"channel": "news", "event": NEW, "entity_id": entity, "thesis_key": thesis,
                      "key": logical_key(entity, thesis, NEW), "signal_id": row["signal_id"], "row": row})
    return items


def screen_items(index: dict) -> tuple[list[dict], list[dict]]:
    """(recommendation events, new-discovery events) that meet the data conditions."""
    if not index.get("candidates") or index.get("stale") or index.get("run_status") != "success":
        return [], []  # stale or partial collection: no new automatic alerts
    recommended, new = [], []
    for cand in index["candidates"]:
        if not cand.get("candidate_id") or cand.get("missing") or cand.get("run_quality") != "complete":
            continue
        base = {"channel": "screen", "entity_id": cand["identity"]["entity_id"], "thesis_key": cand["thesis_key"],
                "candidate_id": cand["candidate_id"], "candidate_version": cand["candidate_version"], "cand": cand}
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
           day: str, screen_cap: int | None = None) -> list[dict]:
    blocked = blocked_keys(ledger)
    bootstrap = set((ledger.get("bootstrap") or {}).get("keys", []))
    alerted_today = {e["entity_id"] for e in ledger["events"].values()
                     if e.get("day") == day and e.get("status") in COUNTED}
    news_sent = {(e["entity_id"], e["thesis_key"]) for e in ledger["events"].values()
                 if e.get("channel") == "news" and e.get("status") in COUNTED}
    chosen: list[dict] = []
    screen_used = 0

    def take(item) -> bool:
        nonlocal screen_used
        if len(chosen) >= slots or item["key"] in blocked or item["entity_id"] in alerted_today:
            return False
        if item["channel"] == "screen":
            if item["event"] == NEW and (item["key"] in bootstrap or (item["entity_id"], item["thesis_key"]) in news_sent):
                return False
            if screen_cap is not None and screen_used >= screen_cap:
                return False
            screen_used += 1
        chosen.append(item)
        alerted_today.add(item["entity_id"])
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
    block = notify.render_block(item["row"])
    return notify.split_lines([f"📡 새 발굴 신호 · {c.today()}\n\n{block}\n\n"
                               f"추적 <code>/track {candidates.esc(item['signal_id'])}</code>"])[0]


def message(item: dict) -> str:
    return screen_message(item) if item["channel"] == "screen" else news_message(item)


# ------------------------------------------------------------------ run

def event_record(item: dict, day: str) -> dict:
    return {k: item.get(k) for k in ("channel", "event", "entity_id", "thesis_key", "candidate_id",
                                     "candidate_version", "signal_id")} | {"day": day, "status": "reserved",
                                                                          "attempts": []}


def run(dry_run: bool = False) -> dict:
    day = c.today()
    ledger = load_ledger()
    notify_state = notify.load_state()
    index = candidates.load_index()
    news = news_items(c.read_rows("signal_log"), notify_state)
    recommended, screen = screen_items(index)
    slots = max(0, c.policy()["daily_candidate_limit"] - used_today(ledger, notify_state, day))
    bootstrap = ledger["bootstrap"] is None and bool(screen)
    cap = settings()["bootstrap_max"] if bootstrap else None
    # A confirmed failure keeps its key and is eligible again; it never becomes a second event.
    retry = [e for e in ledger["events"].values() if e.get("status") == "failed"]
    chosen = select(ledger, news, recommended, screen, slots, day, cap)
    report = {"slots": slots, "selected": [x["key"] for x in chosen], "bootstrap": bootstrap,
              "retry_pending": len(retry), "sent": 0, "failed": 0, "uncertain": 0}
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
    for item in chosen:
        record = ledger["events"].get(item["key"])
        if record is None or record.get("status") == "failed":
            attempts = (record or {}).get("attempts", [])
            record = {**event_record(item, day), "attempts": attempts}
        record.update(status="reserved", day=day, candidate_version=item.get("candidate_version"))
        ledger["events"][item["key"]] = record
        c.atomic_json(ledger_path(), ledger)  # reserved before the network call
        delivery = notify.deliver(token, chat_id, message(item))
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
    status = "degraded" if report["failed"] or report["uncertain"] else "success"
    c.record_run("candidate_alerts", status, **{k: v for k, v in report.items() if k != "selected"},
                 selected=len(report["selected"]))
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
