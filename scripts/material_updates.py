"""Re-review changes of known candidates (P2): 'material_update', an event apart from the first discovery.

A known candidate is one that is in the bootstrap set or got a new-discovery alert; nothing is
backfilled for the others. Its baseline is the observation it was last announced with: the bootstrap
snapshot, the new-discovery alert's observation, the last re-review alert, or a silent rebase (the
comparison key changed, or the baseline source is gone). A rebase is never an event.

Two triggers, one event:
  A. an official business-update filing (P1-A event sentence with its number, P0 subject check) filed
     after the baseline day. A filing whose date cannot be ordered against the baseline waits; an older
     filing collected late is not new. One event signature (issuer, event type, numbers, event date)
     is announced once, whatever document carries it; the same numbers on another date (a re-post) and
     another set of numbers for the same event and date (ambiguous) are held, never sent.
  B. the stored next-year EPS is at least min_growth_pct above the baseline EPS (baseline positive and
     at least min_growth_base_eps, same comparison key), on normal daily screens of two different KST
     days. Only stored eps_now values are compared, never the provider's moving 30/90-day values.
     A condition that lapses before sending is cancelled with its reason.
The event key is fixed by the baseline and the first observation (B) or the signature (A), so a
re-render or another day never makes a new event.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import common as c

VERSION = "material-update-v1"
KIND = "material_update"
METRIC = "eps_next_fy_per_share"
SCREEN_PROVIDER = "Yahoo Finance earningsTrend (+1y)"  # every stored screen row comes from this provider
KST = timezone(timedelta(hours=9))
ANNOUNCED = ("sent", "uncertain")
EVENT_LABELS = {"guidance": "전망 변경", "customer_contract": "고객 계약·수주", "capacity": "생산 능력",
                "acquisition": "인수", "pricing": "가격 인상"}
TRACKED = ("tracked", "entity_tracked")
CANCELLED_KEPT = 200


def settings() -> dict:
    screen = c.policy()["revision_screen"]
    return {"min_growth_pct": float(screen["min_growth_pct"]), "min_growth_base_eps": float(screen["min_growth_base_eps"])}


def empty_state() -> dict:
    return {"version": VERSION, "pending": {}, "rebases": {}, "cancelled": []}


def state_of(ledger: dict) -> dict:
    """Compatible read: a ledger written before P2 has no 'material' part."""
    state = json.loads(json.dumps(ledger.get("material") or empty_state()))
    for key, default in empty_state().items():
        state.setdefault(key, default)
    return state


def kst_day(iso: str | None) -> str | None:
    return datetime.fromisoformat(iso).astimezone(KST).date().isoformat() if iso else None


def comparison_key(eps: dict, provider: str | None) -> list | None:
    """company-independent part of the key: metric, target fiscal period, provider, currency, basis."""
    key = [METRIC, eps.get("eps_target_period"), provider, eps.get("eps_currency"), eps.get("eps_basis")]
    return key if all(key) else None


def entity_key(entity: str, thesis: str) -> str:
    return f"{entity}|{thesis}"


# ------------------------------------------------------------------ baselines

def snapshot_row(ref: dict, ticker: str) -> dict | None:
    """The ticker's row in a stored screen snapshot, only if the file still has the recorded hash."""
    import screen_revisions
    path = screen_revisions.SCREEN_DIR / Path(ref.get("path") or "").name
    if not ref.get("path") or not path.is_file():
        return None
    if hashlib.sha256(path.read_bytes()).hexdigest() != ref.get("sha256"):
        return None
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        rows = json.load(handle).get("derived", {}).get("rows", [])
    return next((r for r in rows if r.get("ticker") == ticker), None)


def bootstrap_baseline(ledger: dict, ticker: str) -> dict | None:
    boot = ledger.get("bootstrap") or {}
    ref = boot.get("source_snapshot") or {}
    row = snapshot_row(ref, ticker)
    if row is None or not isinstance(row.get("eps_now"), (int, float)):
        return None
    observed = ref.get("finished_at")
    return {"source": "bootstrap", "baseline_id": f"bootstrap:{boot.get('date')}:{ref['sha256'][:12]}",
            "observed_at": observed, "day": boot.get("date"), "observation_id": None,
            "snapshot_sha256": ref["sha256"], "eps_now": row["eps_now"],
            "comparison_key": comparison_key(row, SCREEN_PROVIDER)}


def observation_baseline(observation_id: str, source: str) -> dict | None:
    import candidates
    obs = c.read_json(candidates.observations_dir() / f"{observation_id}.json", None)
    if not obs or not isinstance((obs.get("eps") or {}).get("eps_now"), (int, float)):
        return None
    snap = obs.get("source_snapshot") or {}
    observed = snap.get("finished_at") or obs.get("observed_at")
    return {"source": source, "baseline_id": observation_id, "observed_at": observed, "day": kst_day(observed),
            "observation_id": observation_id, "snapshot_sha256": snap.get("sha256"), "eps_now": obs["eps"]["eps_now"],
            "comparison_key": comparison_key(obs["eps"], SCREEN_PROVIDER)}


def baseline(ledger: dict, state: dict, entity: str, thesis: str, ticker: str) -> tuple[dict | None, str | None]:
    """(latest baseline, None), (None, 'unknown') for a candidate never announced, or (None, why)."""
    import candidate_alerts as a
    found, missing = [], None
    new_key = a.logical_key(entity, thesis, a.NEW)
    boot = ledger.get("bootstrap") or {}
    if new_key in (boot.get("keys") or []):
        b = bootstrap_baseline(ledger, ticker)
        if b:
            found.append(b)
        else:
            missing = "bootstrap_snapshot_unavailable"
    event = ledger["events"].get(new_key)
    if event and event.get("status") in ANNOUNCED:
        if event.get("observation_id"):
            b = observation_baseline(event["observation_id"], "new_discovery")
        elif event.get("day") == boot.get("date"):
            b = bootstrap_baseline(ledger, ticker)  # the first run's alert used the bootstrap snapshot
        else:
            b = None
        if b:
            found.append(b)
        else:
            missing = "alert_observation_unavailable"
    for e in ledger["events"].values():
        if (e.get("event") == KIND and e.get("entity_id") == entity and e.get("thesis_key") == thesis
                and e.get("status") in ANNOUNCED and (e.get("material") or {}).get("current")):
            found.append({**e["material"]["current"], "source": KIND})
    rebase = state["rebases"].get(entity_key(entity, thesis))
    if rebase:
        found.append(rebase)
    if not found:
        return None, missing or "unknown"
    return max(found, key=lambda b: b.get("observed_at") or ""), None


# ------------------------------------------------------------------ trigger A

def et_dates(iso: str) -> tuple[str, str]:
    """The baseline's possible US Eastern dates (EDT and EST): a filing date between them is unordered."""
    moment = datetime.fromisoformat(iso)
    return tuple(sorted((moment - timedelta(hours=h)).date().isoformat() for h in (5, 4)))


def signature(cik: str, event: str, numbers: list[str], event_date: str) -> str:
    raw = json.dumps([str(cik), event, sorted(numbers), event_date], separators=(",", ":"))
    return "EV-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16].upper()


def announced_events(ledger: dict) -> list[dict]:
    return [d for e in ledger["events"].values() if e.get("event") == KIND and e.get("status") in ("sent", "uncertain", "reserved")
            for d in (e.get("material") or {}).get("documents") or []]


def new_documents(cand: dict, base: dict, context_state: dict, sent: list[dict]) -> tuple[list[dict], list[str]]:
    """Business-update filings after the baseline, one per signature, and notes on the ones not taken."""
    import company_filings as cf
    entry = (context_state.get("candidates") or {}).get(cand["candidate_id"]) or {}
    cik = (entry.get("issuer") or {}).get("cik")
    early, late = et_dates(base["observed_at"])
    taken, notes, seen = [], [], set()
    for check in entry.get("update_checks") or []:
        if not check.get("eligible"):
            continue
        record = cf.load_document(check["document_id"])
        if not record or not cik or (record.get("issuer") or {}).get("cik") != cik:
            notes.append(f"{check['document_id']}: 문서 없음 또는 발행사 불일치")
            continue
        filed = record.get("filed_at") or ""
        if filed < early:
            notes.append(f"{check['document_id']}: 기준({base['day']}) 이전 제출({filed}) — 새 사건 아님")
            continue
        if filed <= late:
            notes.append(f"{check['document_id']}: 기준일과 같은 날 제출({filed}) — 공개 순서 미확인, 보류")
            continue
        found = cf.business_update_event(record.get("blocks") or [], record.get("issuer_name"))
        if not found:
            notes.append(f"{check['document_id']}: 현재 규칙으로 사건 문장 없음")
            continue
        event_date = record.get("report_date") or filed
        sig = signature(cik, found["event"], found["numbers"], event_date)
        same = [d for d in sent + taken if d.get("cik") == cik and d.get("event") == found["event"]]
        if sig in seen or any(d["signature"] == sig for d in sent):
            notes.append(f"{check['document_id']}: 이미 알린 사건 {sig}")
            continue
        if any(d.get("numbers") == found["numbers"] and d.get("event_date") != event_date for d in same):
            notes.append(f"{check['document_id']}: 같은 수치의 사건 재게재로 보임 — 보류")
            continue
        if any(d.get("event_date") == event_date and d.get("numbers") != found["numbers"] for d in same):
            notes.append(f"{check['document_id']}: 같은 날짜·유형의 다른 수치 — 같은 사건인지 모호, 보류")
            continue
        seen.add(sig)
        taken.append({"document_id": record["document_id"], "url": record.get("url"), "form": record.get("form"),
                      "document_type": record.get("document_type"), "filed_at": filed,
                      "report_date": record.get("report_date"), "event_date": event_date, "cik": cik,
                      "event": found["event"], "numbers": found["numbers"], "sentence": found["sentence"],
                      "signature": sig})
    return taken[:2], notes


# ------------------------------------------------------------------ evaluation

def observation(index: dict, cand: dict) -> dict:
    snap = index.get("source_snapshot") or {}
    observed = snap.get("finished_at") or index.get("observed_at")
    return {"observation_id": cand.get("observation_id"), "baseline_id": cand.get("observation_id"),
            "observed_at": observed, "day": kst_day(observed), "snapshot_sha256": snap.get("sha256"),
            "eps_now": (cand.get("eps") or {}).get("eps_now"),
            "comparison_key": comparison_key(cand.get("eps") or {}, cand.get("eps_provider"))}


def evaluate(index: dict, ledger: dict, context_state: dict, cfg: dict | None = None) -> tuple[list[dict], list[dict], dict]:
    """(alert items, one diagnostic per current candidate, the new material state). Pure: the caller
    stores the state (never in a dry run)."""
    import candidate_alerts as a
    cfg = cfg or settings()
    state = state_of(ledger)
    items, diagnostics, seen = [], [], set()
    sent_docs = announced_events(ledger)
    cards = list(index.get("candidates") or []) + list(index.get("folded_candidates") or [])

    def cancel(ek, reason, **details):
        pending = state["pending"].pop(ek, None)
        if pending:
            state["cancelled"] = (state["cancelled"] + [{"entity": ek, "reason": reason, "at": c.utc_now(),
                                                         "pending": pending, **details}])[-CANCELLED_KEPT:]

    for cand in cards:
        cid, identity = cand.get("candidate_id"), cand.get("identity") or {}
        entity, thesis = identity.get("entity_id"), cand.get("thesis_key")
        if not cid or not entity:
            continue
        ek = entity_key(entity, thesis)
        seen.add(ek)
        diag = {"entity_id": entity, "ticker": identity.get("ticker"), "candidate_id": cid,
                "display_state": cand.get("display_state", "card")}
        diagnostics.append(diag)
        base, why = baseline(ledger, state, entity, thesis, identity.get("ticker"))
        if why == "unknown":
            diag["decision"] = "not_known"  # never announced: the new-discovery path, not a re-review
            continue
        if (cand.get("tracking") or {}).get("status") in TRACKED:
            diag["decision"] = "tracked"
            cancel(ek, "tracked")
            continue
        if cand.get("missing") or cand.get("run_quality") != "complete":
            diag["decision"] = "quality"
            continue
        now = observation(index, cand)
        if base is None or base.get("comparison_key") != now["comparison_key"] or not now["comparison_key"]:
            reason = why or ("comparison_key_changed" if base else "baseline_unavailable")
            if now["comparison_key"]:
                state["rebases"][ek] = {**now, "source": "rebase", "reason": reason}
            cancel(ek, reason)
            diag.update(decision="rebased" if now["comparison_key"] else "no_comparison_key", reason=reason,
                        baseline=base and {k: base.get(k) for k in ("source", "day", "comparison_key")})
            continue
        diag["baseline"] = {k: base.get(k) for k in ("source", "day", "eps_now", "baseline_id")}
        diag["eps_now"] = now["eps_now"]
        triggers, parts, first = [], [], None
        # B: stored EPS against the stored baseline
        b0, b1 = base.get("eps_now"), now["eps_now"]
        pct = (b1 / b0 - 1) * 100 if isinstance(b0, (int, float)) and b0 > 0 and isinstance(b1, (int, float)) else None
        diag["pct"] = None if pct is None else round(pct, 2)
        pending = state["pending"].get(ek)
        if pending and pending.get("baseline_id") != base["baseline_id"]:
            state["pending"].pop(ek)  # the baseline moved (an alert or a rebase): start over
            pending = None
        if b0 is None or b0 < cfg["min_growth_base_eps"] or pct is None:
            diag["b"] = "small_or_negative_base"
            cancel(ek, "small_or_negative_base")
        elif pct < cfg["min_growth_pct"]:
            diag["b"] = "below_threshold"
            cancel(ek, "condition_lapsed", pct=round(pct, 2), observation_id=now["observation_id"])
        elif not pending:
            state["pending"][ek] = {"baseline_id": base["baseline_id"], "first": now}
            diag["b"] = "first_day"
        elif pending["first"]["day"] == now["day"] or pending["first"].get("snapshot_sha256") == now["snapshot_sha256"]:
            diag["b"] = "same_day_waiting"
        else:
            first = pending["first"]
            triggers.append("B")
            parts.append(f"B:{base['baseline_id']}>{first['observation_id']}")
            diag["b"] = "confirmed"
        # A: business-update filings after the baseline
        docs, notes = new_documents(cand, base, context_state, sent_docs)
        if notes:
            diag["a_notes"] = notes
        if docs:
            triggers.append("A")
            parts += [f"A:{d['signature']}" for d in docs]
        if not triggers:
            diag["decision"] = "no_trigger"
            continue
        material = c.validate_record("candidate_alert_material", {
            "version": VERSION, "triggers": triggers, "comparison_key": now["comparison_key"],
            "baseline": base, "first": first, "current": now, "pct": diag["pct"],
            "thresholds": dict(cfg), "documents": docs})
        diag["decision"] = "eligible"
        diag["triggers"] = triggers
        items.append({"channel": "screen", "event": KIND, "entity_id": entity, "thesis_key": thesis,
                      "candidate_id": cid, "candidate_version": cand.get("candidate_version"),
                      "observation_id": cand.get("observation_id"), "cand": cand, "material": material,
                      "key": a.logical_key(entity, thesis, KIND, "+".join(sorted(parts)))})
    for ek in [k for k in state["pending"] if k not in seen]:
        cancel(ek, "not_in_current_screen")
    return items, diagnostics, state


# ------------------------------------------------------------------ message

def message(item: dict) -> str:
    import candidates
    esc = candidates.esc
    cand, m = item["cand"], item["material"]
    base, now = m["baseline"], m["current"]
    source = {"bootstrap": "첫 실행 기준 목록", "new_discovery": "새 발굴 알림", KIND: "이전 재검토 알림",
              "rebase": "기준 재설정"}.get(base.get("source"), base.get("source"))
    period = m["comparison_key"][1]
    lines = [f"<b>🔁 기존 후보의 재검토 변화 · {esc(cand['identity']['ticker'])} {esc(cand.get('name') or '')}</b>",
             f"기준: {esc(base.get('day'))} {esc(source)} 관측"]
    if "B" in m["triggers"]:
        lines.append(f"내년 EPS 예상({esc(period)} 회계연도 말) 기준 {esc(candidates.money(base['eps_now']))} → 현재 "
                     f"{esc(candidates.money(now['eps_now']))} ({m['pct']:+.0f}%), {esc(m['first']['day'])}·{esc(now['day'])} "
                     "두 정상 일간 스크린에서 유지")
        lines.append("제공처 평균 추정치(회계기준 미표시)의 직접 보관값 비교이며 원문 GAAP 실적과 같은 기준이 아님")
    for d in m["documents"]:
        url = d.get("url") or ""
        link = f'<a href="{esc(url)}">원문</a>' if candidates.safe_url(url) else ""
        lines.append(f"새 사업 공시: {esc(d.get('form'))} {esc(d['filed_at'])} 제출 · "
                     f"{esc(EVENT_LABELS.get(d['event'], d['event']))} — \"{esc(d['sentence'][:220])}\" {link}")
    if "A" not in m["triggers"]:
        lines.append("사업 원인: 원문 미확인")
    lines += [esc(text) for text in candidates.estimate_cautions(cand)]
    if cand.get("display_state") == "industry_folded":
        lines.append("업종 제한으로 개별 카드는 접혀 있음(조회 가능)")
    lines += [f"상세 <code>/candidate {esc(cand['candidate_id'])}</code> · 추적 <code>/track {esc(cand['candidate_id'])}</code>",
              "이미 본 후보의 새 변화를 다시 검토하라는 알림이며 투자 권유가 아닙니다."]
    return "\n".join(lines)
