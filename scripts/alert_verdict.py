"""A suggested judgment on a new-discovery alert, so the alert can be read without opening the card.

The user found the alert's numbers alone too hard to judge (2026-10-12). Each new-discovery alert now
leads with one of three suggestions and the reasons behind it, all from fields the screen already has:

  consider  추적 고려   broad raises (at least min_up30 analysts and min_up_share of those covering raised,
                        raises at least up_per_down times the cuts), the company's own numbers moved
                        into the list (not a rank shuffle), and the price has not already risen as much
  low       관심 낮음   one raise or fewer and either a rank shuffle with unchanged numbers, a cut in the
                        same 30 days or a price that already rose as much; or the estimate fell since the
                        previous snapshot
  watch     지켜보기    everything else

Reasons (pros / cons):
  - analysts: how many of the covering analysts raised or cut in 30 days; few_analysts or fewer covering
  - own change against the latest usable snapshot of an earlier KST day (same target period): unchanged
    means the company entered because others left the list (U 2026-10-12: 11 of 22 past alerts)
  - price over the same 90 days against the estimate change (a reference, never proof of mispricing)
  - a company filing (SEC) in the 30 days in which most of the rise happened: a possible cause, unread
  - the REIT caution of candidates.estimate_cautions
The suggestion is a fixed rule (thresholds provisional, config candidate_alerts.verdict), not a model,
a validated score or a recommendation to buy; the user's reply always overrides it.
"""
from __future__ import annotations

from datetime import date, timedelta

import common as c

LABELS = {"consider": "추적 고려", "watch": "지켜보기", "low": "관심 낮음"}
MARKS = {"consider": "🟢", "watch": "🟡", "low": "⚪"}
DEFAULTS = {"min_up30": 2, "min_up_share": 0.3, "up_per_down": 3, "few_analysts": 3, "min_own_rise_pct": 1.0}
SAME = ("eps_now", "eps_30d", "eps_90d")


def settings() -> dict:
    return {**DEFAULTS, **(c.policy().get("candidate_alerts") or {}).get("verdict", {})}


def num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value


def own_change(eps: dict, previous: dict | None) -> tuple[str | None, float | None]:
    """(unchanged | rose | fell | None, percent) of the company's own estimate since the previous snapshot."""
    if not previous or previous.get("eps_target_period") != eps.get("eps_target_period"):
        return None, None
    if all(previous.get(k) == eps.get(k) for k in SAME):
        return "unchanged", 0.0
    old, new = previous.get("eps_now"), eps.get("eps_now")
    if not num(old) or not num(new) or old == new:
        return None, None
    pct = (new / old - 1) * 100 if old > 0 else None
    return ("rose" if new > old else "fell"), pct


def recent_filing(cand: dict) -> dict | None:
    """The latest company filing in the 30 days before observation, when most of the 90-day rise came in
    those 30 days (the provider's 30/90-day values, as candidates.revision_timing)."""
    eps = cand.get("eps") or {}
    now, d30, d90 = eps.get("eps_now"), eps.get("eps_30d"), eps.get("eps_90d")
    if not all(num(v) for v in (now, d30, d90)) or now <= d90 or (now - d30) / (now - d90) < 0.5:
        return None
    try:
        observed = date.fromisoformat(str(cand.get("observed_at", ""))[:10])
    except ValueError:
        return None
    start = (observed - timedelta(days=30)).isoformat()
    documents = [d for d in ((cand.get("context") or {}).get("documents") or [])
                 if start <= str(d.get("filed_at") or "") <= observed.isoformat()]
    return max(documents, key=lambda d: d["filed_at"]) if documents else None


def short_day(day: str) -> str:
    return f"{int(day[5:7])}/{int(day[8:10])}"


def assess(cand: dict, previous: dict | None) -> dict:
    """{"verdict", "label", "mark", "pros", "cons", "cause", "next"} for one new-discovery candidate."""
    cfg = settings()
    eps, price = cand.get("eps") or {}, cand.get("price") or {}
    up, down, analysts = eps.get("up30"), eps.get("down30"), eps.get("analysts")
    up = up if isinstance(up, int) else 0
    down = down if isinstance(down, int) else 0
    pros, cons = [], []

    share_ok = isinstance(analysts, int) and analysts > 0 and up / analysts >= cfg["min_up_share"]
    broad = up >= cfg["min_up30"] and up >= cfg["up_per_down"] * down and share_ok
    single = up <= 1
    who = f"분석가 {analysts}명 중" if isinstance(analysts, int) else "분석가 중"
    if single:
        cons.append(f"최근 30일 {who} {up}명만 올림 — 한 곳의 수정일 수 있음")
    elif broad:
        pros.append(f"최근 30일 {who} {up}명이 올림" + ("(내린 사람 없음)" if not down else ""))
    else:
        cons.append(f"최근 30일 {who} {up}명만 올림 — 일부 분석가의 상향")
    if down:
        cons.append(f"같은 30일에 내린 분석가도 {down}명")
    if isinstance(analysts, int) and analysts <= cfg["few_analysts"]:
        cons.append(f"이 회사를 보는 분석가가 {analysts}명뿐이라 예상치가 몇 명의 수정에 크게 흔들림")

    state, pct = own_change(eps, previous)
    ranks = ", ".join(f"{m['rank']}위" for m in cand.get("memberships") or [])
    if state == "unchanged":
        cons.append("이 회사 숫자는 지난번 관측과 같음 — 다른 회사가 순위에서 빠지면서 "
                    + (f"{ranks}로 " if ranks else "") + "들어옴")
    elif state == "rose" and pct is not None and pct >= cfg["min_own_rise_pct"]:
        pros.append(f"지난번 관측보다 내년 이익 예상이 또 올라감({pct:+.0f}%)")
    elif state == "fell":
        cons.append("지난번 관측보다 내년 이익 예상이 내려감" + (f"({pct:+.0f}%)" if pct is not None else ""))

    eps_pct = eps.get("pct_90")
    priced_in = False
    if price.get("price_status") == "success" and num(price.get("price_pct_90")) and num(eps_pct):
        move = price["price_pct_90"]
        if move >= eps_pct:
            priced_in = True
            cons.append(f"주가가 같은 90일에 {move:+.0f}% 올라 이익 예상 상향({eps_pct:+.0f}%)만큼 이미 움직임")
        elif move <= eps_pct / 2:
            pros.append(f"주가는 같은 90일에 {move:+.0f}%로, 이익 예상 상향({eps_pct:+.0f}%)보다 덜 움직임")
    if "REIT" in str(cand.get("industry") or ""):
        cons.append("부동산 리츠(REIT): 제공처 이익 숫자가 리츠에 맞는 기준이 아닐 수 있음")

    filing = recent_filing(cand)
    if filing:
        form = f"SEC {filing['form']}" if filing.get("form") else "SEC 제출"
        cause = (f"{short_day(filing['filed_at'])} 회사 공식 발표({form}) 무렵에 예상이 대부분 올라감 — "
                 "발표 내용이 원인일 가능성(내용은 아직 확인 전)")
    else:
        cause = "왜 올랐는지는 아직 모름(회사 발표 원문 미확인)"

    if state == "fell" or (single and (state == "unchanged" or down or priced_in)):
        verdict = "low"
        nxt = "지금은 답장 안 하셔도 됩니다. 관심 있으면 '추적'으로 답장해 주세요."
    elif broad and state != "unchanged" and not priced_in:
        verdict = "consider"
        nxt = "추적하려면 이 메시지에 '추적'으로 답장해 주세요. 아니면 '관심없음'."
    else:
        verdict = "watch"
        import material_updates
        growth = material_updates.settings()["min_growth_pct"]
        nxt = (f"지금은 답장 안 하셔도 됩니다. 이익 예상이 알림 때보다 {growth:.0f}% 이상 더 오르거나 새 공식 "
               "발표가 확인되면 '재검토' 알림으로 다시 알려 드립니다.")
    return {"verdict": verdict, "label": LABELS[verdict], "mark": MARKS[verdict],
            "pros": pros, "cons": cons, "cause": cause, "next": nxt}
