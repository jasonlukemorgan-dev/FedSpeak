"""Run settings. Edit here until config.toml and command line options replace this."""

from pathlib import Path

# --- Locations ---
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_MINUTES_DIR = DATA_DIR / "raw" / "minutes"   # html/ and pdf/ subfolders, re-downloadable
MANIFEST_CSV = DATA_DIR / "manifest.csv"         # one row per meeting: dates, type, URLs, checksums
TEXT_DIR = DATA_DIR / "text"                     # cleaned minutes text from HTML, one file per meeting (committed)

# --- Fetching ---
FETCH_START_YEAR = 1993   # first year of minutes in their current form

# --- Analysis ---
KEYWORDS = ["uncertainty", "inflation", "employment", "recession", "tightening"]
START_DATE = None         # "YYYY-MM-DD" to limit the analysis, None for no lower limit
END_DATE = None           # "YYYY-MM-DD", None for no upper limit
MATCH_HYPHENATED = False  # count keywords inside hyphenated compounds ("pre-recession", "Inflation-Protected")?
HYPHENATED_EXCEPTIONS = ["maximum-employment"]   # compounds that still count (mandate language)
CONTEXT_WINDOW = 75       # words on each side of keyword to extract for sentiment

# --- Outputs (git-ignored) ---
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_CSV = OUTPUT_DIR / "fomc_analysis.csv"      # one row per meeting
HITS_CSV = OUTPUT_DIR / "hits.csv"                 # one row per keyword hit, with scored context
DASHBOARD_HTML = OUTPUT_DIR / "fomc_dashboard.html"
SNIPPETS_PER_KEYWORD = 3  # most sentiment-charged snippets printed per keyword after a run
