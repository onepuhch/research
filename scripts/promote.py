"""Register a research hypothesis idempotently, retaining its source links."""
import argparse
import hashlib
import json
import re
from datetime import date, timedelta
import common as c
import add_entry


def find_signal(signal_id):
    return next((r for r in c.read_live_rows("signal_log") if r.get("signal_id") == signal_id.strip().upper()), None)


def identity(signal, ticker=""):
    subject = signal.get("종목/티커", "").strip()
    ticker = ticker or (subject if re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", subject) else "")
    if ticker and not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", ticker):
        raise ValueError("invalid ticker")
    entity = signal.get("entity_id", "")
    if not entity:
        match = re.search(r"/edgar/data/(\d+)/", signal.get("출처URL", ""))
        entity = f"CIK:{int(match.group(1)):010d}" if match else "NAME:" + hashlib.sha256(subject.casefold().encode()).hexdigest()[:16]
    return c.resolve_entity(entity, ticker)


def promote_signal(signal, idea_type="병목 확산형", strength="1", trigger="", thesis_key="", ticker=""):
    if not signal.get("종목/티커") or signal["종목/티커"] == "미분류":
        raise ValueError("identified company required")
    entity, ticker = identity(signal, ticker)
    thesis = thesis_key or signal.get("bottleneck_id") or signal.get("테마") or "unclassified"
    thesis = re.sub(r"\s+", " ", thesis.casefold()).strip()
    origin = signal["signal_id"]
    rows = c.read_live_rows("investment_review_log")
    for row in rows:
        origins = json.loads(row.get("origin_signal_ids") or "[]")
        if origin in origins:
            return row["idea_id"]
        if row.get("entity_id") == entity and row.get("thesis_key", "").casefold() == thesis and row.get("검토 상태") != "종료" and row.get("현재 단계") != "제외":
            return add_entry.process({"target_table": "investment_review_log", "data": {
                "idea_id": row["idea_id"], "origin_signal_ids": json.dumps([*origins, origin]),
                "변경 사유": f"동일 가설에 신규 근거 연결: {origin}", "판단 변화": "자료 부족",
                "최근 점검일": row.get("최근 점검일", ""),
                "검토 상태": "재검토"}})
    if len(c.active_ideas()) >= c.policy()["max_active_ideas"]:
        raise ValueError("active idea capacity reached; review existing ideas first")
    next_date = (date.fromisoformat(c.today()) + timedelta(days=c.policy()["review_interval_days"])).isoformat()
    spec = {"metrics": [{"name": "EPS consensus", "kind": "consensus", "required": True}], "rules": []}
    return add_entry.process({"target_table": "investment_review_log", "data": {
        "대상유형": "종목", "종목/업종": signal["종목/티커"], "entity_id": entity,
        "ticker": ticker, "thesis_key": thesis, "origin_signal_ids": json.dumps([origin]),
        "출처URL": signal.get("document_url") or signal.get("출처URL", ""),
        "당시 판단": f"테마: {signal.get('테마', '')} | 검증 대기", "현재 단계": "관찰",
        "아이디어 유형": idea_type, "근거 강도": "1", "핵심 근거": signal.get("특이값 요약", ""),
        "다음 단계 트리거": trigger, "사업 단계": "미확인", "근거 수준": "가설",
        "검토 상태": "미검토", "다음 점검일": next_date, "판단 변화": "신규",
        "최근 점검일": "",
        "변경 사유": f"원신호 {origin}에서 검토 등록; baseline과 반증 조건 확인 필요",
        "추적 지표 정의": json.dumps(spec, ensure_ascii=False), "data_quality": "live"}})


def promote_candidate(cand, now_day=None):
    """Register the user's choice to track a screener candidate. No signal is invented.

    Same entity + thesis returns the existing idea (linking this candidate once). A repeat
    for an already linked active idea returns its ID before any freshness check and writes
    nothing. A closed idea is never reopened. Every refusal is a ValueError raised before
    any write; OSError propagates for retry.
    """
    import candidates
    today = date.fromisoformat(now_day or c.today())
    cid = cand.get("candidate_id") or ""
    identity = cand.get("identity") or {}
    eps = cand.get("eps") or {}
    if not candidates.normalize_id(cid) or not identity.get("verified") or not identity.get("entity_id"):
        raise ValueError("candidate identity not verified")
    entity, ticker, thesis = identity["entity_id"], identity.get("ticker", ""), cand["thesis_key"]
    active = [row for row in c.read_live_rows("investment_review_log")
              if row.get("entity_id") == entity and row.get("thesis_key") == thesis
              and row.get("검토 상태") != "종료" and row.get("현재 단계") != "제외"]
    for row in active:
        if cid in json.loads(row.get("origin_candidate_ids") or "[]"):
            return row["idea_id"]
    if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", ticker) or not eps.get("eps_currency"):
        raise ValueError("candidate ticker or estimate currency missing")
    # Freshness is the real last observation, as a KST date; a future observation is refused.
    observed = date.fromisoformat(candidates.kst_date(str(cand.get("observed_at", ""))))
    if observed > today:
        raise ValueError("candidate observation in the future")
    if (today - observed).days > c.policy()["signal_lookback_days"]:
        raise ValueError("candidate observation too old; view the latest screen first")
    for row in active:
        linked = json.loads(row.get("origin_candidate_ids") or "[]")
        return add_entry.process({"target_table": "investment_review_log", "data": {
            "idea_id": row["idea_id"], "origin_candidate_ids": json.dumps([*linked, cid]),
            "변경 사유": f"동일 가설에 후보 연결: {cid} 버전 {cand['candidate_version']}",
            "최근 점검일": row.get("최근 점검일", "")}})
    if len(c.active_ideas()) >= c.policy()["max_active_ideas"]:
        raise ValueError("active idea capacity reached; review existing ideas first")
    snapshot = cand.get("source_snapshot") or {}
    price = cand.get("price") or {}
    price_text = (f"주가 {price['price_start_date']}→{price['price_end_date']} {price['price_pct_90']:+.1f}%"
                  if price.get("price_status") == "success" else "주가 비교 미확보")
    missing = ", ".join(m["field"] for m in cand.get("missing", [])) or "없음"
    symbol = ticker.replace(".", "-")
    next_date = (today + timedelta(days=c.policy()["review_interval_days"])).isoformat()
    spec = {"metrics": [{"name": "EPS consensus", "kind": "consensus", "required": True},
                        {"name": "Regular session price", "kind": "price", "required": False}], "rules": []}
    return add_entry.process({"target_table": "investment_review_log", "data": {
        "대상유형": "종목", "종목/업종": ticker, "entity_id": entity, "ticker": ticker, "thesis_key": thesis,
        "origin_signal_ids": "[]", "origin_candidate_ids": json.dumps([cid]),
        "출처URL": f"https://finance.yahoo.com/quote/{symbol}/analysis",
        "당시 판단": (f"EPS 상향 원인·지속성 검토 | 후보 {cid} 버전 {cand['candidate_version']} | "
                   f"관측 {cand.get('observation_id') or '미기록'} | "
                   f"원자료 {snapshot.get('path', '')} ({str(snapshot.get('sha256', ''))[:12]}) | 사용자 추적 선택"),
        "현재 단계": "관찰", "아이디어 유형": "사이클 리비전형", "근거 강도": "1",
        "핵심 근거": (f"등록 기준({str(cand.get('observed_at', ''))[:16]} UTC, Yahoo earningsTrend +1y, "
                   f"{eps.get('eps_target_period')} 회계연도 말, {eps['eps_currency']}): 내년 EPS 예상 "
                   f"90일 전 {eps.get('eps_90d')} → 30일 전 {eps.get('eps_30d')} → 현재 {eps.get('eps_now')}; "
                   f"30일 상향 {eps.get('up30')}/하향 {eps.get('down30')}; {price_text}"),
        "리스크": f"미확인: EPS 상향의 사업 원인(원문), 지속성, 시장 반영 여부. 자료 부족 항목: {missing}",
        "모니터링 지표": "내년 EPS 예상(같은 제공자·대상 기간), 정규장 주가, 분기 EPS·매출",
        "다음 단계 트리거": "실적 발표·가이던스 원문으로 이익 경로를 확인하면 근거 수준 갱신",
        "종료 조건(정량)": (f"같은 대상 기간 EPS 예상이 등록 기준 {eps.get('eps_now')} 아래로 내려가고 "
                        f"30일 하향 수가 상향 수 이상이면 재검토"),
        "사업 단계": "미확인", "근거 수준": "가설", "검토 상태": "추적",
        "다음 점검일": next_date, "판단 변화": "신규", "최근 점검일": "",
        "변경 사유": f"사용자가 /track으로 추적을 선택함(검증 승격 아님). 후보 {cid} 버전 {cand['candidate_version']}",
        "추적 지표 정의": json.dumps(spec, ensure_ascii=False), "data_quality": "live"}})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("signal_id")
    parser.add_argument("--type", dest="idea_type", choices=c.ENUMS["아이디어 유형"], default="병목 확산형")
    parser.add_argument("--trigger", default="")
    parser.add_argument("--thesis-key", default="")
    parser.add_argument("--ticker", default="")
    args = parser.parse_args()
    signal = find_signal(args.signal_id)
    if not signal:
        raise ValueError("signal not found")
    print(promote_signal(signal, idea_type=args.idea_type, trigger=args.trigger,
                         thesis_key=args.thesis_key, ticker=args.ticker))


if __name__ == "__main__":
    main()
