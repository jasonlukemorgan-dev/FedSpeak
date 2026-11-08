# FedSpeak

Keyword frequency and sentiment analysis of Federal Reserve FOMC minutes, with an interactive dashboard.

## What it does

Point it at a folder of FOMC minutes PDFs and a list of keywords. For every meeting it calculates:

- How often each keyword appears, per 1,000 words, so meetings of different length are comparable.
- The average sentiment of the text surrounding each keyword, scored from -1 (very negative) to +1 (very positive) using VADER.

It then builds an interactive Plotly dashboard with three panels: frequency over time, sentiment over time, and a scatter of frequency against sentiment.

## Setup

```
pip install -r requirements.txt
```

Edit the configuration block at the top of `src/fedspeak.py`:

```python
PDF_DIR = "D:\\FOMC_Minutes"
KEYWORDS = ["uncertainty", "inflation", "employment", "recession", "tightening"]
CONTEXT_WINDOW = 75
```

PDF filenames must contain the meeting date as `YYYYMMDD` or `YYYY-MM-DD`. Subfolders are searched automatically. Minutes can be downloaded from federalreserve.gov/monetarypolicy/fomc_historical.htm.

## Run

```
python src/fedspeak.py
```

In Jupyter, run the imports and function cells, then call `process_pdfs`, `build_dashboard` and `print_summary` directly. Use `pio.renderers.default = "notebook"` to render charts inline.

Outputs: `fomc_analysis.csv`, `fomc_dashboard.html`, and a plain English summary printed to the console.

## Reading the sentiment score

- Above about +0.05: positive tone around the keyword.
- Between -0.05 and +0.05: neutral.
- Below about -0.05: negative tone.
- Central bank language rarely reaches extremes, so a sustained move below zero matters more than the exact number.

Sentiment describes the tone of the surrounding language, not a forecast. Treat it as a prompt to read the underlying text, which `export_snippets` helps with.

## Documentation

- `CLAUDE.md`: instructions and project state for Claude Code
- `docs/context.md`: background, design decisions, known issues
- `docs/changelog.md`: history of changes
- `docs/roadmap.md`: planned work
