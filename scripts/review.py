"""Read-only research checks. Trigger hits propose a review, never a trade."""
import json
import operator
from datetime import date
import common as c
import metrics

OPERATORS = {"lt": operator.lt, "le": operator.le, "gt": operator.gt, "ge": operator.ge}


def inspect_idea(idea):
    observations = [r for r in c.read_live_rows("metric_log") if r.get("entity_id") == idea.get("entity_id") and r.get("data_quality") == "live"]
    spec = json.loads(idea.get("추적 지표 정의") or "{}")
    missing = []
    for requirement in spec.get("metrics", []):
        matching = [r for r in observations if r.get("metric_kind") == requirement.get("kind")
                    and r.get("지표명") == requirement.get("name")]
        if requirement.get("required", True) and not matching:
            missing.append(requirement.get("name", "unknown"))
        elif requirement.get("required", True) and matching:
            latest_day = max(metrics.observation_date(r) for r in matching)
            age = (date.fromisoformat(c.today()) - date.fromisoformat(latest_day)).days
            default_age = 120 if requirement.get("kind") in {"actual", "guidance"} else c.policy()["metric_stale_days"]
            if age > requirement.get("max_age_days", default_age):
                missing.append(requirement.get("name", "unknown") + " (자료 오래됨)")
    rules = []
    for rule in spec.get("rules", []):
        selector = rule.get("selector", {})
        matches = [r for r in observations if all(r.get(k, "") == str(v) for k, v in selector.items())]
        groups = {metrics.series_key(r) for r in matches}
        label = rule.get("label", str(selector))
        if not matches or len(groups) != 1:
            rules.append((label, "자료 부족" if not matches else "정의 혼합"))
            continue
        latest = max(matches, key=lambda r: r["as_of"])
        age = (date.fromisoformat(c.today()) - date.fromisoformat(metrics.observation_date(latest))).days
        if age > rule.get("max_age_days", c.policy()["metric_stale_days"]):
            rules.append((label, "자료 오래됨"))
            continue
        fn = OPERATORS.get(rule.get("operator"))
        value, threshold = metrics.number(latest.get("현재값")), metrics.number(rule.get("threshold"))
        if not fn or value is None or threshold is None:
            rules.append((label, "규칙 오류"))
        else:
            rules.append((label, "발동" if fn(value, threshold) else "미발동"))
    due = idea.get("다음 점검일", "")
    return {"missing": missing, "rules": rules, "due": not due or due <= c.today(),
            "due_date": due or "미지정", "observations": len(observations)}
