"""Research views: board, weekly, metric, valuation, bottlenecks, quality, health."""
import argparse
import json
from collections import Counter, defaultdict
from datetime import date, timedelta
import common as c
import metrics
import review


def cell(value):
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |",
                       *["| " + " | ".join(cell(x) for x in row) + " |" for row in rows]]) + "\n"


def active(row):
    return row.get("data_quality") not in {"example", "quarantine"} and row.get("현재 단계") != "제외" and row.get("검토 상태") != "종료"


def render_board():
    rows = []
    for idea in c.active_ideas():
        check = review.inspect_idea(idea)
        rules = "; ".join(f"{k}: {v}" for k, v in check["rules"])
        rows.append([idea["idea_id"], idea["종목/업종"], idea.get("사업 단계", "미확인"),
                     idea.get("근거 수준", "가설"), idea.get("검토 상태", "재검토"),
                     idea.get("최근 점검일", ""), check["due_date"], "점검 필요" if check["due"] else "예정",
                     ", ".join(check["missing"]) or "없음", rules or "정량 규칙 미등록"])
    return f"# 추적 상태판 ({c.today()})\n\n활성 {len(rows)}건. 사업 단계와 근거 수준은 별도로 표시합니다.\n\n" + table(
        ["ID", "대상", "사업 단계", "근거 수준", "검토 상태", "최근 점검", "다음 점검", "일정", "부족 지표", "반증 점검"], rows)


def render_weekly():
    cutoff = (date.fromisoformat(c.today()) - timedelta(days=7)).isoformat()
    history = [r for r in c.read_live_rows("review_history") if r.get("reviewed_at", "")[:10] >= cutoff]
    result = f"# 주간 변화 보고 ({c.today()})\n\n" + table(
        ["아이디어", "검토일", "판단 변화", "이전 상태", "이후 상태", "이유"],
        [[r["idea_id"], r["reviewed_at"], r["판단 변화"], r["이전 상태"], r["이후 상태"], r["변경 사유"]] for r in history])
    if not history:
        result += "\n지난 7일 판단 갱신 없음. 신호 추가와 연구 갱신은 다릅니다.\n"
    return result + "\n" + render_board() + "\n" + render_health()


def group_metric_rows():
    groups = defaultdict(list)
    for row in c.read_rows("metric_log"):
        if row.get("data_quality") == "live":
            groups[metrics.series_key(row)].append(row)
    return dict(groups)


def consecutive_up_count(rows):
    return metrics.revision_stats(rows)["up_events"]


def render_metrics(subject=None, min_count=None):
    rows = []
    for observations in group_metric_rows().values():
        stats = metrics.revision_stats(observations)
        latest = stats["latest"]
        if not latest or (subject and subject.casefold() not in (latest.get("종목/업종", "") + latest.get("entity_id", "")).casefold()):
            continue
        if min_count is not None and (latest.get("metric_kind") != "consensus" or stats["up_events"] < min_count
                                     or stats["age_days"] > c.policy()["metric_stale_days"]):
            continue
        rows.append([latest["종목/업종"], latest["지표명"], latest.get("metric_kind"), latest.get("period_end"),
                     latest["현재값"], latest.get("단위"), latest.get("회계기준"), latest["출처"], latest["as_of"],
                     stats["up_events"], stats["up_months"], stats["last_up"], stats["age_days"]])
    return f"# 지표 관측 ({c.today()})\n\n상향 사건 수는 일별 관측 차이입니다. 유지 관측은 보존하며 월간 변화·자료 신선도를 별도 표시합니다.\n\n" + table(
        ["대상", "지표", "종류", "대상 기간 말", "값", "단위", "기준", "출처", "관측일", "하향 이후 상향 사건", "월간 연속 순상향", "마지막 상향", "경과일"], rows)


def render_metric_board(min_count=2):
    return render_metrics(min_count=min_count)


def render_metric_detail(subject):
    return render_metrics(subject)


def render_valuation(subject):
    observations = [r for r in c.read_rows("metric_log") if r.get("data_quality") == "live" and subject.casefold() in (r.get("종목/업종", "") + r.get("entity_id", "")).casefold()]
    prices = [r for r in observations if r.get("metric_kind") == "price"]
    groups = defaultdict(list)
    for row in observations:
        if row.get("metric_kind") == "consensus":
            groups[metrics.series_key(row)].append(row)
    result = [metrics.aligned_valuation(group, prices) for group in groups.values()] or [{"status": "EPS 관측 없음"}]
    return f"# 동일 기간 밸류 비교: {subject}\n\n멀티플 변화는 저평가 판정이 아닙니다.\n\n```json\n" + json.dumps(result, ensure_ascii=False, indent=2) + "\n```\n"


def render_health():
    state = c.read_json(c.DATA_DIR / "run_status.json", {})
    rows = []
    for name in ["collect", "extract", "eps", "commands", "notify", "review_report", "telegram_delivery"]:
        component = state.get(name, {})
        checked = component.get("checked_at", "")
        old = not checked or checked[:10] < (date.fromisoformat(c.today()) - timedelta(days=1)).isoformat()
        rows.append([name, component.get("status", "미확인"), checked, component.get("last_success_at", ""),
                     "실행 확인 필요" if old else "최근 기록 있음", json.dumps({k: v for k, v in component.items() if k not in {"status", "checked_at", "last_success_at"}}, ensure_ascii=False)])
    return "# 운영 상태\n\n" + table(["기능", "상태", "확인 시각", "마지막 성공", "신선도", "상세"], rows)


def render_bottlenecks():
    config = c.read_json(c.ROOT / "config" / "value_chain.json", {"nodes": []})
    cutoff = (date.fromisoformat(c.today()) - timedelta(days=14)).isoformat()
    signals = [r for r in c.read_rows("signal_log") if r.get("data_quality") == "live" and cutoff <= r.get("published_at", "")[:10] <= c.today()]
    rows = []
    for node in config["nodes"]:
        matching = [r for r in signals if r.get("bottleneck_id") == node["id"]]
        entities = {r.get("entity_id") or r.get("종목/티커") for r in matching}
        rows.append([node["id"], node["name"], node["question"], len(matching), len(entities),
                     ", ".join(r["signal_id"] for r in matching), node["invalidation"]])
    return "# 병목 연구 지도\n\n문서 수와 기업 수는 독립 근거 수가 아닙니다. 병목 이동은 사람이 교차 검증합니다.\n\n" + table(
        ["노드", "밸류체인", "연구 질문", "14일 신호", "기업 수", "근거 ID", "해소·반증 조건"], rows)


def render_quality():
    evaluations = c.read_live_rows("evaluation_log")
    counts = Counter((r.get("평가 종류"), r.get("판정")) for r in evaluations)
    return "# 연구 품질 측정\n\n평가가 없는 항목의 적중률은 미측정입니다. 수익률은 별도 표준 기간·벤치마크로 복기합니다.\n\n" + table(
        ["평가 종류", "판정", "건수"], [[kind, verdict, n] for (kind, verdict), n in sorted(counts.items())])


def render_sector(name):
    return "# 섹터 검토\n\n" + table(["아이디어", "대상", "가설", "근거", "다음 점검"],
        [[r["idea_id"], r["종목/업종"], r.get("thesis_key"), r.get("근거 수준"), r.get("다음 점검일")]
         for r in c.active_ideas() if name.casefold() in json.dumps(r, ensure_ascii=False).casefold()])


def render_share():
    return render_board()


def save(name, content):
    directory = c.ROOT / "reports" / "generated"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}_{c.today()}.md"
    path.write_text(content, encoding="utf-8")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", choices=["board", "weekly", "metric", "valuation", "bottlenecks", "quality", "health", "sector", "share"])
    parser.add_argument("subject", nargs="?")
    parser.add_argument("--min", dest="minimum", type=int, default=2)
    args = parser.parse_args(argv)
    if args.view in {"valuation", "sector"} and not args.subject:
        parser.error("subject required")
    if args.minimum < 1:
        parser.error("--min must be positive")
    if args.view == "metric":
        content = render_metric_detail(args.subject) if args.subject else render_metric_board(args.minimum)
    elif args.view == "valuation":
        content = render_valuation(args.subject)
    elif args.view == "sector":
        content = render_sector(args.subject)
    else:
        content = globals()["render_" + args.view]()
    print(content)
    save(args.view, content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
