"""Render evidence-linked hypotheses and live tests without inventing a market edge."""
import json
from datetime import date
import common as c
import metrics
import review


def validate(case):
    schema = c.read_json(c.CONFIG_PATH, {})["research_case"]
    missing = [k for k in schema["required"] if k not in case]
    if missing:
        raise ValueError(f"case fields missing: {missing}")
    date.fromisoformat(case["as_of"])
    date.fromisoformat(case["next_review"])
    ids = [s["id"] for s in case["sources"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate source ID")
    for source in case["sources"]:
        if not source.get("group") or not source.get("url", "").startswith("https://"):
            raise ValueError("source identity and URL required")
    for claim in case["chain"]:
        if claim["status"] not in schema["link_status"]:
            raise ValueError("invalid claim status")
        if claim["status"] == "확인" and not claim.get("source_ids"):
            raise ValueError("confirmed claim requires sources")
    tickers = set()
    for candidate in case["candidates"]:
        if any(not candidate.get(k) for k in schema["candidate_required"]):
            raise ValueError("candidate definition incomplete")
        if candidate["ticker"] in tickers:
            raise ValueError("duplicate candidate")
        tickers.add(candidate["ticker"])
    for item in [*case["chain"], *case["candidates"]]:
        if set(item.get("source_ids", [])) - set(ids):
            raise ValueError("unresolved source reference")
    for rule in case["decision_tests"]:
        if rule["ticker"] not in tickers or rule["operator"] not in review.OPERATORS:
            raise ValueError("invalid decision test")
        if metrics.number(rule["threshold"]) is None:
            raise ValueError("numeric test threshold required")
        date.fromisoformat(rule["period_end"])
        date.fromisoformat(rule["registered_at"])
    return case


def load_cases():
    directory = c.DATA_DIR.parent / "research" / "cases"
    cases = [validate(c.read_json(p, {})) for p in sorted(directory.glob("*.json"))]
    if len({x["case_id"] for x in cases}) != len(cases):
        raise ValueError("duplicate case ID")
    return cases


def summary(case):
    gaps = sum(link["status"] in {"미확인", "추론"} for link in case["chain"])
    due = "점검 필요" if case["next_review"] <= c.today() else "예정"
    return f"{case['title']}\n{case['conclusion']}\n미완성 연결 {gaps}개 / 다음 점검 {case['next_review']} ({due})"


def render(case_id=None):
    from gen_report import table
    cases = [x for x in load_cases() if not case_id or x["case_id"] == case_id]
    if case_id and not cases:
        raise ValueError("research case not found")
    if not cases:
        return "# 가설 연구\n\n등록된 연구 사례 없음.\n"
    output = []
    ideas = {r["idea_id"]: r for r in c.active_ideas()}
    observations = [r for r in c.read_rows("metric_log") if r.get("data_quality") == "live"]
    for case in cases:
        output.append(f"# {case['title']}\n\n기준일 {case['as_of']} / 생성일 {c.today()}\n\n{summary(case)}\n")
        output.append("## 인과 연결과 빈칸\n")
        output.append(table(["주장", "판정", "근거", "한계"], [[x["claim"], x["status"], ", ".join(x["source_ids"]), x["limit"]] for x in case["chain"]]))
        output.append("## 후보 비교 — 연구 순서이며 매매 추천이 아님\n\n" + case.get("selection_scope", "") + "\n")
        output.append(table(["기업", "우선순위", "이익 연결", "공개 기대와 차이", "다음 확인", "반증"],
                     [[x["ticker"], x.get("priority", ""), x["mechanism"], x["market_gap"], x["next_check"], x["invalidation"]] for x in case["candidates"]]))
        output.append("## 동일 정의 컨센서스 관측\n\n기업별 대상 연도가 다르므로 EPS 절대값으로 기업의 저평가 순서를 정하지 않습니다.\n")
        rows = []
        for candidate in case["candidates"]:
            groups = {}
            for row in observations:
                if row.get("entity_id") == candidate["entity_id"] and row.get("metric_kind") == "consensus":
                    groups.setdefault(metrics.series_key(row), []).append(row)
            if not groups:
                rows.append([candidate["ticker"], "자료 부족", "", "", "", "", "", ""])
            for group in groups.values():
                stats = metrics.revision_stats(group)
                latest = stats["latest"]
                rows.append([candidate["ticker"], latest["period_end"], latest["현재값"], latest["회계기준"], f"[{latest['출처']}]({latest['출처URL']})", latest["as_of"], stats["observations"], stats["up_months"]])
        output.append(table(["기업", "제공자 대상 기간 말", "EPS", "기준", "출처", "관측일", "관측일 수", "연속 월간 순상향"], rows))
        output.append("## 사전 등록한 반증 점검\n\n미래 실적이 없으면 자료 부족입니다. 회사 전망과 시장 컨센서스 초과 여부는 별개입니다.\n")
        rows = []
        for rule in case["decision_tests"]:
            candidate = next(x for x in case["candidates"] if x["ticker"] == rule["ticker"])
            idea = ideas.get(candidate["idea_id"])
            if not idea or idea.get("entity_id") != candidate["entity_id"]:
                status = "활성 아이디어 연결 확인 필요"
            else:
                spec = {"metrics": [], "rules": [{"label": rule["label"], "selector": {
                    "지표명": rule["metric"], "period_end": rule["period_end"], "metric_kind": "actual",
                    "회계기준": rule["basis"], "단위": rule["unit"], "통화": rule["currency"], "출처": rule["source"]},
                    "operator": rule["operator"], "threshold": rule["threshold"], "max_age_days": 120}]}
                checked = review.inspect_idea({**idea, "추적 지표 정의": json.dumps(spec)})
                status = checked["rules"][0][1]
            rows.append([rule["ticker"], rule["registered_at"], rule["period_end"], rule["label"], rule["threshold"], status])
        output.append(table(["기업", "등록일", "대상 기간", "조건", "기준", "현재 결과"], rows))
        output.append("## 다음 연구 행동\n\n" + "\n".join("- " + x for x in case.get("next_actions", [])))
        output.append("\n## 출처 원장\n\n공급자 발표는 독립 고객 채택 증거가 아닙니다. 날짜 없는 제품 페이지는 기준일에 확인한 자료이며 발표일을 추정하지 않았습니다.\n")
        output.append(table(["ID", "원출처 그룹", "역할", "발표일", "확인 사실", "원문"],
                     [[x["id"], x["group"], x["role"], x["published_at"] or "미표기", x["fact"], f"[출처]({x['url']})"] for x in case["sources"]]))
    return "\n".join(output)
