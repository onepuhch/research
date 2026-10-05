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
# 8-K items that can carry a business change between results: material agreement, completed acquisition,
# Regulation FD (investor day, guidance update) and other events. Only recent ones are read (O3).
UPDATE_ITEMS = ("1.01", "2.01", "7.01", "8.01")
UPDATE_WORDS = ("guidance", "outlook", "raises", "raised", "increases", "agreement", "contract", "award", "order",
                "backlog", "acquisition", "acquire", "capacity", "pricing", "price increase", "expects")
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


def recent_filings(submissions: dict, today: date, days: int = 120, update_days: int | None = None) -> list[dict]:
    """Recent 8-K/6-K results and 10-Q/10-K/20-F reports, newest first, earnings releases first. With
    update_days, 8-Ks of UPDATE_ITEMS filed within that many days come before them ('update': True):
    what happened after the last results release (an investor day, a guidance raise, a contract)."""
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
        elif (form == "8-K" and update_days is not None and (today - filed).days <= update_days
              and any(i in items for i in UPDATE_ITEMS)):
            chosen.append({**row, "rank": -1, "update": True})
            continue
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


def pick_documents(docs: list[dict], form: str, include_main: bool = False) -> list[dict]:
    """Earnings exhibits (EX-99*) for 8-K/6-K; the main report for periodic forms. The body decides later.
    include_main (business-update 8-Ks): the 8-K's own text comes after its EX-99s, for an agreement
    stated only there. Contract exhibits (EX-10) are never collected."""
    if form in ("8-K", "6-K"):
        exhibits = [d for d in docs if d["type"].upper().startswith("EX-99")]
        main = [d for d in docs if d["type"].upper() == form]
        exhibits.sort(key=lambda d: not any(w in (d["description"] + " " + d["name"]).lower() for w in ("earning", "result", "financial", "guidance")))
        return exhibits + (main if form == "6-K" or include_main or not exhibits else [])  # no EX-99: the 8-K text
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


# ---- whose financial statements a passage sits in (P0): a filer's 8-K can carry an acquired company's
# own statements ('Runway Buyer, LLC CONSOLIDATED STATEMENT OF CASH FLOWS' in Novanta's EX-99.1).
SUBJECT_CHECK_VERSION = "subject-check-v2"
ENTITY_SUFFIX = r"(?:LLC|L\.L\.C\.|Inc\.?|Incorporated|Corp\.?|Corporation|Holdings?|L\.P\.|LP|Ltd\.?|Limited|Co\.|plc|N\.V\.|S\.A\.)"
STATEMENT_HEAD = re.compile(
    r"((?:[A-Z][\w&'.-]*,?\s+){1,6}" + ENTITY_SUFFIX + r")\s+(?:and\s+subsidiaries\s+)?(?:\(?unaudited\)?\s+)?"
    r"(?:condensed\s+)?(?:consolidated\s+)?(?:statements?\s+of\s+(?:cash\s+flows|operations|income|comprehensive|"
    r"financial\s+position|changes|members|stockholders|shareholders)|balance\s+sheets?)", re.I)
GENERIC_NAME = {"inc", "inc.", "incorporated", "corp", "corp.", "corporation", "llc", "l.l.c.", "holdings", "holding",
                "lp", "l.p.", "ltd", "ltd.", "limited", "co.", "plc", "the", "and", "subsidiaries", "group", "company"}


def name_tokens(name: str) -> set[str]:
    return set(entity_name(name))


def entity_name(name: str | None) -> tuple[str, ...]:
    """The distinctive words of a company name in order: case, punctuation, the SEC state suffix
    ('CORP/TX') and legal-form words removed ('Cracker Barrel Old Country Store, Inc' = '... INC.')."""
    text = re.sub(r"/[a-z]{2,4}/?\s*$", "", str(name or "").lower().strip())
    text = re.sub(r"\b(?:l\.l\.c\.|l\.p\.|n\.v\.|s\.a\.|co\.)", " ", text)
    text = re.sub(r"\band subsidiaries\b", " ", text)
    words = re.findall(r"[a-z0-9&]+", text.replace("'", "").replace("’", ""))
    return tuple(w for w in words if w not in GENERIC_NAME and (len(w) > 1 or w.isdigit()))


def same_entity(heading: str, issuer_name: str | None, aliases=()) -> bool | None:
    """True only when the whole distinctive name equals the filer's name or one of its CIK-linked names
    (SEC former names); False when the two names share no word; None (unverified) otherwise: a shared
    word such as 'Northstar' or 'PBF' does not prove one legal entity (subject-check-v2, Q0)."""
    theirs = entity_name(heading)
    names = [entity_name(n) for n in [issuer_name, *(aliases or [])] if n]
    names = [n for n in names if n]
    if not theirs or not names:
        return None
    if any(theirs == n for n in names):
        return True
    if all(not set(theirs) & set(n) for n in names):
        return False
    return None


def statement_scope(text_before: str) -> str | None:
    """The entity named by the last financial-statement heading in the text before a passage."""
    heads = list(STATEMENT_HEAD.finditer(text_before))
    if not heads:
        return None
    name = " ".join(heads[-1].group(1).split())
    # The capture can start inside a previous label or sentence ('EX-99.1. Novanta Inc.'): keep the last
    # sentence piece that still names a company, without leading words that carry digits.
    pieces = [p for p in re.split(r"(?<=\.)\s+(?=[A-Z])", name) if entity_name(p)]
    words = (pieces[-1] if pieces else name).split()
    while len(words) > 1 and re.search(r"\d", words[0]):
        words.pop(0)
    return " ".join(words)


def block_scopes(blocks: list[dict]) -> dict[str, str]:
    """{block id: entity} for blocks under another statement heading, in document order. A heading
    inside a block applies to that block and the ones after it until the next heading."""
    scopes, current = {}, None
    for block in blocks:
        text = block_text(block)
        found = statement_scope(text)
        if found:
            current = found
        if current:
            scopes[block["id"]] = current
    return scopes


UPDATE_CHECK_VERSION = "update-check-v5"
# One sentence must state the business event and carry its number (P1-A): words spread over a document
# no longer add up. A sentence about a dividend, buyback, borrowing, credit agreement, pay or litigation
# is never an update, even if it says 'increases' or 'capacity'.
# v3 (10/5 operation: a Valero director-election release passed on its 'About Valero' capacity sentence):
# only prose before an 'About <company>' heading counts, a capacity must change, an amortization line of
# 'acquired intangibles' is not an acquisition and 'in order to' is not an order.
UPDATE_EVENTS = (
    ("guidance", re.compile(r"\b(?:rais|increas|lift|updat|reaffirm|lower|reduc|cut)\w*\b[^.;]{0,80}\b(?:guidance|outlook)\b"
                            r"|\b(?:guidance|outlook)\b[^.;]{0,60}\b(?:rais|increas|lift|lower|reduc|cut)\w*")),
    ("customer_contract", re.compile(r"\b(?:supply|purchase|customer|long-term|multi-year|master)\s+(?:supply\s+)?"
                                     r"(?:agreement|contract)\b|\b(?:award(?:ed)?|purchase orders?|backlog|design wins?)\b|(?<!\bin )\borders?\b")),
    ("capacity", re.compile(r"\b(?:expand|expansion|increas|add|adding|added|doubl|ramp|new|additional)\w*\b[^.;]{0,60}"
                            r"\bcapacity\b|\bcapacity\s+(?:expansion|increase|addition)s?\b")),
    ("acquisition", re.compile(r"\b(?:acquire|to acquire|acquisition of|has acquired|have acquired|"
                               r"completed (?:its |the )?acquisition|merger agreement)\b")),
    ("pricing", re.compile(r"\bprice increase\b|\bpricing actions?\b")),
)
UPDATE_EXCLUDE = re.compile(r"\b(?:dividend|repurchase|buyback|share repurchase|credit agreement|credit facility|"
                            r"revolving|borrowing|notes due|indenture|loan|compensation|severance|bonus|settlement|"
                            r"litigation|lawsuit|complaint|appoint|resign|director)\w*\b")
UPDATE_NUMBER = re.compile(r"[$€£]\s?\d|\b\d[\d,.]*\s?(?:million|billion|%|percent|units|tons|mw|gw)\b")
# The numbers of an event sentence, for the event signature (P2): '$1.2 billion' and '$1.2billion' are one.
EVENT_NUMBER = re.compile(r"[$€£]\s?\d[\d,.]*(?:\s?(?:million|billion))?|\b\d[\d,.]*\s?(?:million|billion|%|percent|units|tons|mw|gw)\b")
BOILERPLATE_WORDS = ("forward-looking", "could differ", "safe harbor", "risk factors", "undue reliance", "cautionary")
ABOUT_HEADING = re.compile(r"^about\s+[\w&.,'’ -]{1,60}$")


def business_update_judgment(blocks: list[dict], issuer_name: str | None = None) -> tuple[bool, str]:
    """Search eligibility of a recent 8-K text (not proof of a cause): a sentence naming a business event
    (guidance change, customer contract/order/backlog, capacity, acquisition, price increase) with its own
    number, outside excluded topics and outside another company's statements (P0)."""
    found = business_update_event(blocks, issuer_name)
    if found:
        return True, f"{UPDATE_CHECK_VERSION}:{found['event']}:{found['block_id']}"
    return False, f"{UPDATE_CHECK_VERSION}:no_event_sentence"


def business_update_event(blocks: list[dict], issuer_name: str | None = None) -> dict | None:
    """The first event sentence business_update_judgment accepts (search eligibility only)."""
    events = business_events(blocks, issuer_name)
    return events[0] if events else None


# ---- alert eligibility of an event sentence (Q1, update-check-v4). Search eligibility above only says a
# document is worth reading; an alert needs a verified new event: a dated or announced event (not a
# restated result, an unchanged outlook or a recounted past contract) and, for guidance, an explicit
# change of one comparable outlook (old and new values, or a stated change amount).
MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december")
_MONTH = "(" + "|".join(MONTHS) + ")"
DAY_DATE = re.compile(_MONTH + r"\s+(\d{1,2}),?\s+(20\d\d)")
MONTH_DATE = re.compile(r"\b(?:in|during|since|from)\s+(?:early\s+|late\s+|mid-)?" + _MONTH + r",?\s+(20\d\d)")
DATELINE = re.compile(r"^[A-Z][A-Za-z .,'&-]{1,60}?,?\s+" + _MONTH.replace("(", "(", 1) + r"\s+(\d{1,2}),\s+(20\d\d)", re.I)
REAFFIRM = re.compile(r"\b(?:reaffirm\w*|unchanged|maintain\w*|reiterat\w*|continues? to expect|remains?|"
                      r"in line with (?:its|the) (?:prior|previous))\b")
RESULT_COMPARISON = re.compile(r"\b(?:compared (?:with|to)|versus|vs\.|year[- ]over[- ]year|prior[- ]year|"
                               r"from the (?:prior|previous|same) (?:year|period|quarter)|as of|previously announced|"
                               r"previously recorded)\b")
PERIOD_RECOUNT = re.compile(r"\b(?:during|in) the (?:first|second|third|fourth) (?:fiscal )?quarter\b|"
                            r"\b(?:during|in) (?:fiscal|the fiscal year|the year)\b|\b(?:months|quarter|year) ended\b")
ANNOUNCE = re.compile(r"\b(?:today|announc\w*|(?:has|have|was|were) (?:been )?awarded|signed|entered into|"
                      r"receiv(?:ed|es)|secured|won|rais(?:es|ed|ing)|lower(?:s|ed|ing)|increas(?:es|ed|ing)|"
                      r"reduc(?:es|ed|ing)|cuts|will (?:expand|add|acquire)|plans to (?:expand|add|acquire)|"
                      r"agreed to acquire|completed)\b")
GUIDE_METRIC = re.compile(r"\b(net revenues?|revenues?|net sales|sales|adjusted ebitda|ebitda|adjusted (?:diluted )?eps|"
                          r"(?:diluted )?eps|earnings per share|adjusted net income|net income|operating income|"
                          r"free cash flow|capital expenditures?|capex|gross margin|operating margin)\b")
# The outlook's own period (R0): a quarter stays a quarter, and a year elsewhere in the sentence (an event
# date such as 'On September 1, 2026') is never taken for the target period.
QUARTER_NAMES = {"first": 1, "second": 2, "third": 3, "fourth": 4, "q1": 1, "q2": 2, "q3": 3, "q4": 4}
GUIDE_QUARTER = re.compile(r"\b(first|second|third|fourth)[- ]quarter(?:\s+of)?(?:\s+fiscal(?:\s+year)?)?\s+'?(20\d\d)\b|"
                           r"\b(q[1-4])\s+(?:of\s+)?(?:fiscal(?:\s+year)?\s+|fy\s*)?'?(20\d\d|\d\d)\b")
GUIDE_YEAR = re.compile(r"\b(?:fiscal(?: year)?|full[- ]year|fy)\s*'?(20\d\d|\d\d)\b|\b(20\d\d)\s+(?:full[- ]year|fiscal year)\b|"
                        r"\b(20\d\d)\s+(?:[a-z-]+\s+){0,3}(?:guidance|outlook)\b|"
                        r"\bfiscal year end(?:ing|ed)\s+[a-z]+\s+\d{1,2},\s+(20\d\d)\b")
MONEY = r"\$\s?(\d[\d,]*(?:\.\d+)?)\s*(million|billion)?"
MONEY_RANGE = re.compile(MONEY + r"(?:\s*(?:to|-|–|—|and)\s*\$?\s?(\d[\d,]*(?:\.\d+)?)\s*(million|billion)?)?")
CHANGE_FROM_TO = re.compile(r"\bfrom\s+(" + MONEY_RANGE.pattern + r")\s+to\s+(" + MONEY_RANGE.pattern + r")")
CHANGE_TO_FROM = re.compile(r"\bto\s+(" + MONEY_RANGE.pattern + r")\s*,?\s*(?:up |down )?from\s+(?:the prior |its prior |prior )?(?:guidance of\s+)?("
                            + MONEY_RANGE.pattern + r")")
CHANGE_BY = re.compile(r"\bby\s+(?:approximately\s+|about\s+)?(" + MONEY + r")")
COUNTERPARTY = re.compile(r"\b(?:with|from|by|for)\s+((?:[A-Z][\w&.-]*\s){0,4}[A-Z][\w&.-]*(?:,? (?:Inc|LLC|Corp|Ltd)\.?)?)")
NOT_PARTY = {"The", "The Company", "Company", "We", "Our", "It", "This", "Fiscal", "Q1", "Q2", "Q3", "Q4"}


def money_range(text: str) -> list[float] | None:
    """'$1.1 – $1.2 billion' -> [1100.0, 1200.0] in millions (a single value is a one-point range)."""
    m = MONEY_RANGE.search(text)
    if not m:
        return None
    lo, lo_unit, hi, hi_unit = m.group(1), m.group(2), m.group(3), m.group(4)
    unit = hi_unit or lo_unit
    scale = {"billion": 1000.0, "million": 1.0, None: 1.0}  # no unit word: dollars as written (per-share)

    def value(number, own_unit):
        return float(number.replace(",", "")) * scale[own_unit or unit]
    return [value(lo, lo_unit), value(hi, hi_unit)] if hi else [value(lo, lo_unit)] * 2


def guidance_key(sentence: str) -> dict | None:
    """Metric, the outlook's own period (annual FY or one fiscal quarter), currency, unit and GAAP basis;
    None when any of them cannot be read (never a guessed period or currency)."""
    s = sentence.lower()
    metric = GUIDE_METRIC.search(s)
    quarter = GUIDE_QUARTER.search(s)
    if not metric:
        return None
    if quarter:
        name, year = (quarter.group(1), quarter.group(2)) if quarter.group(1) else (quarter.group(3), quarter.group(4))
        year = year if len(year) == 4 else "20" + year
        period = f"FY{year}-Q{QUARTER_NAMES[name]}"
    else:
        found = GUIDE_YEAR.search(s)
        if not found:
            return None
        year = next(g for g in found.groups() if g)
        year = year if len(year) == 4 else "20" + year
        period = f"FY{year}"
    currency = "USD" if "$" in sentence else "EUR" if "€" in sentence else "GBP" if "£" in sentence else None
    if currency is None:
        return None
    name = re.sub(r"\b(?:adjusted|diluted)\s+", "", metric.group(1)).replace("earnings per share", "eps")
    name = {"revenues": "revenue", "net revenue": "revenue", "net revenues": "revenue", "net sales": "sales",
            "capital expenditure": "capex", "capital expenditures": "capex"}.get(name, name)
    gaap = "non-GAAP" if re.search(r"\badjusted\b|\bnon-gaap\b", s) else "unspecified"
    unit = "per_share" if name == "eps" else "pct" if "margin" in name else "usd_millions"
    return {"metric": name, "period": period, "gaap": gaap, "unit": unit, "currency": currency}


def range_direction(old: list[float], new: list[float]) -> str:
    """Both ends move the same way (one may stay) -> up/down; ends moving apart or together -> mixed."""
    signs = {(b > a) - (b < a) for a, b in zip(old, new)}
    if signs == {0}:
        return "unchanged"
    if signs <= {0, 1}:
        return "up"
    if signs <= {0, -1}:
        return "down"
    return "mixed"


def guidance_change(sentence: str, prior: list[dict] | None = None) -> dict:
    """An outlook change stated in one sentence, or against the latest prior outlook of the same key
    (issuer, metric, fiscal period, currency, unit, GAAP basis). Never a midpoint, never a first outlook."""
    key = guidance_key(sentence)
    low = sentence.lower()
    out = {"key": key, "old": None, "new": None, "delta": None, "direction": None, "status": None}
    if key is None:
        return {**out, "status": "no_comparable_key"}
    if REAFFIRM.search(low):
        return {**out, "status": "unchanged"}
    m = CHANGE_FROM_TO.search(sentence)
    if m:
        out["old"], out["new"] = money_range(m.group(1)), money_range(m.group(6))
    else:
        m = CHANGE_TO_FROM.search(sentence)
        if m:
            out["new"], out["old"] = money_range(m.group(1)), money_range(m.group(6))
    if out["old"] and out["new"]:
        out["direction"] = range_direction(out["old"], out["new"])
    else:
        by = CHANGE_BY.search(sentence)
        verb = re.search(r"\b(rais|increas|lift|lower|reduc|cut)\w*", low)
        if by and verb:
            out["delta"] = money_range(by.group(1))[0]
            out["direction"] = "up" if verb.group(1) in ("rais", "increas", "lift") else "down"
            rest = sentence[by.end():]
            out["new"] = money_range(rest) if re.match(r"\s*(?:,\s*)?to\s", rest) else None
        else:
            out["new"] = money_range(sentence)
            same = [p for p in prior or [] if p.get("key") == key and p.get("new")]
            if same and out["new"]:
                out["old"] = same[-1]["new"]
                out["prior_document"] = same[-1].get("document_id")
                # Where the earlier value was stated: document, block, quote, date and subject (R0).
                out["prior"] = {k: same[-1].get(k) for k in ("document_id", "block_id", "sentence", "document_date",
                                                             "filed_at", "subject", "key")}
                out["direction"] = range_direction(out["old"], out["new"])
            elif out["new"] and re.search(r"\b(?:rais|increas|lift|lower|reduc|cut)\w*", low):
                out["status_hint"] = "prior_unverified"  # a change is claimed, but no comparable earlier value
    if out["direction"] in ("up", "down"):
        out["status"] = "changed"
    elif out["direction"] == "mixed":
        out["status"] = "mixed_range"
    elif out["direction"] == "unchanged":
        out["status"] = "unchanged"
    elif out.pop("status_hint", None):
        out["status"] = "prior_unverified"  # a change claim whose earlier value is not a comparable own outlook
    else:
        out["status"] = "no_prior_value"  # a first outlook
    return out


PERIOD_END_BEFORE = re.compile(r"(?:ending|ended|end of|ends|through|thru|until|by)\s*$")


def sentence_date(sentence: str) -> tuple[str | None, str | None]:
    """The first date the sentence names ('In July 2025, ... through July 31, 2026' -> 2025-07). A date that
    ends a period ('fiscal year ending June 25, 2027', 'through December 31') is not an event date."""
    low = sentence.lower()
    found = [(m.start(), f"{m.group(3)}-{MONTHS.index(m.group(1)) + 1:02d}-{int(m.group(2)):02d}", "day")
             for m in DAY_DATE.finditer(low) if not PERIOD_END_BEFORE.search(low[max(0, m.start() - 20):m.start()])]
    found += [(m.start(), f"{m.group(2)}-{MONTHS.index(m.group(1)) + 1:02d}", "month") for m in MONTH_DATE.finditer(low)]
    if not found:
        return None, None
    _, date, precision = min(found)
    return date, precision


def document_date(blocks: list[dict]) -> str | None:
    """The release's own dateline ('SAN ANTONIO, September 18, 2026 –') in its first paragraphs."""
    for block in blocks[:12]:
        if block.get("kind") == "p":
            m = DATELINE.search(block_text(block).strip())
            if m:
                return f"{m.group(3)}-{MONTHS.index(m.group(1).lower()) + 1:02d}-{int(m.group(2)):02d}"
    return None


def event_values(sentence: str, match_at: int) -> list[str]:
    """The amount of the event itself: the money/unit figure nearest after the event words (else before)."""
    found = [(m.start(), re.sub(r"\s+", "", m.group(0)).lower()) for m in EVENT_NUMBER.finditer(sentence)]
    after = [v for at, v in found if at >= match_at]
    return [after[0]] if after else [found[-1][1]] if found else []


def counterparty(sentence: str) -> str | None:
    for m in COUNTERPARTY.finditer(sentence):
        name = m.group(1).strip().rstrip(",")
        if name.endswith(".") and not re.search(r"\b(?:Inc|Corp|Ltd|Co)\.$", name):
            name = name[:-1]  # the sentence's full stop, not an abbreviation
        if name not in NOT_PARTY and not re.match(r"(?:" + "|".join(MONTHS) + r")\b", name.lower()):
            return name
    return None


def alert_judgment(name: str, sentence: str, match_at: int, doc_date: str | None,
                   prior: list[dict] | None = None) -> dict:
    """Content-level alert eligibility of one event sentence; novelty against a baseline is decided by
    the caller with event_date and date_precision."""
    low = sentence.lower()
    out = {"alert_eligible": False, "alert_reason": None, "event_date": None, "date_precision": None,
           "values": event_values(sentence, match_at), "counterparty": None, "guidance": None}
    if name == "guidance":
        change = guidance_change(sentence, prior)
        out["guidance"] = change
        if change["status"] != "changed":
            return {**out, "alert_reason": f"guidance_{change['status']}"}
        out["values"] = [change["key"]["period"], change["key"]["metric"], change["key"]["gaap"],
                         json.dumps(change["new"] or change["delta"])]
        # The change's own date first (a release retelling 'On September 1, 2026, ... raised' is that old
        # change); only an undated change sentence takes the release dateline (R0).
        date, precision = sentence_date(sentence)
        if date is None:
            date, precision = doc_date, "document" if doc_date else None
        out.update(event_date=date, date_precision=precision)
        return {**out, "alert_eligible": bool(date), "alert_reason": None if date else "event_date_unknown"}
    if REAFFIRM.search(low) or RESULT_COMPARISON.search(low):
        return {**out, "alert_reason": "restated_result_or_unchanged"}
    if PERIOD_RECOUNT.search(low):
        return {**out, "alert_reason": "period_recount"}  # a reporting period's figures, not a new event
    date, precision = sentence_date(sentence)
    if date is None:
        if not ANNOUNCE.search(low) or not doc_date:
            return {**out, "alert_reason": "event_date_unknown"}
        date, precision = doc_date, "document"
    out.update(event_date=date, date_precision=precision, counterparty=counterparty(sentence))
    return {**out, "alert_eligible": True}


def business_events(blocks: list[dict], issuer_name: str | None = None, prior: list[dict] | None = None) -> list[dict]:
    """Every event sentence that passes the search rule, with its alert judgment (update-check-v4)."""
    scopes = block_scopes(blocks)
    doc_date = document_date(blocks)
    events = []
    for block in blocks[:400]:
        if block.get("kind") != "p":
            continue  # table rows are figures, not event sentences
        text = block_text(block)
        low = text.lower().strip()
        if ABOUT_HEADING.match(low) and len(low.split()) <= 8:
            break  # the company description and legal notices that follow are not this release's event
        if any(w in low for w in BOILERPLATE_WORDS):
            continue
        heading = scopes.get(block.get("id"))
        if heading and same_entity(heading, issuer_name) is not True:
            continue  # statements of another or an unconfirmed entity are not the filer's update
        for sentence in re.split(r"(?<=[.;])\s+", text):
            s = sentence.lower()
            if UPDATE_EXCLUDE.search(s) or not UPDATE_NUMBER.search(s):
                continue
            for name, pattern in UPDATE_EVENTS:
                match = pattern.search(s)
                if match:
                    numbers = sorted({re.sub(r"\s+", "", n) for n in EVENT_NUMBER.findall(s)})
                    events.append({"event": name, "block_id": block.get("id"), "sentence": sentence.strip()[:600],
                                   "numbers": numbers, "document_date": doc_date,
                                   **alert_judgment(name, sentence.strip(), match.start(), doc_date, prior)})
                    break
    return events


def guidance_statements(blocks: list[dict], issuer_name: str | None = None, aliases=()) -> list[dict]:
    """Outlook values a document states as the filer's own (the 'prior' a later outlook is compared with):
    the same subject check as the new outlook (R0) -- no block under another or an unconfirmed entity's
    statements, nothing after an 'About <company>' heading or in legal notices -- with the block and quote."""
    out = []
    scopes = block_scopes(blocks)
    doc_date = document_date(blocks)
    for block in blocks[:400]:
        if block.get("kind") != "p":
            continue
        low_block = block_text(block).lower().strip()
        if ABOUT_HEADING.match(low_block) and len(low_block.split()) <= 8:
            break
        if any(w in low_block for w in BOILERPLATE_WORDS):
            continue
        heading = scopes.get(block.get("id"))
        if heading and same_entity(heading, issuer_name, aliases) is not True:
            continue
        for sentence in re.split(r"(?<=[.;])\s+", block_text(block)):
            low = sentence.lower()
            if re.search(r"\b(?:guidance|outlook|expects?)\b", low) and "$" in sentence:
                key = guidance_key(sentence)
                change = guidance_change(sentence)
                new = change["new"] or (money_range(sentence) if change["status"] in ("no_prior_value", "prior_unverified", "unchanged") else None)
                if key and new:
                    out.append({"key": key, "new": new, "sentence": sentence.strip()[:300],
                                "block_id": block.get("id"), "document_date": doc_date, "subject": issuer_name})
    return out


def looks_like_business_update(blocks: list[dict], issuer_name: str | None = None) -> tuple[bool, str]:
    """Kept for stored records; the current rule is business_update_judgment."""
    return business_update_judgment(blocks, issuer_name)


def looks_like_earnings(blocks: list[dict]) -> tuple[bool, str]:
    """Decided from the body, not the exhibit label: EX-99 is not always a results release."""
    boilerplate = ("forward-looking", "could differ", "safe harbor", "risk factors", "undue reliance", "cautionary")
    kept = [b for b in blocks[:400] if not any(w in block_text(b).lower() for w in boilerplate)]
    body = " ".join(block_text(b) for b in kept).lower()
    hits = [w for w in EARNINGS_WORDS if w in body]
    has_table = any(b["kind"] == "table" for b in kept)
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
    update, update_reason = (business_update_judgment(blocks, issuer.get("name")) if blocks
                             else (False, "unsupported_content"))
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
                      "core_earnings": relevant and any(w in " ".join(block_text(b) for b in blocks).lower() for w in ("net income", "net sales", "earnings per share", "operating income")),
                      "business_update": update, "update_reason": update_reason},
        "normalization_version": NORMALIZATION_VERSION, "blocks": blocks,
    }
