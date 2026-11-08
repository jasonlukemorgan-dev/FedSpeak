"""Run settings. Edit here until config.toml and command line options replace this."""

PDF_DIR = "D:\\FOMC_Minutes"
KEYWORDS = ["uncertainty", "inflation", "employment", "recession", "tightening"]
CONTEXT_WINDOW = 75       # words on each side of keyword to extract for sentiment
OUTPUT_CSV = "fomc_analysis.csv"
DASHBOARD_HTML = "fomc_dashboard.html"
