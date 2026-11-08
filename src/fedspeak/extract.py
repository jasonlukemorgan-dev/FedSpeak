"""Meeting dates from filenames and text from PDF and HTML minutes."""

import re
from pathlib import Path

import pandas as pd
import pdfplumber
from bs4 import BeautifulSoup

# Main content block of a minutes page, by site era. First match wins.
#   #article     2010s onward
#   #leftText    around 2008 to 2009
#   #content     1993 to 1995
# Pages from 1996 to 2007 have no content wrapper, so the whole document is used
# (minus <head>). Selecting <body> instead loses text on pages whose malformed HTML
# makes the parser close <body> early (1996-11-13 lost 90 percent of its words).
HTML_CONTENT_SELECTORS = ["#article", "#leftText", "#content"]

# Link text that appears inside the minutes: "Return to top" after sections (1990s pages
# repeat it after every section) and "Return to text" after each footnote.
HTML_LINK_TEXT = re.compile(r"\[?\s*(?:Return|Back)\s+to\s+(?:top|text)\.?\s*\]?", re.IGNORECASE)

# Site footer that follows the minutes. Only cut when it starts near the end of the page.
HTML_FOOTER = re.compile(r"\s(?:(?:FOMC )?Home \| (?:FOMC|Monetary Policy)\b|Last update:)", re.IGNORECASE)
HTML_FOOTER_MAX_WORDS = 80


def normalize_text(text):
    """Character fixes applied to every extracted text, PDF or HTML.

    - Soft hyphens (U+00AD) and zero-width joiners (U+200D) are invisible but split
      words for matching ("al\\u00adthough"). Found in 2016 to 2024 HTML minutes.
    - Non-breaking hyphens (U+2011, "longer\\u2011run") become ordinary hyphens.
    """
    return text.replace("­", "").replace("‍", "").replace("‑", "-")


def extract_date_from_filename(filename):
    patterns = [
        r'(\d{4})(\d{2})(\d{2})',
        r'(\d{4})-(\d{2})-(\d{2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            y, m, d = match.groups()
            return pd.Timestamp(f"{y}-{m}-{d}")
    return None


def extract_text_from_pdf(filepath):
    text = ""
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + " "
    return normalize_text(text)


def text_filename(meeting_date):
    """data/text file name for a meeting date ("YYYY-MM-DD")."""
    return f"fomcminutes{meeting_date.replace('-', '')}.txt"


def build_text_corpus(manifest_path, text_dir, dates=None, force=False):
    """Write cleaned HTML text for each meeting in the manifest to text_dir.

    The HTML version is the text source for analysis: it exists for every meeting
    since 1993, reads in the right order, and excludes the Summary of Economic
    Projections consistently (see docs/context.md, Verification findings).
    Existing files are kept unless force is set; rerun with force after changing
    the extractor. `dates` limits the build to those meeting dates.
    Returns the number of files written.
    """
    from fedspeak.config import PROJECT_ROOT

    manifest = pd.read_csv(manifest_path, dtype=str).fillna("")
    text_dir = Path(text_dir)
    text_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for rec in manifest.itertuples():
        if dates is not None and rec.meeting_date not in dates:
            continue
        if not rec.html_path:
            print(f"  {rec.meeting_date}: no HTML version, skipped")
            continue
        dest = text_dir / text_filename(rec.meeting_date)
        if dest.exists() and not force:
            continue
        text = extract_text_from_html(PROJECT_ROOT / rec.html_path)
        dest.write_text(text + "\n", encoding="utf-8", newline="\n")
        written += 1
    return written


def extract_text_from_html(filepath):
    """Minutes text from a federalreserve.gov HTML page, without site navigation.

    Encoding is decided here rather than guessed: many older pages declare no charset,
    and automatic detection can pick an unrelated encoding and garble the text. UTF-8
    is tried first (strict, so it rarely matches by accident), then Windows-1252, the
    usual encoding of older English web pages.
    """
    raw = Path(filepath).read_bytes()
    try:
        markup = raw.decode("utf-8")
    except UnicodeDecodeError:
        markup = raw.decode("cp1252", errors="replace")
    soup = BeautifulSoup(markup, "html.parser")
    for tag in soup(["head", "title", "script", "style", "noscript"]):
        tag.decompose()
    container = next((el for sel in HTML_CONTENT_SELECTORS if (el := soup.select_one(sel))), soup)
    text = normalize_text(container.get_text(" "))
    # Some 1999 to 2007 pages contain U+FFFD where the Fed's own file lost a character,
    # usually an apostrophe ("System�s"), sometimes a dash or fraction. Restore the
    # apostrophe between letters; otherwise use a space so words are not fused together.
    text = re.sub(r"(?<=[A-Za-z])�(?=[A-Za-z])", "'", text).replace("�", " ")
    text = HTML_LINK_TEXT.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for match in HTML_FOOTER.finditer(text):
        if len(text[match.start():].split()) <= HTML_FOOTER_MAX_WORDS:
            return text[:match.start()].rstrip()
    return text
