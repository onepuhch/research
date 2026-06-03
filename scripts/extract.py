"""Extract discovery signals from collected raw items into signal_log.csv.

The extractor is deliberately conservative for Phase 1. It uses deterministic
keyword rules so the local pipeline works without paid data or external
packages. LLM-backed extraction can be added later behind the same output
schema.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

RAW_LATEST = c.ROOT / "data" / "raw" / "discovery" / "latest.json"

SIGNAL_RULES: list[tuple[str, str, list[str]]] = [
    ("가이던스상향", "guidance", ["raise guidance", "guidance raised", "raised guidance", "guidance increase"]),
    ("수주/백로그", "backlog", ["backlog", "order book", "bookings", "long-term agreement", "prepayment"]),
    ("신규고객", "new customer", ["new customer", "design win", "wins customer", "customer win"]),
    ("CAPEX", "capex", ["capex", "capital expenditure", "capacity expansion", "capacity doubling", "capacity triple"]),
    ("ASP/가격", "pricing", ["pricing up", "price increase", "higher prices", "asp", "average selling price"]),
    ("리드타임", "lead time", ["lead time", "delivery time", "supply constrained", "sold out"]),
    ("EPS상향", "eps", ["eps", "estimate revision", "earnings revision", "consensus raised"]),
    ("기술로드맵", "roadmap", ["roadmap", "800g", "1.6t", "cpo", "co-packaged", "optical", "copper"]),
    ("공시(8-K)", "8-k", ["8-k", "sec filing", "edgar"]),
    ("커뮤니티", "community", ["reddit", "substack", "community"]),
]

THEME_RULES: list[tuple[str, list[str]]] = [
    ("AI 인프라", ["ai infrastructure", "accelerator", "gpu", "data center", "datacenter"]),
    ("반도체", ["semiconductor", "memory", "dram", "nand", "hbm", "foundry", "chip"]),
    ("전력 인프라", ["power", "grid", "transformer", "electricity"]),
    ("광통신", ["optical", "800g", "1.6t", "cpo", "transceiver"]),
]

GLOSSARY: dict[str, str] = {
    "backlog": "백로그: 이미 받은 주문 잔고로, 향후 매출 가시성을 보여준다.",
    "capex": "CAPEX: 설비투자. 공급 확대와 병목 해소 시점을 판단하는 단서다.",
    "asp": "ASP: 평균판매단가. 가격 결정력과 이익률 변화를 직접 보여준다.",
    "lead time": "리드타임: 주문부터 납품까지 걸리는 시간. 공급 부족이면 길어지는 경향이 있다.",
    "design win": "디자인윈: 고객 제품 설계에 채택됐다는 뜻으로, 향후 매출 전환 가능성이 있다.",
    "cpo": "CPO: 광부품을 칩 가까이에 붙이는 기술 방향으로, AI 네트워크 병목 이동을 볼 때 중요하다.",
}


def load_payload(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"collected payload not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def find_signal_type(text: str, source_type: str) -> str | None:
    lowered = normalize(text)
    for signal_type, _label, phrases in SIGNAL_RULES:
        if any(phrase in lowered for phrase in phrases):
            return signal_type
    if source_type == "edgar":
        return "공시(8-K)"
    return None


def infer_theme(text: str) -> str:
    lowered = normalize(text)
    for theme, phrases in THEME_RULES:
        if any(phrase in lowered for phrase in phrases):
            return theme
    return "미분류"


def infer_subject(title: str) -> str:
    title = title or ""
    ticker = re.search(r"\(([A-Z]{1,5})\)", title)
    if ticker:
        return ticker.group(1)
    if " - " in title:
        return title.rsplit(" - ", 1)[0][:40]
    return title[:40] or "미분류"


def score_item(text: str, signal_type: str) -> int:
    lowered = normalize(text)
    score = 0
    axes = [
        ["small cap", "underfollowed", "pure play"],
        ["margin", "profit", "eps", "earnings", "guidance"],
        ["supply constrained", "sold out", "pricing", "asp", "backlog", "lead time"],
        ["ai", "data center", "multi-year", "structural"],
        ["revision", "estimate", "consensus", "raised"],
        ["new customer", "capacity expansion", "coverage", "8-k", "design win"],
    ]
    for phrases in axes:
        hits = sum(1 for phrase in phrases if phrase in lowered)
        score += min(2, hits)
    if signal_type in {"가이던스상향", "EPS상향", "수주/백로그"}:
        score += 1
    return max(1, min(score, 12))


def tier_from_score(score: int) -> str:
    if score >= 10:
        return "A"
    if score >= 6:
        return "B"
    return "관망"


def stage_from_signal(signal_type: str, score: int) -> str:
    if signal_type in {"EPS상향", "가이던스상향"} and score >= 6:
        return "초기후반"
    if signal_type in {"수주/백로그", "ASP/가격", "리드타임"}:
        return "초기"
    return "관찰"


def explain_terms(text: str) -> str:
    lowered = normalize(text)
    explanations = [explanation for key, explanation in GLOSSARY.items() if key in lowered]
    return " / ".join(explanations[:2])


def summarize(item: dict[str, str], signal_type: str) -> str:
    title = item.get("title", "").strip()
    raw_text = item.get("raw_text", "").strip()
    summary = raw_text or title
    if len(summary) > 180:
        summary = summary[:177].rstrip() + "..."
    return f"{signal_type} 신호: {summary}"


def build_signal(item: dict[str, str]) -> dict[str, str] | None:
    raw_text = item.get("raw_text", "") or item.get("title", "")
    signal_type = find_signal_type(raw_text, item.get("source_type", ""))
    if signal_type is None:
        return None
    score = score_item(raw_text, signal_type)
    return {
        "날짜": date.today().isoformat(),
        "종목/티커": infer_subject(item.get("title", "")),
        "테마": infer_theme(raw_text),
        "신호유형": signal_type,
        "특이값 요약": summarize(item, signal_type),
        "upside_score": str(score),
        "티어": tier_from_score(score),
        "단계 추정": stage_from_signal(signal_type, score),
        "용어 풀이": explain_terms(raw_text),
        "출처": item.get("source_name", ""),
        "출처URL": item.get("url", ""),
    }


def fallback_signal(item: dict[str, str]) -> dict[str, str]:
    score = 1
    return {
        "날짜": date.today().isoformat(),
        "종목/티커": infer_subject(item.get("title", "")),
        "테마": infer_theme(item.get("raw_text", "")),
        "신호유형": "기타",
        "특이값 요약": summarize(item, "기타"),
        "upside_score": str(score),
        "티어": tier_from_score(score),
        "단계 추정": "관찰",
        "용어 풀이": "",
        "출처": item.get("source_name", ""),
        "출처URL": item.get("url", ""),
    }


def append_signals(signals: list[dict[str, str]]) -> None:
    rows = c.read_rows("signal_log")
    key = c.table_def("signal_log")["key"]
    for signal in signals:
        problems = c.validate_enums(signal)
        if problems:
            raise ValueError("enum validation failed:\n" + "\n".join(problems))
        signal[key] = c.next_id("signal_log")
        rows.append(signal)
        c.write_rows("signal_log", rows)


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else RAW_LATEST
    try:
        payload = load_payload(path)
        items = payload.get("items", [])
        if not isinstance(items, list):
            raise ValueError("'items' must be a list.")
        signals = [signal for item in items if isinstance(item, dict) for signal in [build_signal(item)] if signal]
        if not signals and items:
            signals = [fallback_signal(items[0])]
        if not signals:
            raise ValueError("no collected items available for extraction.")
        append_signals(signals)
    except Exception as error:
        print(f"[error] {error}")
        return 1

    print(f"[extracted] signal_log rows added: {len(signals)}")
    for signal in signals[:10]:
        print(
            f"- {signal['티어']} {signal['upside_score']} "
            f"{signal['신호유형']} | {signal['종목/티커']} | {signal['테마']}"
        )
    if len(signals) > 10:
        print(f"- ... {len(signals) - 10} more")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
