"""Run settings. Edit here until config.toml and command line options replace this."""

from pathlib import Path

# --- Locations ---
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_MINUTES_DIR = DATA_DIR / "raw" / "minutes"   # html/ and pdf/ subfolders, re-downloadable
MANIFEST_CSV = DATA_DIR / "manifest.csv"         # one row per meeting: dates, type, URLs, checksums

# --- Fetching ---
FETCH_START_YEAR = 1993   # first year of minutes in their current form

# --- Analysis ---
PDF_DIR = RAW_MINUTES_DIR / "pdf"
KEYWORDS = ["uncertainty", "inflation", "employment", "recession", "tightening"]
START_DATE = None         # "YYYY-MM-DD" to limit the analysis, None for no lower limit
END_DATE = None           # "YYYY-MM-DD", None for no upper limit
CONTEXT_WINDOW = 75       # words on each side of keyword to extract for sentiment
OUTPUT_CSV = "fomc_analysis.csv"
DASHBOARD_HTML = "fomc_dashboard.html"
