"""First discovery times and later outcomes of screen candidates (P3, minimal; no new collection).

Fixed records, one per company|thesis, built from the stored daily screens, the stored candidate
drafts and the alert ledger. The population is every condition-passing company of every stored
screen (shown cards, industry-folded and outside the top lists); a company that leaves the list or
does badly stays in it. A 'first' value is written once from the snapshot it came from and never
moves: a re-render, a later snapshot or a newer draft never changes it, and rendered_at is never
used as a discovery time. Unknown values stay null.

mode: 'retrospective' when the first pass is older than this store (rebuilt from archives after the
fact, like N's manual AEHR/OSCR selection), 'prospective' when the store already existed when it was
first seen. Claims about earlier discovery use prospective records only.

Latency is the first measure of earliness, never 'earlier than the market':
  evidence document: SEC filing date -> our download (date precision; the filing time is not kept)
  first condition pass -> first card -> first alert receipt (hours)
Our own later EPS observation for the same comparison key is shown apart.
Outcome: research_returns.compare with the first card (else the first pass) as the registration time:
first regular close after it, 30/90/180 calendar days, USD adjusted closes, SPY, 0.20%p round-trip
cost, from stored price batches only. A ticker without stored prices is 'price not collected'.

    python scripts/discovery_timing.py           # update the store and write the report
    python scripts/discovery_timing.py --render  # report from the store as it is
"""
from __future__ import annotations

import argparse
import statistics
from datetime import datetime, timezone
from pathlib import Path

import common as c

VERSION = "discovery-timing-v1"
HORIZONS = (30, 90, 180)
PRICE_MISSING = "시세 미수집"


def store_path() -> Path:
    return c.DATA_DIR / "discovery_timing.json"


def load() -> dict:
    store = c.read_json(store_path(), None)
    if store is None:
        return {"version": VERSION, "created_at": None, "snapshots": [], "records": {}}
    if not isinstance(store.get("records"), dict):
        raise ValueError("invalid discovery timing store; restore it before updating")
    return store


def screen_states(derived: dict) -> dict[str, str]:
    import candidates
    shown = {t for t, _ in candidates.display_order(derived)}
    folded = {t for g in derived.get("industry_groups") or [] for t in g.get("folded", [])} - shown
    return {r["ticker"]: "card" if r["ticker"] in shown else "folded" if r["ticker"] in folded else "outside"
            for r in derived.get("rows", []) if r.get("candidate")}


def observation(path: Path, run: dict, row: dict, state: str) -> dict:
    import material_updates
    cfg = run.get("config") or {}
    return {"snapshot": path.name, "run_id": run.get("run_id"), "observed_at": run["finished_at"], "state": state,
            "eps": {k: row.get(k) for k in ("eps_now", "eps_30d", "eps_90d", "up30", "down30", "analysts")},
            "comparison_key": material_updates.comparison_key(row, material_updates.SCREEN_PROVIDER),
            "rule": {"code_version": run.get("code_version"), "top_n": cfg.get("top_n"),
                     "max_per_industry": cfg.get("max_per_industry")}}


def new_record(entity: str | None, ticker: str, cid: str | None) -> dict:
    return {"entity_id": entity, "ticker": ticker, "candidate_id": cid, "mode": None, "passes": 0,
            "first_pass": None, "first_card": None, "first_folded": None, "last_pass": None,
            "first_evidence": None, "first_alert": None, "bootstrap": None}


def first_evidence(cid: str) -> dict | None:
    """The earliest stored draft that the validator accepts, with its cited documents' dates."""
    import candidates
    records = [c.read_json(p, {}) for p in (c.DATA_DIR / "candidate_context_history").glob("CTX-*.json")]
    for record in sorted((r for r in records if r.get("candidate_id") == cid), key=lambda r: r.get("generated_at") or ""):
        if record.get("context_status") != "draft_ready":
            continue
        view, _ = candidates.verified_context(record)
        claims = (view or {}).get("claims") or []
        if not claims:
            continue
        cited = {x.get("document_id") for x in claims}
        return {"context_id": record["context_id"], "generated_at": record.get("generated_at"),
                "validator": view.get("display_validator_version"), "claims": len(claims),
                "documents": [{k: d.get(k) for k in ("document_id", "form", "filed_at", "observed_at", "url")}
                              for d in view.get("documents") or [] if d.get("document_id") in cited]}
    return None


def first_alert(ledger: dict, entity: str) -> dict | None:
    events = [e for e in ledger.get("events", {}).values()
              if e.get("entity_id") == entity and e.get("status") in ("sent", "uncertain")]
    receipts = []
    for e in events:
        attempt = next((x for x in e.get("attempts") or [] if x.get("status") in ("sent", "uncertain")), None)
        if attempt:
            receipts.append({"at": attempt["at"], "status": attempt["status"], "message_id": attempt.get("message_id"),
                             "channel": e.get("channel"), "event": e.get("event"), "day": e.get("day")})
    return min(receipts, key=lambda r: r["at"]) if receipts else None


def update(now: datetime | None = None) -> dict:
    """Add the snapshots not yet read and fill first values that are still null; returns a report."""
    import candidate_alerts
    import candidates
    import screen_revisions
    now = now or datetime.now(timezone.utc)
    store = load()
    store["created_at"] = store["created_at"] or now.isoformat(timespec="seconds")
    created = datetime.fromisoformat(store["created_at"])
    registry = c.read_json(c.ROOT / "config" / "entities.json", {})
    seen, added = set(store["snapshots"]), 0
    paths = screen_revisions.snapshots()
    # Early screens did not record the exchange: a ticker identified by any stored screen keeps that entity.
    known = {r["ticker"]: candidates.identify(r, registry)["entity_id"]
             for p in paths for r in screen_revisions.load_snapshot(p).get("derived", {}).get("rows", [])
             if candidates.identify(r, registry)["entity_id"]}
    for path in paths:
        if path.name in seen:
            continue
        snap = screen_revisions.load_snapshot(path)
        run = snap.get("run") or {}
        store["snapshots"].append(path.name)
        if run.get("status") not in ("success", "degraded") or not run.get("finished_at"):
            continue  # no usable observation time: never back-filled from a file name
        added += 1
        states = screen_states(snap.get("derived", {}))
        for row in snap["derived"]["rows"]:
            if not row.get("candidate"):
                continue
            entity = candidates.identify(row, registry)["entity_id"] or known.get(row["ticker"])
            key = f"{entity or 'unidentified:' + row['ticker']}|{candidates.THESIS_KEY}"
            rec = store["records"].setdefault(key, new_record(entity, row["ticker"],
                                                              candidates.candidate_id(entity) if entity else None))
            obs = observation(path, run, row, states[row["ticker"]])
            if rec["first_pass"] is None:
                rec["first_pass"] = obs
                rec["mode"] = ("retrospective" if datetime.fromisoformat(obs["observed_at"]) < created
                               else "prospective")
            if obs["state"] == "card" and rec["first_card"] is None:
                rec["first_card"] = obs
            if obs["state"] == "folded" and rec["first_folded"] is None:
                rec["first_folded"] = obs
            if not rec["last_pass"] or obs["observed_at"] >= rec["last_pass"]["observed_at"]:
                rec["last_pass"] = {k: obs[k] for k in ("snapshot", "observed_at", "state", "eps", "comparison_key")}
            rec["passes"] += 1
    ledger = candidate_alerts.load_ledger()
    boot = ledger.get("bootstrap") or {}
    boot_entities = {k.split("|")[0] for k in boot.get("keys") or []}
    for rec in store["records"].values():
        if rec["entity_id"] and rec["first_alert"] is None:
            rec["first_alert"] = first_alert(ledger, rec["entity_id"])
        if rec["entity_id"] and rec["bootstrap"] is None and rec["entity_id"] in boot_entities:
            rec["bootstrap"] = {"date": boot.get("date"), "snapshot": (boot.get("source_snapshot") or {}).get("path")}
        if rec["candidate_id"] and rec["first_evidence"] is None:
            rec["first_evidence"] = first_evidence(rec["candidate_id"])
    store["version"], store["updated_at"] = VERSION, now.isoformat(timespec="seconds")
    c.atomic_json(store_path(), store)
    return {"snapshots_added": added, "records": len(store["records"])}


# ------------------------------------------------------------------ measures

def hours(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() / 3600


def latencies(rec: dict) -> dict:
    card = rec.get("first_card") or {}
    out = {"pass_to_card_h": hours((rec.get("first_pass") or {}).get("observed_at"), card.get("observed_at")),
           "card_to_alert_h": hours(card.get("observed_at"), (rec.get("first_alert") or {}).get("at")),
           "filing_to_download_days": []}
    for d in (rec.get("first_evidence") or {}).get("documents") or []:
        if d.get("filed_at") and d.get("observed_at"):
            out["filing_to_download_days"].append(
                (datetime.fromisoformat(d["observed_at"]).date() - datetime.fromisoformat(d["filed_at"]).date()).days)
    return out


def own_eps_change(rec: dict) -> dict:
    """Our own stored EPS for the same key since the first pass; not a claim about the market."""
    first, last = rec.get("first_pass") or {}, rec.get("last_pass") or {}
    if not first or not last or first.get("observed_at") == last.get("observed_at"):
        return {"status": "단일 관측"}
    if first.get("comparison_key") != last.get("comparison_key"):
        return {"status": "비교 기준 변경"}
    a, b = first["eps"].get("eps_now"), last["eps"].get("eps_now")
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)) or a <= 0:
        return {"status": "비교 불가(기준값)"}
    days = (datetime.fromisoformat(last["observed_at"]) - datetime.fromisoformat(first["observed_at"])).days
    return {"status": "관측", "pct": (b / a - 1) * 100, "days": days}


def outcomes(rec: dict, batch: dict | None) -> dict[int, dict]:
    import research_returns
    start = (rec.get("first_card") or rec.get("first_pass") or {}).get("observed_at")
    if not batch or rec["ticker"] not in batch.get("series", {}):
        return {h: {"status": PRICE_MISSING} for h in HORIZONS}
    cohort = {"ticker": rec["ticker"], "captured_at": start}
    return {h: research_returns.compare(cohort, batch["series"][rec["ticker"]], batch["series"].get("SPY", {}),
                                        batch["retrieved_at"], h) for h in HORIZONS}


def latest_batch() -> dict | None:
    files = sorted((c.DATA_DIR / "return_history").glob("*.json"))
    return c.read_json(files[-1], None) if files else None


def median_text(values: list[float], unit: str, digits: int = 1) -> str:
    values = [v for v in values if v is not None]
    return f"중앙값 {statistics.median(values):.{digits}f}{unit} (n={len(values)})" if values else "자료 없음 (n=0)"


def render(store: dict | None = None) -> str:
    store = store or load()
    records = list(store["records"].values())
    batch = latest_batch()
    lines = ["## 발견 시점과 이후 결과 (최소 기록)", "",
             f"조건 통과 기업 전체가 모집단입니다(대표 카드·업종 묶음·일반 순위 밖, 이탈 기업 포함). 기록 시작 "
             f"{store.get('created_at') or '-'}; 그 전에 처음 관측된 기업은 저장 스냅샷에서 복원한 **사후(retrospective)** 기록입니다. "
             "적중률·조기 발견 성과는 충분한 전향(prospective) 표본 전에는 표시하지 않습니다.", ""]
    if not records:
        return "\n".join(lines + ["기록 없음.", ""])
    count = lambda f: sum(1 for r in records if f(r))  # noqa: E731
    lines += [f"- 기업 {len(records)}곳 (사후 {count(lambda r: r['mode'] == 'retrospective')}, "
              f"전향 {count(lambda r: r['mode'] == 'prospective')}, 식별 불가 {count(lambda r: not r['entity_id'])})",
              f"- 대표 카드에 오른 적 있음 {count(lambda r: r['first_card'])} · 업종 묶음으로 접힌 적 있음 "
              f"{count(lambda r: r['first_folded'])} · 일반 순위 밖만 {count(lambda r: not r['first_card'] and not r['first_folded'])}",
              f"- 실제 알림 {count(lambda r: r['first_alert'])} · 초기 관측 목록(알림 없음) "
              f"{count(lambda r: r['bootstrap'] and not r['first_alert'])} · 유효 근거 초안 {count(lambda r: r['first_evidence'])}"]
    lat = [latencies(r) for r in records]
    lines += ["", "지연시간(빠르다는 뜻이 아니라 우리 경로의 소요 시간):",
              f"- 근거 문서 제출일→수집: {median_text([d for x in lat for d in x['filing_to_download_days']], '일')} (날짜 정밀도)",
              f"- 첫 조건 통과→첫 대표 카드: {median_text([x['pass_to_card_h'] for x in lat], '시간', 2)}",
              f"- 첫 대표 카드→첫 알림: {median_text([x['card_to_alert_h'] for x in lat], '시간', 2)}"]
    eps = [own_eps_change(r) for r in records]
    lines.append(f"- 첫 통과 이후 자체 관측 EPS(같은 비교 키): 관측 {sum(e['status'] == '관측' for e in eps)}곳, "
                 f"기준 변경 {sum(e['status'] == '비교 기준 변경' for e in eps)}곳, 단일 관측 {sum(e['status'] == '단일 관측' for e in eps)}곳")
    lines += ["", "이후 주가(첫 대표 카드, 없으면 첫 통과 이후 첫 정규장 종가 기준, SPY 비교, 왕복 0.20%p; 기존 성과 정의):"]
    results = [outcomes(r, batch) for r in records]
    for h in HORIZONS:
        statuses: dict[str, int] = {}
        for res in results:
            statuses[res[h]["status"]] = statuses.get(res[h]["status"], 0) + 1
        lines.append(f"- {h}일: " + ", ".join(f"{k} {v}" for k, v in sorted(statuses.items())))
    missing = sorted({r["ticker"] for r, res in zip(records, results) if res[30]["status"] == PRICE_MISSING})
    lines += ["", f"보관 시세가 없는 기업 {len(missing)}곳: 성과를 계산하려면 종목당 Yahoo 일봉 요청 1회(총 약 {len(missing)}회)가 "
              "필요합니다. 일간 자동 수집에는 추가하지 않았습니다(다음 변경에서 결정).", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--render", action="store_true", help="report only; the store is not updated")
    args = parser.parse_args(argv)
    if not args.render:
        print(f"[discovery_timing] {update()}")
    from gen_report import save
    print(save("discovery_timing", render()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
