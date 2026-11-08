"""Download FOMC minutes (HTML and PDF) from federalreserve.gov and keep a manifest.

Where the links live:
- The calendar page lists the most recent years (currently 2021 onward).
- One historical page per year covers everything older (fomchistoricalYYYY.htm).

Each minutes link is read together with its meeting heading (which says whether
the meeting was scheduled, unscheduled or a conference call) and its release date.
Files already on disk are skipped, so the command can be rerun to resume or to
pick up newly released minutes.
"""

import csv
import hashlib
import re
import time
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from fedspeak.config import MANIFEST_CSV, PROJECT_ROOT, RAW_MINUTES_DIR

BASE_URL = "https://www.federalreserve.gov"
CALENDAR_URL = f"{BASE_URL}/monetarypolicy/fomccalendars.htm"
HISTORICAL_URL = f"{BASE_URL}/monetarypolicy/fomchistorical{{year}}.htm"
USER_AGENT = "fedspeak/0.6 (FOMC minutes research tool)"
REQUEST_DELAY = 1.0  # seconds between requests

# Minutes URLs seen on the site:
#   /monetarypolicy/files/fomcminutes20230201.pdf
#   /monetarypolicy/fomcminutes20230201.htm
#   /monetarypolicy/fomc20080625.htm          (some 2008 era pages)
#   /fomc/MINUTES/1993/19930203min.htm        (1993 to 1995)
#   /fomc/minutes/19960130.htm                (1996 to 2007)
MINUTES_URL = re.compile(
    r"(?:fomcminutes|fomc)(?P<d1>\d{8})\.(?P<ext1>htm|pdf)$"
    r"|/minutes/(?:\d{4}/)?(?P<d2>\d{8})(?:min)?\.(?P<ext2>htm)$",
    re.IGNORECASE,
)
RELEASED = re.compile(r"Released\s+([A-Z][a-z]+\.?\s+\d{1,2},\s+\d{4})")
CALENDAR_YEAR = re.compile(r"(\d{4}) FOMC Meetings")


@dataclass
class MinutesRecord:
    meeting_date: str            # YYYY-MM-DD, last day of the meeting (as in the Fed's filenames)
    meeting_label: str           # heading as shown by the Fed, e.g. "March 15 (unscheduled) Meeting - 2020"
    meeting_type: str            # scheduled, unscheduled, conference_call, notation_vote
    release_date: str = ""       # YYYY-MM-DD, when the minutes were published
    html_url: str = ""
    pdf_url: str = ""
    source_page: str = ""
    html_path: str = ""
    pdf_path: str = ""
    html_sha256: str = ""
    pdf_sha256: str = ""
    html_bytes: int = 0
    pdf_bytes: int = 0
    status: str = ""             # ok, or a short description of what failed
    fetched_at: str = ""


MANIFEST_COLUMNS = [f.name for f in fields(MinutesRecord)]


# --- Parsing ---

def classify_meeting(label):
    text = label.lower()
    if "unscheduled" in text:
        return "unscheduled"
    if "conference call" in text:
        return "conference_call"
    if "notation vote" in text:
        return "notation_vote"
    return "scheduled"


def _release_date(text):
    match = RELEASED.search(text)
    return pd.Timestamp(match.group(1).replace(".", "")).strftime("%Y-%m-%d") if match else ""


def _minutes_links(soup, page_url):
    """Yield (anchor, meeting_date, kind, absolute_url) for each minutes link on a page."""
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        # A link with a #fragment points into another meeting's minutes (for example a
        # conference call recorded inside the next meeting's document). Skip it.
        if "#" in href:
            continue
        match = MINUTES_URL.search(href)
        if not match:
            continue
        # Keep only links that sit in a block labelled as minutes, not e.g. a transcript.
        if "minutes" not in a.parent.get_text(" ", strip=True).lower():
            continue
        digits = match.group("d1") or match.group("d2")
        kind = (match.group("ext1") or match.group("ext2")).lower()
        date = f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"
        yield a, date, ("pdf" if kind == "pdf" else "html"), urljoin(page_url, href)


def _merge(records, key, date, label, release, kind, url, page_url):
    """Add one link to the record for its meeting block (key).

    Links are grouped by the meeting block they appear in, not by the date in the URL,
    because the Fed occasionally dates the HTML and PDF of one meeting differently
    (October 2012: PDF 20121023, HTML 20121024). The later date is kept, matching the
    Fed's convention of dating minutes by the last day of the meeting.
    """
    rec = records.get(key)
    if rec is None:
        rec = records[key] = MinutesRecord(
            meeting_date=date, meeting_label=label,
            meeting_type=classify_meeting(label), source_page=page_url,
        )
    rec.meeting_date = max(rec.meeting_date, date)
    if release and not rec.release_date:
        rec.release_date = release
    if kind == "pdf" and not rec.pdf_url:
        rec.pdf_url = url
    if kind == "html" and not rec.html_url:
        rec.html_url = url


def parse_historical_page(html, page_url):
    """Minutes records from a fomchistoricalYYYY.htm page."""
    soup = BeautifulSoup(html, "html.parser")
    records = {}
    for a, date, kind, url in _minutes_links(soup, page_url):
        panel = a.find_parent("div", class_="panel")
        heading = panel.find(["h4", "h5"]) if panel else None
        label = heading.get_text(" ", strip=True) if heading else date
        release = _release_date(a.parent.get_text(" ", strip=True))
        key = id(panel) if panel is not None else date
        _merge(records, key, date, label, release, kind, url, page_url)
    return list(records.values())


def parse_calendar_page(html, page_url):
    """Minutes records from fomccalendars.htm, plus the years the page covers."""
    soup = BeautifulSoup(html, "html.parser")
    years = sorted({int(y) for y in CALENDAR_YEAR.findall(soup.get_text(" "))})
    records = {}
    for a, date, kind, url in _minutes_links(soup, page_url):
        row = a.find_parent("div", class_="fomc-meeting")
        if row is not None:
            month = row.find(class_="fomc-meeting__month")
            days = row.find(class_="fomc-meeting__date")
            # "*" marks meetings with a Summary of Economic Projections; not part of the name.
            parts = [el.get_text(" ", strip=True).replace("*", "") for el in (month, days) if el]
            label = f"{' '.join(parts)} Meeting - {date[:4]}"
            if re.search(r"unscheduled|notation vote", row.get_text(" ").lower()):
                label = f"{' '.join(parts)} (unscheduled) Meeting - {date[:4]}"
        else:
            label = date
        release = _release_date(a.parent.get_text(" ", strip=True))
        key = id(row) if row is not None else date
        _merge(records, key, date, label, release, kind, url, page_url)
    return list(records.values()), years


# --- Network ---

def make_session():
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    retry = Retry(total=4, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _get(session, url):
    time.sleep(REQUEST_DELAY)
    response = session.get(url, timeout=60)
    response.raise_for_status()
    return response


def discover(session, start_year, end_year):
    """All minutes records between start_year and end_year, newest pages first."""
    calendar_records, calendar_years = parse_calendar_page(_get(session, CALENDAR_URL).text, CALENDAR_URL)
    if not calendar_years:
        raise RuntimeError("Could not read the years on the FOMC calendar page; the page layout may have changed.")
    records = [r for r in calendar_records if start_year <= int(r.meeting_date[:4]) <= end_year]

    for year in range(start_year, min(end_year, calendar_years[0] - 1) + 1):
        url = HISTORICAL_URL.format(year=year)
        records += parse_historical_page(_get(session, url).text, url)
        print(f"  {year}: found minutes for {sum(r.meeting_date.startswith(str(year)) for r in records)} meetings")

    return sorted(records, key=lambda r: r.meeting_date)


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _download(session, url, dest, force):
    """Download url to dest unless it is already there. Returns True if a request was made."""
    if dest.exists() and not force:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = _get(session, url).content
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(dest)
    return True


# --- Manifest ---

def read_manifest(path=MANIFEST_CSV):
    if not Path(path).exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {row["meeting_date"]: row for row in csv.DictReader(f)}


def write_manifest(records, path=MANIFEST_CSV):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        for rec in sorted(records, key=lambda r: r.meeting_date):
            writer.writerow(asdict(rec))


# --- Entry point ---

def fetch_minutes(start_year, end_year=None, force=False, raw_dir=RAW_MINUTES_DIR, manifest_path=MANIFEST_CSV):
    end_year = end_year or datetime.now().year
    session = make_session()
    previous = read_manifest(manifest_path)

    print(f"Finding FOMC minutes {start_year} to {end_year} on federalreserve.gov ...")
    records = discover(session, start_year, end_year)
    print(f"Found {len(records)} meetings with minutes.\n")

    # Keep manifest rows outside the requested range untouched.
    kept = {d: MinutesRecord(**{k: row.get(k, "") for k in MANIFEST_COLUMNS})
            for d, row in previous.items() if not start_year <= int(d[:4]) <= end_year}

    downloaded = 0
    for i, rec in enumerate(records, 1):
        problems = []
        for kind, url in (("html", rec.html_url), ("pdf", rec.pdf_url)):
            if not url:
                continue
            ext = "htm" if kind == "html" else "pdf"
            dest = Path(raw_dir) / kind / f"fomcminutes{rec.meeting_date.replace('-', '')}.{ext}"
            try:
                if _download(session, url, dest, force):
                    downloaded += 1
                setattr(rec, f"{kind}_path", dest.resolve().relative_to(PROJECT_ROOT).as_posix()
                        if dest.resolve().is_relative_to(PROJECT_ROOT) else str(dest))
                setattr(rec, f"{kind}_sha256", _sha256(dest))
                setattr(rec, f"{kind}_bytes", dest.stat().st_size)
            except requests.RequestException as exc:
                problems.append(f"{kind}: {exc.__class__.__name__}")
        rec.status = "; ".join(problems) or "ok"
        old = previous.get(rec.meeting_date, {})
        same_files = (old.get("html_sha256", "") == rec.html_sha256 and old.get("pdf_sha256", "") == rec.pdf_sha256)
        rec.fetched_at = old.get("fetched_at") if same_files and old.get("fetched_at") else \
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if i % 10 == 0 or i == len(records):
            write_manifest(list(kept.values()) + records[:i], manifest_path)
            print(f"  {i}/{len(records)} meetings processed, {downloaded} files downloaded")

    failed = [r for r in records if r.status != "ok"]
    print(f"\nDone. {downloaded} new files. Manifest: {manifest_path}")
    if failed:
        print(f"{len(failed)} meetings had download problems:")
        for r in failed:
            print(f"  {r.meeting_date}: {r.status}")
    return records
