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
