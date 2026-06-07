"""Collect Reddit ticker buzz into an ISOLATED watch file (not signal_log).

레딧은 노이즈가 많아 메인 발굴 원장(signal_log)에 섞지 않는다. 이 스크립트는
공개 RSS 피드(키 불필요)로 인기글을 긁어 종목 언급 빈도를 집계하고,
data/processed/reddit_watch.csv 에 따로 쌓는다. 사람이 보고 판단해, 진짜다 싶은
종목만 수동으로 메인 발굴 RUN(§9)으로 승격한다.

참고: 레딧 .json 엔드포인트는 현재 403 차단이라 .rss(Atom)를 쓴다. RSS에는
upvote/댓글 수가 없어 '언급 빈도'를 핵심 신호로 본다.

신뢰도를 위해 종목 후보는: (1) 캐시태그 $TICKER 는 항상 인정,
(2) 일반 대문자 토큰은 같은 실행에서 캐시태그로도 등장한 것만 인정(노이즈 컷).
표준 라이브러리만 사용한다.
"""
from __future__ import annotations

import csv
import json
import re
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timezone
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "reddit_sources.json"
RAW_DIR = ROOT / "data" / "raw" / "discovery"
OUT_CSV = ROOT / "data" / "processed" / "reddit_watch.csv"
TICKER_CACHE = RAW_DIR / "sec_tickers.json"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_UA = "investment-research-system research@example.com"  # SEC는 연락처 포함 UA를 요구
TIMEOUT = 20
ATOM = "{http://www.w3.org/2005/Atom}"
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

CASHTAG = re.compile(r"\$([A-Za-z]{1,5})\b")
CAPS = re.compile(r"\b([A-Z]{2,5})\b")
TAG = re.compile(r"<[^>]+>")

FIELDS = [
    "날짜", "종목후보", "언급수", "서브레딧", "대표글제목", "대표URL", "신호메모",
]


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"reddit source config not found: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def strip_html(value: str) -> str:
    return " ".join(unescape(TAG.sub(" ", value or "")).split())


def load_ticker_universe() -> set[str]:
    """SEC 전체 티커 목록(무료). 캐시가 있으면 재사용, 없으면 1회 다운로드."""
    text = ""
    if TICKER_CACHE.exists():
        text = TICKER_CACHE.read_text(encoding="utf-8")
    else:
        try:
            request = Request(SEC_TICKERS_URL, headers={"User-Agent": SEC_UA, "Accept": "application/json"})
            with urlopen(request, timeout=TIMEOUT) as response:
                text = response.read().decode("utf-8", errors="replace")
            RAW_DIR.mkdir(parents=True, exist_ok=True)
            TICKER_CACHE.write_text(text, encoding="utf-8")
            print(f"[downloaded] SEC ticker universe -> {TICKER_CACHE}")
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            print(f"[warn] SEC 티커 목록 다운로드 실패(캐시태그만 사용): {error}")
            return set()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return set()
    universe: set[str] = set()
    for record in data.values():
        ticker = str(record.get("ticker", "")).upper().strip()
        if ticker.isalpha() and 1 <= len(ticker) <= 5:
            universe.add(ticker)
    return universe


def fetch_entries(subreddit: str, listing: str, limit: int, user_agent: str) -> list[dict]:
    url = f"https://www.reddit.com/r/{subreddit}/{listing}/.rss?limit={int(limit)}"
    request = Request(url, headers={"User-Agent": user_agent, "Accept": "application/atom+xml, application/xml, */*"})
    with urlopen(request, timeout=TIMEOUT) as response:
        xml_text = response.read().decode("utf-8", errors="replace")
    root = ElementTree.fromstring(xml_text)
    entries: list[dict] = []
    for entry in root.findall(f"{ATOM}entry"):
        title_el = entry.find(f"{ATOM}title")
        content_el = entry.find(f"{ATOM}content")
        link_el = entry.find(f"{ATOM}link")
        title = (title_el.text or "") if title_el is not None else ""
        content = strip_html(content_el.text if content_el is not None else "")
        link = link_el.get("href", "") if link_el is not None else ""
        entries.append({"title": title, "content": content, "url": link})
    return entries


def extract_tickers(text: str, stoplist: set[str], confirmed: set[str]) -> set[str]:
    """캐시태그는 항상 인정. 일반 대문자 토큰은 confirmed(캐시태그로도 본 것)만 인정."""
    found: set[str] = set()
    for match in CASHTAG.findall(text or ""):
        ticker = match.upper()
        if ticker not in stoplist:
            found.add(ticker)
    for match in CAPS.findall(text or ""):
        ticker = match.upper()
        if ticker in confirmed and ticker not in stoplist:
            found.add(ticker)
    return found


def entry_text(entry: dict) -> str:
    return f"{entry.get('title', '')} {entry.get('content', '')}"


def main() -> int:
    try:
        config = load_config()
    except Exception as error:
        print(f"[error] {error}")
        return 1

    stoplist = {str(t).upper() for t in config.get("ticker_stoplist", [])}
    user_agent = config.get("user_agent", BROWSER_UA) or BROWSER_UA
    listing = config.get("listing", "hot")
    min_mentions = int(config.get("min_mentions", 2))

    entries: list[dict] = []
    errors: list[str] = []
    for source in config.get("subreddits", []):
        name = source.get("name")
        if not name:
            continue
        try:
            fetched = fetch_entries(name, listing, source.get("limit", 30), user_agent)
            for entry in fetched:
                entry["_subreddit"] = name
            entries.extend(fetched)
            print(f"[collected] r/{name}: {len(fetched)}")
            time.sleep(1.0)  # 레딧 예의상 호출 간격
        except (HTTPError, URLError, TimeoutError, ElementTree.ParseError, ValueError) as error:
            errors.append(f"r/{name}: {error}")
            print(f"[warn] r/{name} failed: {error}")

    if not entries:
        print("[error] 레딧에서 가져온 글이 없습니다. (IP 차단/네트워크 확인)")
        return 1

    # 노이즈 컷 기준: 실제 존재하는 SEC 티커(무료 목록) + 이번 실행의 캐시태그
    universe = load_ticker_universe()
    confirmed: set[str] = set(universe)
    for entry in entries:
        for match in CASHTAG.findall(entry_text(entry)):
            ticker = match.upper()
            if ticker not in stoplist:
                confirmed.add(ticker)
    print(f"[universe] SEC 티커 {len(universe)}개 로드")

    # 2차: 종목별 집계
    agg: dict[str, dict] = defaultdict(
        lambda: {"mentions": 0, "subs": set(), "title": "", "url": "", "cashtag": False}
    )
    for entry in entries:
        text = entry_text(entry)
        tickers = extract_tickers(text, stoplist, confirmed)
        if not tickers:
            continue
        cashtags = {m.upper() for m in CASHTAG.findall(text)}
        for ticker in tickers:
            row = agg[ticker]
            row["mentions"] += 1
            row["subs"].add(entry.get("_subreddit", ""))
            if ticker in cashtags:
                row["cashtag"] = True
            if not row["title"]:
                row["title"] = entry.get("title", "")
                row["url"] = entry.get("url", "")

    today = date.today().isoformat()
    rows = []
    for ticker, data in agg.items():
        if data["mentions"] < min_mentions:
            continue
        note = "캐시태그($) 확인" if data["cashtag"] else "대문자 토큰(확인필요)"
        rows.append({
            "날짜": today,
            "종목후보": ticker,
            "언급수": data["mentions"],
            "서브레딧": " ".join(sorted(s for s in data["subs"] if s)),
            "대표글제목": data["title"][:160],
            "대표URL": data["url"],
            "신호메모": note,
        })
    rows.sort(key=lambda r: (r["언급수"], r["신호메모"]), reverse=True)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    # 원본 스냅샷도 보관(gitignore된 raw 폴더)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = RAW_DIR / "reddit_latest.json"
    snapshot.write_text(
        json.dumps(
            {"collected_at": datetime.now(timezone.utc).isoformat(), "entry_count": len(entries), "errors": errors},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )

    print(f"[saved] {OUT_CSV} - 종목후보 {len(rows)}개 (글 {len(entries)}개에서 집계)")
    for row in rows[:10]:
        print(f"- {row['종목후보']}: 언급 {row['언급수']} / {row['서브레딧']} / {row['신호메모']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
