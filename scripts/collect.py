"""Collect raw discovery items from free public sources.

Phase 1 keeps the collector narrow: a small EDGAR query and a few RSS feeds.
Results are written to data/raw/discovery/latest.json for extract.py.
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

import common as c

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "discovery_sources.json"
RAW_DIR = ROOT / "data" / "raw" / "discovery"
USER_AGENT = "investment-research-system/0.1 contact=local-research@example.com"
TIMEOUT = 20
ENCODING = "utf-8-sig"
EDGAR_DOCUMENT_LIMIT = 2000
EDGAR_DOCUMENT_MAX_BYTES = 2_000_000
SEC_REQUEST_DELAY = 0.3


class TextExtractor(HTMLParser):
    """Extract visible text from a small SEC HTML document."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self.ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self.ignored_depth:
            self.ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth and data.strip():
            self.parts.append(data)


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"source config not found: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding=ENCODING))


def fetch_text(url: str, max_bytes: int | None = None) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, application/rss+xml, application/xml, text/xml, */*",
        },
    )
    with urlopen(request, timeout=TIMEOUT) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        content = response.read(max_bytes) if max_bytes else response.read()
        return content.decode(charset, errors="replace")


def clean_text(value: str | None) -> str:
    text = unescape(value or "")
    return " ".join(text.replace("\n", " ").replace("\r", " ").split())


def html_to_text(value: str) -> str:
    parser = TextExtractor()
    parser.feed(value)
    parser.close()
    return clean_text(" ".join(parser.parts))


def search_phrases(query: str) -> list[str]:
    quoted = [phrase.strip().lower() for phrase in re.findall(r'"([^"]+)"', query or "")]
    return [phrase for phrase in quoted if phrase]


def relevant_excerpt(text: str, phrases: list[str], limit: int = EDGAR_DOCUMENT_LIMIT) -> str:
    cleaned = clean_text(text)
    if len(cleaned) <= limit:
        return cleaned
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\s{2,}", cleaned) if part.strip()]
    matches = [
        sentence
        for sentence in sentences
        if any(phrase in sentence.lower() for phrase in phrases)
    ]
    selected = matches or sentences
    excerpt = " ".join(selected)
    if len(excerpt) < min(limit, 800) and matches:
        excerpt = " ".join([*matches, *sentences])
    return excerpt[:limit].rstrip()


def edgar_identity(hit: dict) -> tuple[str, str, str]:
    source = hit.get("_source", {})
    hit_id = str(hit.get("_id", "") or "")
    accession = str(source.get("adsh", "") or hit_id.split(":", 1)[0]).strip()
    ciks = source.get("ciks") or []
    cik = str(ciks[0] if ciks else "").strip()
    document_name = hit_id.split(":", 1)[1].strip() if ":" in hit_id else ""
    if not accession or not cik or not document_name:
        raise ValueError("EDGAR hit is missing accession, CIK, or document name")
    if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
        raise ValueError(f"invalid EDGAR accession: {accession}")
    if not cik.isdigit():
        raise ValueError(f"invalid EDGAR CIK: {cik}")
    return accession, str(int(cik)), document_name


def text_from_child(item: ElementTree.Element, name: str) -> str:
    child = item.find(name)
    return clean_text(child.text if child is not None else "")


def parse_rss_published_at(value: str, source_name: str, title: str) -> datetime | None:
    if not value:
        print(f"[warn] RSS item skipped: {source_name}: missing pubDate: {title or '(untitled)'}")
        return None
    try:
        published = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, OverflowError) as error:
        print(f"[warn] RSS item skipped: {source_name}: invalid pubDate {value!r}: {error}")
        return None
    if published.tzinfo is None:
        print(f"[warn] RSS item skipped: {source_name}: pubDate missing timezone {value!r}")
        return None
    return published.astimezone(timezone.utc)


def collect_rss_source(source: dict) -> list[dict[str, str]]:
    xml_text = fetch_text(source["url"])
    root = ElementTree.fromstring(xml_text)
    items = root.findall("./channel/item")
    limit = int(source.get("limit", 5))
    lookback_days = int(source.get("lookback_days", 14))
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    source_name = source.get("name", "RSS")
    records: list[dict[str, str]] = []
    for item in items:
        title = text_from_child(item, "title")
        description = text_from_child(item, "description")
        url = text_from_child(item, "link")
        published = parse_rss_published_at(text_from_child(item, "pubDate"), source_name, title)
        if published is None:
            continue
        if lookback_days > 0 and published < cutoff:
            continue
        records.append(
            {
                "source_type": "rss",
                "source_name": source_name,
                "source_id": url,
                "title": title,
                "url": url,
                "published_at": published.date().isoformat(),
                "raw_text": clean_text(f"{title}. {description}"),
            }
        )
        if len(records) >= limit:
            break
    return records


def collect_edgar(config: dict) -> list[dict[str, str]]:
    if not config.get("enabled", True):
        return []
    search_limit = int(config.get("search_limit", config.get("limit", 100)))
    max_pages = max(1, int(config.get("max_pages", 1)))
    base_params = {
        "q": config.get("query", "guidance OR backlog"),
    }
    forms = config.get("forms") or []
    if forms:
        base_params["forms"] = ",".join(forms)
    lookback_days = int(config.get("lookback_days", 30))
    if lookback_days > 0:
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=lookback_days)
        base_params["startdt"] = start.isoformat()
        base_params["enddt"] = end.isoformat()
    hits: list[dict] = []
    for page in range(max_pages):
        offset = page * 100
        if offset >= search_limit:
            break
        size = min(100, search_limit - offset)
        params = {**base_params, "from": str(offset), "size": str(size)}
        url = "https://efts.sec.gov/LATEST/search-index?" + urlencode(params)
        try:
            data = json.loads(fetch_text(url))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            print(f"[warn] EDGAR search page skipped: from={offset} size={size}: {error}")
            continue
        page_hits = data.get("hits", {}).get("hits", [])
        if not isinstance(page_hits, list):
            print(f"[warn] EDGAR search page skipped: from={offset}: invalid hits payload")
            continue
        hits.extend(page_hits)
        if len(page_hits) < size:
            break
    records: list[dict[str, str]] = []
    seen_accessions: set[str] = set()
    phrases = search_phrases(str(config.get("query", "")))
    for hit in hits:
        source = hit.get("_source", {})
        try:
            accession, cik, document_name = edgar_identity(hit)
        except ValueError as error:
            print(f"[warn] EDGAR hit skipped: {error}")
            continue
        if accession in seen_accessions:
            continue
        company = ", ".join(source.get("display_names") or [])
        if c.is_megacap(company):
            seen_accessions.add(accession)
            print(f"[prefilter] EDGAR megacap skipped before fetch: {company} {accession}")
            continue
        accession_compact = accession.replace("-", "")
        filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_compact}/"
        document_url = filing_url + quote(document_name)
        try:
            time.sleep(SEC_REQUEST_DELAY)
            document_html = fetch_text(document_url, EDGAR_DOCUMENT_MAX_BYTES)
            document_text = relevant_excerpt(html_to_text(document_html), phrases)
            if not document_text:
                raise ValueError("empty filing document text")
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            print(f"[warn] EDGAR filing skipped: {accession}: {error}")
            continue
        form = source.get("file_type") or source.get("form") or "SEC filing"
        filed_at = source.get("file_date", "")
        title = clean_text(f"{company} {form} {filed_at}")
        records.append(
            {
                "source_type": "edgar",
                "source_name": "SEC EDGAR",
                "source_id": accession,
                "title": title,
                "url": filing_url,
                "published_at": filed_at,
                "raw_text": clean_text(f"{title}. {document_text}")[:EDGAR_DOCUMENT_LIMIT],
            }
        )
        seen_accessions.add(accession)
    return records


def write_payload(payload: dict) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RAW_DIR / f"collected_{stamp}.json"
    latest = RAW_DIR / "latest.json"
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(text, encoding=ENCODING)
    latest.write_text(text, encoding=ENCODING)
    return path


def main() -> int:
    try:
        config = load_config()
    except Exception as error:
        print(f"[error] {error}")
        return 1

    items: list[dict[str, str]] = []
    errors: list[str] = []

    try:
        edgar_items = collect_edgar(config.get("edgar", {}))
        items.extend(edgar_items)
        print(f"[collected] EDGAR: {len(edgar_items)}")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as error:
        errors.append(f"EDGAR: {error}")
        print(f"[warn] EDGAR failed: {error}")

    for source in config.get("rss", []):
        try:
            rss_items = collect_rss_source(source)
            items.extend(rss_items)
            print(f"[collected] {source.get('name', 'RSS')}: {len(rss_items)}")
            time.sleep(0.3)
        except (HTTPError, URLError, TimeoutError, ElementTree.ParseError, ValueError) as error:
            errors.append(f"{source.get('name', 'RSS')}: {error}")
            print(f"[warn] RSS failed: {source.get('name', 'RSS')}: {error}")

    if not items:
        reason = "; ".join(errors) or "no source returned records"
        print(f"[warn] no public source records collected; items left empty: {reason}")

    payload = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "item_count": len(items),
        "errors": errors,
        "items": items,
    }
    path = write_payload(payload)
    print(f"[saved] {path}")
    print(f"[saved] {RAW_DIR / 'latest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
