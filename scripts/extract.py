"""Extract discovery signals from collected raw items into signal_log.csv.

Gemini Flash is used when GEMINI_API_KEY is available from the environment or
from a local .env file. If the key is missing or a Gemini request fails, the
deterministic keyword stub is used so the local pipeline keeps working without
external packages.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

RAW_LATEST = c.ROOT / "data" / "raw" / "discovery" / "latest.json"
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_TIMEOUT = 30
# 무료티어 429 방지: 호출 사이 대기(초) + 429/503 지수 백오프 재시도 횟수
GEMINI_SLEEP = float(os.environ.get("GEMINI_SLEEP", "4"))
GEMINI_MAX_RETRIES = int(os.environ.get("GEMINI_MAX_RETRIES", "3"))
RETRY_STATUS = {429, 500, 502, 503, 504}

# 시장이 이미 다 아는 메가캡 — 소외축 0 + 티어 A 금지 (소형주 발굴이 목표)
MEGA_CAP_TICKERS = {
    "NVDA", "GOOGL", "GOOG", "MSFT", "AMZN", "AAPL", "META", "TSLA",
    "AVGO", "AMD", "TSM", "ORCL", "NFLX", "INTC", "QCOM", "TXN", "CSCO",
    "IBM", "ADBE", "CRM", "MU", "ASML", "SMCI", "DELL", "ARM",
}
MEGA_CAP_NAMES = {
    "alphabet", "google", "microsoft", "amazon", "apple", "meta", "tesla",
    "nvidia", "broadcom", "oracle", "netflix", "intel", "qualcomm", "cisco",
    "advanced micro devices", "micron", "asml", "taiwan semiconductor",
}

SIGNAL_TYPES = c.ENUMS["신호유형"]
TIERS = c.ENUMS["티어"]
STAGES = c.ENUMS.get("현재 단계", ["관찰", "초기", "초기후반", "중기", "후기", "제외"])

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
    "backlog": "백로그: 이미 받은 주문 잔고로, 향후 매출 가시성을 보여주는 단서다.",
    "capex": "CAPEX: 설비투자. 공급 확대와 병목 해소 시점을 판단하는 단서다.",
    "asp": "ASP: 평균판매단가. 가격 결정력과 이익률 변화를 직접 보여준다.",
    "lead time": "리드타임: 주문부터 납품까지 걸리는 시간. 길어지면 공급 부족 신호일 수 있다.",
    "design win": "디자인윈: 고객 제품 설계에 채택됐다는 뜻으로, 향후 매출 전환 가능성이 있다.",
    "cpo": "CPO: 광모듈을 칩 가까이에 붙이는 기술 방향으로, AI 네트워크 병목 이동을 보는 단서다.",
}

AXES: tuple[tuple[str, str], ...] = (
    ("underfollowed_pure_play", "소외/순수노출"),
    ("earnings_leverage", "실적 레버리지"),
    ("supply_demand_tightness", "수급 타이트함"),
    ("structural_ai_demand", "구조적 AI 수요"),
    ("revision_momentum", "추정치 상향 모멘텀"),
    ("catalyst_visibility", "촉매 가시성"),
)

SIGNAL_ALIASES = {
    "guidance": "가이던스상향",
    "guidance_raise": "가이던스상향",
    "backlog": "수주/백로그",
    "order": "수주/백로그",
    "new_customer": "신규고객",
    "customer_win": "신규고객",
    "capex": "CAPEX",
    "pricing": "ASP/가격",
    "asp": "ASP/가격",
    "lead_time": "리드타임",
    "eps": "EPS상향",
    "estimate_revision": "EPS상향",
    "roadmap": "기술로드맵",
    "8-k": "공시(8-K)",
    "filing": "공시(8-K)",
    "community": "커뮤니티",
    "other": "기타",
}


def load_payload(path: Path) -> dict[str, Any]:
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


def infer_subject(title: str, raw_text: str = "", source_type: str = "") -> str:
    text = " ".join(part for part in [title or "", raw_text or ""] if part)

    ticker_patterns = [
        r"\(([A-Z]{1,5})\)",
        r"\b(?:NASDAQ|NYSE|AMEX|OTC|TSX|LSE|KRX)\s*[:：]\s*([A-Z0-9]{1,8})\b",
        r"\$([A-Z]{1,5})\b",
    ]
    for pattern in ticker_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)

    if source_type == "edgar":
        company_match = re.match(r"\s*([^()]{3,80}?)\s+\(CIK\s+\d+\)", title or "", re.IGNORECASE)
        if company_match:
            return company_match.group(1).strip(" ,")

    return "미분류"


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


def summarize(item: dict[str, Any], signal_type: str) -> str:
    title = str(item.get("title", "")).strip()
    raw_text = str(item.get("raw_text", "")).strip()
    summary = raw_text or title
    if len(summary) > 180:
        summary = summary[:177].rstrip() + "..."
    return f"{signal_type} 신호: {summary}"


def is_unnamed_subject(subject: Any) -> bool:
    return clean_text(subject) in {"", "미분류"}


def cap_unnamed_subject_tier(subject: Any, tier: str) -> str:
    if is_unnamed_subject(subject) and tier == "A":
        return "B"
    return tier


def build_keyword_signal(item: dict[str, Any]) -> dict[str, str] | None:
    raw_text = str(item.get("raw_text", "") or item.get("title", ""))
    signal_type = find_signal_type(raw_text, str(item.get("source_type", "")))
    if signal_type is None:
        return None
    score = score_item(raw_text, signal_type)
    subject = infer_subject(str(item.get("title", "")), raw_text, str(item.get("source_type", "")))
    tier = cap_unnamed_subject_tier(subject, tier_from_score(score))
    return {
        "날짜": date.today().isoformat(),
        "종목/티커": subject,
        "테마": infer_theme(raw_text),
        "신호유형": signal_type,
        "특이값 요약": summarize(item, signal_type),
        "upside_score": str(score),
        "티어": tier,
        "단계 추정": stage_from_signal(signal_type, score),
        "용어 풀이": explain_terms(raw_text),
        "출처": str(item.get("source_name", "")),
        "출처URL": str(item.get("url", "")),
    }


def fallback_signal(item: dict[str, Any]) -> dict[str, str]:
    score = 1
    raw_text = str(item.get("raw_text", ""))
    subject = infer_subject(str(item.get("title", "")), raw_text, str(item.get("source_type", "")))
    tier = cap_unnamed_subject_tier(subject, tier_from_score(score))
    return {
        "날짜": date.today().isoformat(),
        "종목/티커": subject,
        "테마": infer_theme(raw_text),
        "신호유형": "기타",
        "특이값 요약": summarize(item, "기타"),
        "upside_score": str(score),
        "티어": tier,
        "단계 추정": "관찰",
        "용어 풀이": "",
        "출처": str(item.get("source_name", "")),
        "출처URL": str(item.get("url", "")),
    }


def gemini_prompt(item: dict[str, Any]) -> str:
    axis_lines = "\n".join(f"- {key}: {label} (0, 1, 2)" for key, label in AXES)
    return f"""아래 수집 항목에서 투자 발굴 신호를 JSON만으로 추출하라.

규칙:
- 종목/티커는 실제 회사명 또는 티커를 찾을 수 있을 때만 작성한다. 뉴스 헤드라인, 기사 제목, 언론사명, 일반 테마명은 절대 종목/티커로 쓰지 말고 "미분류"로 둔다.
- 우리는 "시장이 아직 모르는 소형주"를 찾는다. 잘 알려진 메가캡(시총 수천억 달러 이상: NVDA, GOOGL/GOOG, MSFT, AMZN, AAPL, META, TSLA, AVGO, AMD, TSM, MU, ASML, ORCL 등)은 이미 시장이 다 안다. 이런 종목은 underfollowed_pure_play(소외/순수노출)를 반드시 0으로 주고, 티어를 절대 A로 주지 않는다(최대 B).
- 신호유형은 다음 중 하나만 사용한다: {", ".join(SIGNAL_TYPES)}
- 티어는 다음 중 하나만 사용한다: {", ".join(TIERS)}
- 단계는 다음 중 하나만 사용한다: {", ".join(STAGES)}
- 특이값 요약과 용어 풀이는 한국어로 쓴다.
- upside_axes는 각 축 0~2점이며 총점은 0~12점이다.

upside 6축:
{axis_lines}

응답 JSON 형식:
{{
  "subject": "회사명 또는 TICKER 또는 미분류",
  "theme": "테마 또는 미분류",
  "signal_type": "신호유형 enum",
  "special_value_summary": "한국어 한 문장",
  "upside_axes": {{
    "underfollowed_pure_play": 0,
    "earnings_leverage": 0,
    "supply_demand_tightness": 0,
    "structural_ai_demand": 0,
    "revision_momentum": 0,
    "catalyst_visibility": 0
  }},
  "upside_score": 0,
  "tier": "A|B|관망",
  "stage": "관찰|초기|초기후반|중기|후기|제외",
  "glossary": "어려운 용어 1~2개 풀이"
}}

수집 항목:
{json.dumps(item, ensure_ascii=False, indent=2)[:6000]}
"""


def call_gemini(item: dict[str, Any], api_key: str) -> dict[str, Any]:
    body = {
        "contents": [{"role": "user", "parts": [{"text": gemini_prompt(item)}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{quote(GEMINI_MODEL)}:generateContent"
    request = Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    delay = 5.0
    payload: dict[str, Any] = {}
    for attempt in range(GEMINI_MAX_RETRIES + 1):
        try:
            with urlopen(request, timeout=GEMINI_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except HTTPError as error:
            if error.code in RETRY_STATUS and attempt < GEMINI_MAX_RETRIES:
                print(f"[retry] Gemini {error.code}; {delay:.0f}s 대기 ({attempt + 1}/{GEMINI_MAX_RETRIES})")
                time.sleep(delay)
                delay *= 2
                continue
            raise
        except (URLError, TimeoutError):
            if attempt < GEMINI_MAX_RETRIES:
                print(f"[retry] Gemini 네트워크 오류; {delay:.0f}s 대기 ({attempt + 1}/{GEMINI_MAX_RETRIES})")
                time.sleep(delay)
                delay *= 2
                continue
            raise

    parts = payload["candidates"][0]["content"]["parts"]
    text = "".join(str(part.get("text", "")) for part in parts)
    return parse_json_object(text)


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        data = json.loads(cleaned[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("Gemini response JSON must be an object.")
    return data


def clamp_int(value: Any, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(number, maximum))


def clean_text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def normalize_signal_type(value: Any, item: dict[str, Any]) -> str:
    text = clean_text(value)
    if text in SIGNAL_TYPES:
        return text
    alias = SIGNAL_ALIASES.get(normalize(text).replace(" ", "_"))
    if alias in SIGNAL_TYPES:
        return alias
    raw_text = str(item.get("raw_text", "") or item.get("title", ""))
    return find_signal_type(raw_text, str(item.get("source_type", ""))) or "기타"


def normalize_subject(value: Any, item: dict[str, Any]) -> str:
    subject = clean_text(value, "미분류")
    title = str(item.get("title", "")).strip()
    if subject == title or len(subject) > 80 or looks_like_headline(subject):
        subject = infer_subject(title, str(item.get("raw_text", "")), str(item.get("source_type", "")))
    return subject or "미분류"


def is_megacap(subject: str) -> bool:
    """유명 메가캡이면 True. 티커(단어 경계)·회사명 부분일치 둘 다 본다."""
    if not subject:
        return False
    upper = subject.upper()
    for ticker in MEGA_CAP_TICKERS:
        if re.search(rf"\b{re.escape(ticker)}\b", upper):
            return True
    lowered = subject.lower()
    return any(name in lowered for name in MEGA_CAP_NAMES)


def looks_like_headline(value: str) -> bool:
    lowered = normalize(value)
    headline_terms = [
        "why should",
        "what is",
        "investors care",
        "breaking",
        "exclusive",
        "report:",
        "news",
        "article",
    ]
    return any(term in lowered for term in headline_terms)


def normalize_axes(value: Any) -> dict[str, int]:
    source = value if isinstance(value, dict) else {}
    return {key: clamp_int(source.get(key, 0), 0, 2) for key, _label in AXES}


def axis_summary(axes: dict[str, int]) -> str:
    labels = {key: label for key, label in AXES}
    return ", ".join(f"{labels[key]} {score}" for key, score in axes.items())


def build_gemini_signal(item: dict[str, Any], api_key: str) -> dict[str, str]:
    data = call_gemini(item, api_key)
    subject = normalize_subject(data.get("subject"), item)
    megacap = is_megacap(subject)
    signal_type = normalize_signal_type(data.get("signal_type"), item)
    axes_source = data.get("upside_axes")
    axes = normalize_axes(axes_source)
    if megacap:  # 메가캡은 소외/순수노출 가치가 없다 → 0 강제
        axes["underfollowed_pure_play"] = 0
    score = sum(axes.values()) if isinstance(axes_source, dict) else clamp_int(data.get("upside_score"), 1, 12)
    score = max(1, min(score, 12))

    # 티어는 점수에서 결정론적으로 뽑는다(루브릭=점수 기반). Gemini의 tier 필드는
    # 점수와 어긋날 수 있어 신뢰하지 않는다(예: 점수7인데 관망 반환 문제).
    tier = tier_from_score(score)
    if megacap and tier == "A":  # 유명 메가캡은 티어 A 금지 (최대 B)
        tier = "B"
    tier = cap_unnamed_subject_tier(subject, tier)

    stage = clean_text(data.get("stage"))
    if stage not in STAGES:
        stage = stage_from_signal(signal_type, score)

    summary = clean_text(data.get("special_value_summary"), summarize(item, signal_type))
    summary = f"{summary[:240].rstrip()} | 6축: {axis_summary(axes)}"

    return {
        "날짜": date.today().isoformat(),
        "종목/티커": subject,
        "테마": clean_text(data.get("theme"), infer_theme(str(item.get("raw_text", ""))))[:60],
        "신호유형": signal_type,
        "특이값 요약": summary[:360],
        "upside_score": str(score),
        "티어": tier,
        "단계 추정": stage,
        "용어 풀이": clean_text(data.get("glossary"), explain_terms(str(item.get("raw_text", ""))))[:240],
        "출처": str(item.get("source_name", "")),
        "출처URL": str(item.get("url", "")),
    }


def build_signal(item: dict[str, Any], api_key: str = "") -> dict[str, str] | None:
    if api_key:
        try:
            return build_gemini_signal(item, api_key)
        except (HTTPError, URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError, ValueError) as error:
            print(f"[warn] Gemini extraction failed; using keyword fallback: {error}")
    return build_keyword_signal(item)


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
        api_key = c.load_dotenv_value("GEMINI_API_KEY")
        dict_items = [item for item in items if isinstance(item, dict)]
        signals: list[dict[str, str]] = []
        for index, item in enumerate(dict_items):
            signal = build_signal(item, api_key)
            if signal:
                signals.append(signal)
            # 무료티어 429 방지: Gemini를 쓸 때만 호출 사이 대기 (마지막 항목 제외)
            if api_key and index < len(dict_items) - 1:
                time.sleep(GEMINI_SLEEP)
        if not signals and items:
            signals = [fallback_signal(items[0])]
        if not signals:
            raise ValueError("no collected items available for extraction.")
        append_signals(signals)
    except Exception as error:
        print(f"[error] {error}")
        return 1

    source = "Gemini Flash" if c.load_dotenv_value("GEMINI_API_KEY") else "keyword fallback"
    print(f"[extracted] signal_log rows added: {len(signals)} ({source})")
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
