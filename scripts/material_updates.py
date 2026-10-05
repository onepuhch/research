"""Re-review changes of known candidates (P2): 'material_update', an event apart from the first discovery.

A known candidate is one that is in the bootstrap set or got a new-discovery alert; nothing is
backfilled for the others. Its baseline is the observation it was last announced with: the bootstrap
snapshot, the new-discovery alert's observation, the last re-review alert, or a silent rebase (the
comparison key changed, or the baseline source is gone). A rebase is never an event.

Two triggers, one event:
  A. a verified new business event (update-check-v4 alert judgment, confirmed subject) in any stored
     filing of the company, results releases included: dated or announced after the baseline (an older
     event retold in a later filing, an unchanged outlook, a restated result or an undatable sentence is
     not new), and for guidance an explicit change of one comparable outlook. One event signature
     (issuer, event type, its own values, event date, counterparty) is announced once, whatever document
     carries it; a re-post and an ambiguous duplicate are held, never sent.
     An A-only alert does not move the EPS baseline (v2): A history is the sent signatures.
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

VERSION = "material-update-v2"
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
    if state["version"] != VERSION:
        # v1 -> v2 keeps pending first observations and rebases as they are: no A-only alert was ever
        # sent under v1 rules that moved a baseline, so there is nothing to restore (idempotent).
        state["previous_version"], state["version"] = state["version"], VERSION
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
        # Only a delivered alert that carried the EPS change moves the EPS baseline (Q1-B): an A-only
        # alert keeps it, and an uncertain one is locked without being treated as delivered.
        if (e.get("event") == KIND and e.get("entity_id") == entity and e.get("thesis_key") == thesis
                and e.get("status") == "sent" and "B" in (e.get("material") or {}).get("triggers", [])
                and (e.get("material") or {}).get("current")):
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


def signature(cik: str, event: str, values: list[str], event_date: str, party: str | None = None) -> str:
    raw = json.dumps([str(cik), event, list(values), event_date, party], separators=(",", ":"))
    return "EV-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16].upper()


def announced_events(ledger: dict) -> list[dict]:
    return [d for e in ledger["events"].values() if e.get("event") == KIND and e.get("status") in ("sent", "uncertain", "reserved")
            for d in (e.get("material") or {}).get("documents") or []]


def checked_documents(entry: dict) -> list[str]:
    """Every stored document the research read for this company: update checks (P1-A and v4 checks of
    results releases) and the linked documents, in that order, once each."""
    ids = [x["document_id"] for x in entry.get("update_checks") or []]
    ids += list(entry.get("document_ids") or []) + list(entry.get("examined") or [])
    return list(dict.fromkeys(ids))


def prior_guidance(records: list[dict], before: str) -> list[dict]:
    """Outlook values stated by this company's stored documents filed before 'before', oldest first."""
    import company_filings as cf
    out = []
    for record in sorted((r for r in records if (r.get("filed_at") or "") < before), key=lambda r: r.get("filed_at") or ""):
        out += [{**g, "document_id": record["document_id"]}
                for g in cf.guidance_statements(record.get("blocks") or [], record.get("issuer_name"))]
    return out


def novelty(event: dict, base: dict, filed: str) -> str | None:
    """None when the event is after the baseline; otherwise why it is not new (or cannot be ordered)."""
    early, late = et_dates(base["observed_at"])
    date, precision = event.get("event_date"), event.get("date_precision")
    if not date:
        return "사건 날짜 미확인 — 보류"
    if precision == "month":
        month = base["day"][:7] if base.get("day") else early[:7]
        if date < early[:7]:
            return f"사건 시점 {date}이 기준({base['day']}) 이전 — 새 사건 아님"
        if date <= late[:7] or date <= month:
            return f"사건 시점 {date}이 기준과 같은 달 — 선후 미확인, 보류"
        return None
    if date > filed:
        return f"사건 날짜 {date}이 제출일 {filed}보다 뒤 — 사건일 아님, 보류"
    if date < early:
        return f"사건 날짜 {date}이 기준({base['day']}) 이전 — 새 사건 아님"
    if date <= late:
        return f"사건 날짜 {date}이 기준일과 같은 날 — 공개 순서 미확인, 보류"
    return None


def new_documents(cand: dict, base: dict, context_state: dict, sent: list[dict]) -> tuple[list[dict], list[str]]:
    """Verified new business events after the baseline (update-check-v4 alert judgment on every stored
    document of the company, results releases included), one per signature, and notes on the rest."""
    import company_filings as cf
    entry = (context_state.get("candidates") or {}).get(cand["candidate_id"]) or {}
    cik = (entry.get("issuer") or {}).get("cik")
    records = []
    for doc_id in checked_documents(entry):
        record = cf.load_document(doc_id)
        if record and cik and (record.get("issuer") or {}).get("cik") == cik:
            records.append(record)
    taken, notes, seen = [], [], set()
    for record in records:
        filed = record.get("filed_at") or ""
        early, _ = et_dates(base["observed_at"])
        if filed < early:
            continue  # filed before the baseline: nothing in it is new (no note: every old filing would add one)
        prior = prior_guidance(records, filed)
        for event in cf.business_events(record.get("blocks") or [], record.get("issuer_name"), prior):
            label = f"{record['document_id']}#{event['block_id']} {event['event']}"
            if not event["alert_eligible"]:
                notes.append(f"{label}: 알림 근거 아님({event['alert_reason']})")
                continue
            why = novelty(event, base, filed)
            if why:
                notes.append(f"{label}: {why}")
                continue
            sig = signature(cik, event["event"], event["values"], event["event_date"], event.get("counterparty"))
            same = [d for d in sent + taken if d.get("cik") == cik and d.get("event") == event["event"]]
            if sig in seen or any(d["signature"] == sig for d in sent):
                notes.append(f"{label}: 이미 알린 사건 {sig}")
                continue
            if any(d.get("values") == event["values"] and d.get("event_date") != event["event_date"]
                   and d.get("counterparty") == event.get("counterparty") for d in same):
                notes.append(f"{label}: 같은 내용의 사건 재게재로 보임 — 보류")
                continue
            if any(d.get("event_date") == event["event_date"] and d.get("values") != event["values"]
                   and not (d.get("counterparty") and event.get("counterparty")
                            and d["counterparty"] != event["counterparty"]) for d in same):
                notes.append(f"{label}: 같은 날짜·유형의 다른 수치 — 같은 사건인지 모호, 보류")
                continue
            seen.add(sig)
            taken.append({"document_id": record["document_id"], "url": record.get("url"), "form": record.get("form"),
                          "document_type": record.get("document_type"), "filed_at": filed,
                          "report_date": record.get("report_date"), "event_date": event["event_date"],
                          "date_precision": event["date_precision"], "cik": cik, "event": event["event"],
                          "values": event["values"], "counterparty": event.get("counterparty"),
                          "guidance": event.get("guidance"), "sentence": event["sentence"], "signature": sig,
                          "rule": cf.UPDATE_CHECK_VERSION})
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
        # An unfinished event with any of these parts keeps its ID: reserved/uncertain stay locked,
        # failed/released are retried as they were fixed, never re-issued with a new ID (Q1-B).
        open_event = next((e for k, e in ledger["events"].items()
                           if e.get("event") == KIND and e.get("entity_id") == entity
                           and e.get("status") in ("reserved", "uncertain", "failed", "released")
                           and set(parts) & set((e.get("material") or {}).get("parts") or [])), None)
        if open_event and open_event["status"] in ("reserved", "uncertain"):
            diag["decision"] = "locked_unconfirmed"
            continue
        if open_event:
            key = next(k for k, e in ledger["events"].items() if e is open_event)
            diag.update(decision="retry", triggers=open_event["material"]["triggers"])
            items.append({"channel": "screen", "event": KIND, "entity_id": entity, "thesis_key": thesis,
                          "candidate_id": cid, "candidate_version": cand.get("candidate_version"),
                          "observation_id": cand.get("observation_id"), "cand": cand,
                          "material": open_event["material"], "key": key})
            continue
        material = c.validate_record("candidate_alert_material", {
            "version": VERSION, "triggers": triggers, "comparison_key": now["comparison_key"],
            "baseline": base, "first": first, "current": now, "pct": diag["pct"],
            "thresholds": dict(cfg), "documents": docs, "parts": sorted(parts)})
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
        when = f"사건일 {d['event_date']}" + (" (보도자료 날짜)" if d.get("date_precision") == "document" else "")
        lines.append(f"새 사업 공시: {esc(d.get('form'))} {esc(d['filed_at'])} 제출 · {esc(when)} · "
                     f"{esc(EVENT_LABELS.get(d['event'], d['event']))} — \"{esc(d['sentence'][:220])}\" {link}")
        g = d.get("guidance") or {}
        if g.get("status") == "changed":
            key = g["key"]
            shown = lambda r: "?" if not r else (f"{r[0]:,.2f}" if r[0] == r[1] else f"{r[0]:,.2f}~{r[1]:,.2f}")  # noqa: E731
            change = (f"{shown(g['old'])} → {shown(g['new'])}" if g.get("old") else f"변경폭 {g['delta']:,.0f}"
                      + (f", 새 값 {shown(g['new'])}" if g.get("new") else ""))
            unit = {"per_share": "달러/주", "pct": "%"}.get(key["unit"], "백만 달러")
            lines.append(f"  전망 {esc(key['metric'])} {esc(key['period'])}({esc(key['gaap'])}, {unit}): {esc(change)} "
                         f"— {'상향' if g['direction'] == 'up' else '하향'}"
                         + (" · 이전 값은 이전 공시에서" if g.get("prior_document") else ""))
    if "A" not in m["triggers"]:
        lines.append("사업 원인: 원문 미확인")
    lines += [esc(text) for text in candidates.estimate_cautions(cand)]
    if cand.get("display_state") == "industry_folded":
        lines.append("업종 제한으로 개별 카드는 접혀 있음(조회 가능)")
    lines += [f"상세 <code>/candidate {esc(cand['candidate_id'])}</code> · 추적 <code>/track {esc(cand['candidate_id'])}</code>",
              "이미 본 후보의 새 변화를 다시 검토하라는 알림이며 투자 권유가 아닙니다."]
    return "\n".join(lines)
