"""Collect raw discovery items from free public sources.

Phase 1 keeps the collector narrow: a small EDGAR query and a few RSS feeds.
Results are written to data/raw/discovery/latest.json for extract.py.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "discovery_sources.json"
RAW_DIR = ROOT / "data" / "raw" / "discovery"
USER_AGENT = "investment-research-system/0.1 contact=local-research@example.com"
TIMEOUT = 20


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"source config not found: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def fetch_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, application/rss+xml, application/xml, text/xml, */*",
        },
    )
    with urlopen(request, timeout=TIMEOUT) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def clean_text(value: str | None) -> str:
    text = unescape(value or "")
    return " ".join(text.replace("\n", " ").replace("\r", " ").split())


def text_from_child(item: ElementTree.Element, name: str) -> str:
    child = item.find(name)
    return clean_text(child.text if child is not None else "")


def collect_rss_source(source: dict) -> list[dict[str, str]]:
    xml_text = fetch_text(source["url"])
    root = ElementTree.fromstring(xml_text)
    items = root.findall("./channel/item")
    limit = int(source.get("limit", 5))
    records: list[dict[str, str]] = []
    for item in items[:limit]:
        title = text_from_child(item, "title")
        description = text_from_child(item, "description")
        records.append(
            {
                "source_type": "rss",
                "source_name": source.get("name", "RSS"),
                "title": title,
                "url": text_from_child(item, "link"),
                "published_at": text_from_child(item, "pubDate"),
                "raw_text": clean_text(f"{title}. {description}"),
            }
        )
    return records


def collect_edgar(config: dict) -> list[dict[str, str]]:
    if not config.get("enabled", True):
        return []
    params = {
        "q": config.get("query", "guidance OR backlog"),
        "from": "0",
        "size": str(config.get("limit", 5)),
    }
    forms = config.get("forms") or []
    if forms:
        params["forms"] = ",".join(forms)
    lookback_days = int(config.get("lookback_days", 30))
    if lookback_days > 0:
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=lookback_days)
        params["startdt"] = start.isoformat()
        params["enddt"] = end.isoformat()
    url = "https://efts.sec.gov/LATEST/search-index?" + urlencode(params)
    data = json.loads(fetch_text(url))
    hits = data.get("hits", {}).get("hits", [])
    records: list[dict[str, str]] = []
    for hit in hits[: int(config.get("limit", 5))]:
        source = hit.get("_source", {})
        company = ", ".join(source.get("display_names") or [])
        form = source.get("file_type") or source.get("form") or "SEC filing"
        filed_at = source.get("file_date", "")
        title = clean_text(f"{company} {form} {filed_at}")
        summary = clean_text(
            " ".join(
                str(source.get(key, ""))
                for key in ("biz_states", "sics", "items", "file_description")
            )
        )
        records.append(
            {
                "source_type": "edgar",
                "source_name": "SEC EDGAR",
                "title": title,
                "url": source.get("root_form", "") or url,
                "published_at": filed_at,
                "raw_text": clean_text(f"{title}. {summary}"),
            }
        )
    return records


def fallback_record(reason: str) -> dict[str, str]:
    return {
        "source_type": "fallback",
        "source_name": "local fallback",
        "title": "AI infrastructure capacity expansion and backlog monitoring seed",
        "url": "",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "raw_text": (
            "AI infrastructure suppliers report capacity expansion, backlog focus, "
            "lead time monitoring, and pricing discipline. "
            f"Collector fallback reason: {reason}"
        ),
    }


def write_payload(payload: dict) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RAW_DIR / f"collected_{stamp}.json"
    latest = RAW_DIR / "latest.json"
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
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
        items.append(fallback_record("; ".join(errors) or "no source returned records"))
        print("[warn] no public source records collected; wrote one local fallback seed")

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
