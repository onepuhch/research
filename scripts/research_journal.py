"""Freeze research revisions and evaluate their original conditions, without hindsight."""
import hashlib
import json
from datetime import datetime, timezone
import common as c
import metrics
import review


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def instant(value):
    # Date-only observations are conservatively available at the end of that KST day.
    text = str(value)
    if len(text) == 10:
        text += "T23:59:59.999999+09:00"
    result = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("journal timestamps require timezone")
    return result


def directory():
    return c.DATA_DIR / "research_journal"


def verify(snapshot):
    payload = {k: v for k, v in snapshot.items() if k != "integrity"}
    if snapshot.get("integrity") != digest(payload):
        raise ValueError("research snapshot integrity mismatch")
    if snapshot["revision"] != digest(snapshot["case"]):
        raise ValueError("research revision mismatch")
    instant(snapshot["captured_at"])
    return snapshot


def capture(case, observations, captured_at=None, destination=None):
    """One snapshot per case revision. Repeated runs never refresh its baseline."""
    captured_at = captured_at or datetime.now(timezone.utc).isoformat()
    cutoff = instant(captured_at)
    revision = digest(case)
    path = (destination or directory()) / (revision + ".json")
    if path.exists():
        return verify(c.read_json(path, {}))
    entities = {x["entity_id"] for x in case["candidates"]}
    baseline = [r for r in observations if r.get("data_quality") == "live"
                and r.get("entity_id") in entities and instant(r["as_of"]) <= cutoff]
    snapshot = {"version": 1, "revision": revision, "captured_at": captured_at,
                "case": case, "observations": baseline,
                "registration_note": "실제 스냅샷 생성 시각이 평가 기준. 기존 registered_at은 주장 이력이며 소급 성과로 사용하지 않음."}
    snapshot["integrity"] = digest(snapshot)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replace, within the workflow's single-writer slot.
    c.atomic_json(path, snapshot)
    return snapshot


def evaluate(snapshot, observations, evaluated_at=None):
    verify(snapshot)
    cutoff = instant(evaluated_at or datetime.now(timezone.utc).isoformat())
    captured = instant(snapshot["captured_at"])
    if cutoff < captured:
        raise ValueError("evaluation precedes snapshot")
    case = snapshot["case"]
    output = []
    for rule in case["decision_tests"]:
        candidate = next(x for x in case["candidates"] if x["ticker"] == rule["ticker"])
        selector = {"entity_id": candidate["entity_id"], "지표명": rule["metric"],
                    "period_end": rule["period_end"], "metric_kind": "actual",
                    "회계기준": rule["basis"], "단위": rule["unit"],
                    "통화": rule["currency"], "출처": rule["source"], "data_quality": "live"}
        result = {"ticker": rule["ticker"], "condition": rule["label"],
                  "period_end": rule["period_end"], "threshold": rule["threshold"],
                  "status": "평가 대기", "first": None, "latest": None}
        period_close = instant(rule["period_end"])
        if period_close <= captured:
            result["status"] = "사후 등록·성과 제외"
        else:
            matches = [r for r in observations if all(r.get(k) == v for k, v in selector.items())
                       and period_close < instant(r["as_of"]) <= cutoff
                       and metrics.number(r.get("현재값")) is not None
                       and r.get("출처URL", "").startswith("https://")]
            if len({metrics.series_key(r) for r in matches}) > 1:
                result["status"] = "정의 혼합·평가 보류"
            elif matches:
                matches.sort(key=lambda r: (instant(r["as_of"]), r.get("metric_id", "")))
                result.update(first=matches[0], latest=matches[-1])
                hit = review.OPERATORS[rule["operator"]](metrics.number(matches[0]["현재값"]),
                                                         metrics.number(rule["threshold"]))
                result["status"] = "반증 발동" if hit else "반증 미발동·적중 판정 아님"
        output.append(result)
    return output


def render():
    from gen_report import table
    snapshots = [verify(c.read_json(p, {})) for p in sorted(directory().glob("*.json"))]
    observations = c.read_live_rows("metric_log")
    output = ["# 사전 판단 복기\n\n실제 저장 시각부터 평가합니다. 최신 가설로 과거 조건을 덮어쓰지 않습니다. "
              "반증 미발동은 시장 대비 예측 적중이 아닙니다. 최초 관측 실적과 정정된 최신 값을 함께 보존합니다. "
              "실적은 원문 검증 후 원장에 입력해야 평가됩니다.\n"]
    if not snapshots:
        output.append("저장된 스냅샷 없음. 적중률 미측정.\n")
    for snapshot in sorted(snapshots, key=lambda x: instant(x["captured_at"])):
        output.append(f"## {snapshot['case']['title']}\n\n저장 {snapshot['captured_at']} / 개정 {snapshot['revision'][:12]}\n\n"
                      + snapshot["case"]["conclusion"] + "\n")
        output.append(table(["기업", "대상 기간", "고정 조건", "기준", "결과", "최초 관측", "최신 관측"],
            [[r["ticker"], r["period_end"], r["condition"], r["threshold"], r["status"],
              _observation(r["first"]), _observation(r["latest"])] for r in evaluate(snapshot, observations)]))
        output.append(f"\n당시 원장 관측 {len(snapshot['observations'])}개와 출처·판단·후속 행동을 스냅샷에 보존했습니다.\n")
    import research_returns
    output.append(research_returns.render())
    return "\n".join(output)


def _observation(row):
    return f"[{row['현재값']}]({row['출처URL']}) ({row['as_of']})" if row else "자료 없음"


def summary(case):
    path = directory() / (digest(case) + ".json")
    if not path.exists():
        return "현재 개정 스냅샷 미저장·성과 미측정"
    snapshot = verify(c.read_json(path, {}))
    results = evaluate(snapshot, c.read_live_rows("metric_log"))
    pending = sum(r["status"] == "평가 대기" for r in results)
    triggered = sum(r["status"] == "반증 발동" for r in results)
    return (f"판단 보존 {snapshot['captured_at'][:10]} / 현재 개정 조건 {len(results)}개: "
            f"대기 {pending}, 반증 발동 {triggered}. 주가 성과는 30/90/180일 별도 복기.")


def main():
    import research_cases
    from gen_report import save
    observations = c.read_live_rows("metric_log")
    for case in research_cases.load_cases():
        capture(case, observations)
    print(save("outcomes", render()))


if __name__ == "__main__":
    main()
