"""Official company documents from SEC EDGAR: a paced client, filing selection,
HTML normalization that keeps tables, and immutable document records.

Only SEC hosts are fetched here. Registered IR domains may be added later as an
optional path; search results and model-made URLs are never followed.

Documents: data/processed/company_documents/{DOC-id}.json.gz, one per
issuer + accession + document path + content SHA256. A corrected body of the same
URL is a new DOC; the old one stays.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler

import common as c

NORMALIZATION_VERSION = "norm-v1"
SEC_HOSTS = ("sec.gov",)
MIN_INTERVAL_S = 0.5   # at most 2 requests per second, one at a time (SEC allows 10)
EARNINGS_ITEMS = ("2.02",)
EARNINGS_WORDS = ("results", "revenue", "net income", "earnings per share", "outlook", "guidance",
                  "quarter", "fiscal", "operating income", "net sales")
_last_request = [0.0]


def pace(url: str, clock=time.monotonic, sleep=time.sleep) -> None:
    """Shared SEC pacing for this process (collect.py uses it too)."""
    host = urlparse(url).hostname or ""
    if not any(host == h or host.endswith("." + h) for h in SEC_HOSTS):
        return
    wait = _last_request[0] + MIN_INTERVAL_S - clock()
    if wait > 0:
        sleep(wait)
    _last_request[0] = clock()


def documents_dir() -> Path:
    return c.DATA_DIR / "company_documents"


class Budget(Exception):
    """Stopped before a request: daily HTTP attempts or the step's time budget are used up."""


class Blocked(Exception):
    """SEC refused repeatedly (403): stop this provider for the run."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def direct_open(request, timeout):
    return build_opener(NoRedirect()).open(request, timeout=timeout)


def sec_url(url):
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return parsed.scheme == "https" and (host == "sec.gov" or host.endswith(".sec.gov")) and not parsed.username


@dataclass
class SecClient:
    user_agent: str
    attempts_left: int
    deadline: float
    max_bytes: int = 2_000_000
    timeout_s: float = 15.0
    clock: object = time.monotonic
    sleep: object = time.sleep
    opener: object = direct_open
    on_attempt: object = None
    forbidden: int = 0
    attempts: int = 0
    log: list = field(default_factory=list)

    def _spend(self):
        if self.attempts_left <= 0:
            raise Budget("daily_http_attempts")
        if self.clock() >= self.deadline:
            raise Budget("time_budget")
        if self.on_attempt:
            self.on_attempt()
        self.attempts_left -= 1
        self.attempts += 1

    def get(self, url):
        retries, redirects = 0, 0
        while True:
            if not sec_url(url):
                raise ValueError("only https SEC URLs are fetched")
            pace(url, self.clock, self.sleep)
            self._spend()
            request = Request(url, headers={"User-Agent": self.user_agent, "Accept-Encoding": "identity"})
            try:
                with self.opener(request, timeout=min(self.timeout_s, self.deadline - self.clock())) as response:
                    body = response.read(self.max_bytes + 1)
                    final = response.geturl() if hasattr(response, "geturl") else url
                if self.clock() >= self.deadline:
                    raise Budget("time_budget")
                if final != url:
                    raise ValueError("uncontrolled redirect")
                self.log.append({"url": url, "status": 200})
                return body[:self.max_bytes], final, len(body) > self.max_bytes
            except HTTPError as error:
                self.log.append({"url": url, "status": error.code})
                if error.code in (301, 302, 303, 307, 308):
                    redirects += 1
                    if redirects > 3 or not error.headers.get("Location"):
                        raise ValueError("redirect limit or missing target") from None
                    url = urljoin(url, error.headers["Location"])
                    continue
                if error.code == 403:
                    self.forbidden += 1
                    if self.forbidden >= 2:
                        raise Blocked("sec_403") from None
                    raise
                if error.code not in (429, 500, 502, 503, 504) or retries >= 1:
                    raise
                try:
                    wait = max(0.0, float((error.headers or {}).get("Retry-After") or 2))
                except ValueError:
                    raise Budget("unsupported_retry_after") from None
                if self.clock() + wait >= self.deadline:
                    raise Budget("retry_after_exceeds_budget") from None
                self.sleep(wait)
                retries += 1
            except (URLError, TimeoutError, OSError):
                if retries >= 1:
                    raise
                retries += 1


# ------------------------------------------------------------------ filings

def cik10(value) -> str:
    digits = re.sub(r"\D", "", str(value))
    if not digits or len(digits) > 10:
        raise ValueError(f"invalid CIK {value!r}")
    return digits.zfill(10)


def submissions_url(cik: str) -> str:
    return f"https://data.sec.gov/submissions/CIK{cik10(cik)}.json"


def recent_filings(submissions: dict, today: date, days: int = 120) -> list[dict]:
    """Recent 8-K/6-K results and 10-Q/10-K/20-F reports, newest first, earnings releases first."""
    recent = (submissions.get("filings") or {}).get("recent") or {}
    keys = ("accessionNumber", "filingDate", "reportDate", "form", "primaryDocument", "primaryDocDescription", "items")
    rows = [dict(zip(keys, values)) for values in zip(*(recent.get(k) or [] for k in keys))]
    chosen = []
    for row in rows:
        try:
            filed = date.fromisoformat(row["filingDate"])
        except (TypeError, ValueError):
            continue
        if not 0 <= (today - filed).days <= days:
            continue
        form = row["form"]
        items = str(row.get("items") or "")
        if form == "8-K" and any(i in items for i in EARNINGS_ITEMS):
            rank = 0
        elif form == "6-K":
            rank = 1
        elif form in ("10-Q", "10-K", "20-F", "40-F"):
            rank = 2
        else:
            continue
        chosen.append({**row, "rank": rank})
    chosen.sort(key=lambda r: r["filingDate"], reverse=True)
    chosen.sort(key=lambda r: r["rank"])  # stable: newest first within each kind
    return chosen


def filing_index_url(cik: str, accession: str) -> str:
    return (f"https://www.sec.gov/Archives/edgar/data/{int(cik10(cik))}/{accession.replace('-', '')}/"
            f"{accession}-index.htm")


class _IndexParser(HTMLParser):
    """Rows of the EDGAR filing index table: Seq, Description, Document(link), Type, Size."""

    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell, self.href, self.in_cell = [], None, [], None, False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.in_cell, self.cell, self.href = True, [], None
        elif tag == "a" and self.in_cell:
            self.href = dict(attrs).get("href")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.row is not None:
            self.row.append({"text": " ".join("".join(self.cell).split()), "href": self.href})
            self.in_cell = False
        elif tag == "tr" and self.row:
            self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.in_cell:
            self.cell.append(data)


def filing_documents(index_html: str, base_url: str) -> list[dict]:
    parser = _IndexParser()
    parser.feed(index_html)
    docs = []
    for row in parser.rows:
        if len(row) < 4 or not row[2]["href"]:
            continue
        href = row[2]["href"]
        if href.startswith("/ix?doc="):
            href = href[len("/ix?doc="):]
        url = href if href.startswith("http") else "https://www.sec.gov" + href if href.startswith("/") else base_url + href
        docs.append({"description": row[1]["text"], "name": row[2]["text"], "type": row[3]["text"], "url": url})
    return docs


def pick_documents(docs: list[dict], form: str) -> list[dict]:
    """Earnings exhibits (EX-99*) for 8-K/6-K; the main report for periodic forms. The body decides later."""
    if form in ("8-K", "6-K"):
        exhibits = [d for d in docs if d["type"].upper().startswith("EX-99")]
        main = [d for d in docs if d["type"].upper() == form]
        exhibits.sort(key=lambda d: not any(w in (d["description"] + " " + d["name"]).lower() for w in ("earning", "result", "financial", "guidance")))
        return exhibits + (main if form == "6-K" else [])
    return [d for d in docs if d["type"].upper() == form]


# ------------------------------------------------------------------ normalization

BLOCK_TAGS = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr", "title"}
SKIP_TAGS = {"script", "style", "nav", "header", "footer", "noscript"}


class _Normalizer(HTMLParser):
    """Paragraph and table blocks with stable IDs. Table cells keep '(1.2)' negatives and units."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks, self.text, self.skip = [], [], 0
        self.table, self.row, self.cell, self.tables = None, None, None, 0

    def _flush(self):
        text = " ".join("".join(self.text).split())
        if text:
            self.blocks.append({"id": f"p{sum(b['kind'] == 'p' for b in self.blocks) + 1}", "kind": "p", "text": text})
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip += 1
        elif tag == "table":
            self._flush()
            self.tables += 1
            self.table = {"id": f"t{self.tables}", "kind": "table", "rows": []}
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []
        elif tag in BLOCK_TAGS and self.table is None:
            self._flush()

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
        elif tag in ("td", "th") and self.row is not None and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.table is not None and self.row is not None:
            cells = [x for x in self.row]
            if any(cells):
                self.table["rows"].append(merge_cells(cells))
            self.row = None
        elif tag == "table" and self.table is not None:
            if self.table["rows"]:
                self.blocks.append(self.table)
            self.table = None
        elif tag in BLOCK_TAGS and self.table is None:
            self._flush()

    def handle_data(self, data):
        if self.skip:
            return
        if self.cell is not None:
            self.cell.append(data)
        elif self.table is None:
            self.text.append(data)


def merge_cells(cells: list[str]) -> list[str]:
    """EDGAR tables split '$', '(1.2' and ')' or '%' into separate cells; join them back."""
    out: list[str] = []
    for cell in cells:
        if not cell:
            continue
        if out and (cell in (")", "%", ")%") or out[-1] in ("$", "(", "($")):
            out[-1] += cell
        else:
            out.append(cell)
    return out


def normalize_html(raw: bytes) -> list[dict]:
    text = raw.decode("utf-8", errors="replace")
    parser = _Normalizer()
    parser.feed(text)
    parser.close()
    parser._flush()
    return parser.blocks


def block_text(block: dict) -> str:
    return block["text"] if block["kind"] == "p" else " | ".join(" ; ".join(r) for r in block["rows"])


def looks_like_earnings(blocks: list[dict]) -> tuple[bool, str]:
    """Decided from the body, not the exhibit label: EX-99 is not always a results release."""
    body = " ".join(block_text(b) for b in blocks[:400]).lower()
    hits = [w for w in EARNINGS_WORDS if w in body]
    has_table = any(b["kind"] == "table" for b in blocks)
    purpose = any(w in body for w in ("reports", "results", "outlook", "guidance"))
    period = any(w in body for w in ("quarter", "fiscal", "year ended", "year ending"))
    metric = any(w in body for w in ("revenue", "net income", "net sales", "earnings per share", "operating income"))
    if purpose and period and metric and (has_table or re.search(r"[$%]|\d[.,]\d", body)):
        return True, "earnings_terms_and_tables:" + ",".join(hits[:5])
    return False, "not_an_earnings_document:" + ",".join(hits[:5])


# ------------------------------------------------------------------ records

def document_id(cik: str, accession: str, url: str, sha: str) -> str:
    return "DOC-" + hashlib.sha256(f"{cik10(cik)}|{accession}|{urlparse(url).path}|{sha}".encode()).hexdigest()[:16].upper()


def store_document(record: dict) -> bool:
    """Write once. The same ID means the same bytes, so an existing file is kept as is."""
    c.validate_record("company_document", record)
    path = documents_dir() / f"{record['document_id']}.json.gz"
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False)
    tmp.replace(path)
    return True


def load_document(document_id: str) -> dict | None:
    path = documents_dir() / f"{document_id}.json.gz"
    if not path.exists():
        return None
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def build_record(issuer: dict, filing: dict, doc: dict, raw: bytes, final_url: str, truncated: bool,
                 observed_at: str) -> dict:
    sha = hashlib.sha256(raw).hexdigest()
    content_type = "pdf" if raw[:5] == b"%PDF-" or doc["name"].lower().endswith(".pdf") else "html"
    blocks = normalize_html(raw) if content_type == "html" else []
    relevant, reason = looks_like_earnings(blocks) if blocks else (False, "unsupported_content")
    return {
        "document_id": document_id(issuer["cik"], filing["accessionNumber"], doc["url"], sha),
        "issuer": issuer, "url": doc["url"], "final_url": final_url,
        "accession": filing["accessionNumber"], "form": filing["form"], "document_type": doc["type"],
        "title": doc["description"] or doc["name"], "issuer_name": issuer.get("name"),
        "published_at": None,  # the release date inside the document is not parsed; filed_at is the SEC date
        "filed_at": filing["filingDate"], "report_date": filing.get("reportDate") or None,
        "observed_at": observed_at, "raw_sha256": sha, "raw_bytes": len(raw),
        "content_type": content_type, "coverage": "partial" if truncated else ("complete" if blocks else "none"),
        "status": "unsupported_content" if content_type != "html" or not blocks else "parsed",
        "relevance": {"earnings": relevant, "reason": reason,
                      "core_earnings": relevant and any(w in " ".join(block_text(b) for b in blocks).lower() for w in ("net income", "net sales", "earnings per share", "operating income"))},
        "normalization_version": NORMALIZATION_VERSION, "blocks": blocks,
    }
