# Plan: Verification, Metrics and Dot Plot

Working plan for the next stage of FedSpeak. It covers three areas, in the order they should be built:

1. Data verification: prove the pipeline finds the right words and the right context.
2. Additional metrics: statistics that make keyword series comparable and highlight real shifts.
3. Dot plot quantification: add the FOMC's rate projections and compare them with the language.

Verification comes first because every later metric inherits any error in extraction or matching. `docs/roadmap.md` remains the list of smaller fixes. This document covers the larger pieces of work and the reasoning behind them.

Before section 1, the foundation in section 0 is put in place.

## 0. Foundation: environment, structure, data

Decided 2026-11-08. The original PDFs lived only on an external drive that is no longer available, and the old Jupyter notebooks were not recovered. The rebuild treats federalreserve.gov as the source of truth and makes every local file reproducible.

### 0.1 Environment

- Plain Python in VS Code instead of Anaconda and Jupyter. Notebooks remain an option for exploration only, importing the package.
- `uv` manages a project-local `.venv`, the Python version and a lockfile (`uv.lock`).
- `pyproject.toml` replaces `requirements.txt` as the dependency declaration.

### 0.2 Package layout

`src/fedspeak.py` is split into a package, one module per pipeline stage:

```
src/fedspeak/
  fetch.py      download minutes (PDF and HTML) and SEP pages
  extract.py    PDF and HTML to clean text
  match.py      single keyword matcher producing hit records
  sentiment.py  VADER, later Loughran-McDonald
  metrics.py    EWMA, z-scores, confidence intervals, change points
  dots.py       dot plot parsing and metrics
  dashboard.py  Plotly dashboard
  cli.py        command line entry points (fetch, run, audit)
config.toml     keywords, window, date range, paths
tests/
```

Paths are handled with `pathlib` and read from config, so nothing is tied to one machine or drive letter.

### 0.3 Data storage

```
data/
  raw/              downloaded PDF and HTML minutes, SEP pages   (git-ignored, re-downloadable)
  text/             cleaned text, one file per meeting          (committed, a few MB)
  fedspeak.duckdb   hits, metrics, dot plot data                (git-ignored, rebuilt by pipeline)
```

- The downloader fetches only what is missing, waits between requests and uses a generic client name.
- Cleaned text is committed so the analysis can run without downloading anything.
- DuckDB replaces loose CSV outputs. Tables can be exported to CSV when needed.

### 0.4 Build order

1. Environment: uv, `pyproject.toml`, lockfile.
2. Restructure into the package layout, behavior unchanged.
3. Downloader for minutes in PDF and HTML.
4. Section 1, data verification.

## 1. Data verification

Two layers can fail independently: text extraction (PDF to text) and matching logic (text to hits and windows). Each needs its own checks.

### 1.1 Extraction quality

Risks with pdfplumber:

- Words hyphenated across line breaks ("uncer- tainty") are split and never match.
- Running headers, footers and page numbers are mixed into the text and the context windows.
- Footnotes and the attendance list add text that is not deliberation.

Check: the Fed publishes each set of minutes as HTML as well as PDF. Count keywords in both versions for every meeting and report any meeting where the counts differ. The HTML acts as an independent reference.

Fixes to consider once the differences are known: rejoin line-break hyphenation, strip repeated header and footer lines, or switch the primary source to HTML.

### 1.2 Matching consistency

`count_keywords` and `keyword_sentiment` currently match differently:

- `count_keywords` uses `\b` regex on the raw text, so "uncertainty-driven" counts as a hit.
- `keyword_sentiment` strips non-letters from each token and compares whole tokens, so the same word becomes "uncertaintydriven" and does not match. Multi-word keywords never match.

The frequency panel and the sentiment panel can therefore describe different sets of hits.

Fix: one matching function that returns a list of hit records, used by both frequency and sentiment.

Check: for every meeting and keyword, the number of hits behind the sentiment score equals the raw count. Any difference fails.

### 1.3 Hit records

Replace the truncated snippet strings with a full record per hit:

| Field | Purpose |
|---|---|
| meeting date, filename | where the hit came from |
| keyword | which term matched |
| matched text | the exact text matched, including case and punctuation |
| word index, character offset | position in the document |
| page number | lets a reader find it in the PDF |
| words taken left, words taken right | proves the window size |
| full context text | not truncated |
| sentiment score | stored once, never recomputed |

Write hits to `output/hits.csv`. This closes known issue 8 (scores recomputed on truncated text) and makes every chart value traceable to its source text.

### 1.4 Automated tests

Add `tests/` with pytest and small synthetic texts where the correct answer is known:

- Keyword as the first word, the last word, and within `window` words of either end. Expected: window shortened only on the short side.
- Keyword followed by punctuation, capitalized, hyphenated, plural.
- Keyword split by line-break hyphenation.
- Multi-word keyword ("price stability").
- Two hits close together. Expected: both recorded, overlap reported.
- Zero hits. Expected: sentiment is NaN, not 0.

pytest is a small dependency for tests only.

### 1.5 Human audit

Generate `output/audit.html` showing a random sample of 30 to 50 hits per keyword, each with the keyword highlighted, the window boundaries marked, the page number and the score. Use a fixed random seed so the sample can be regenerated. A reader marks each hit correct or incorrect. This is the only check that the context is meaningful and not just correctly counted.

### 1.6 Window definition

75 words on each side is about 150 words and usually spans several sentences, often including other keywords. Nearby hits produce overlapping windows, so the same text is scored more than once.

Option to evaluate: score the sentence (or sentence plus one on each side) around each hit. Compare the two methods on the audit sample before deciding. Keep the word window as a setting either way.

### Done when

- Extraction counts agree with the HTML minutes, or every remaining difference is explained.
- Frequency and sentiment use the same hits, and the consistency check passes for all meetings.
- The test suite passes.
- One audit pass has been completed and its findings recorded in `docs/context.md`.

## 2. Additional metrics

Constraint: about 80 meetings over ten years. Prefer simple, interpretable statistics over models with many parameters.

| Metric | What it answers | Effort |
|---|---|---|
| EWMA | Smoothed trend that weights recent meetings more than a flat rolling mean. Replaces or sits beside the 4-meeting average. | Low |
| Trailing z-score | How unusual this meeting is compared with the previous two years. Puts keywords on a common scale and flags outlier meetings. | Low |
| Bootstrap confidence intervals on sentiment | How much to trust each sentiment point. An average of 2 hits is mostly noise, an average of 40 is meaningful. | Low |
| Loughran-McDonald net tone | Finance-specific tone: (negative words minus positive words) divided by total words. Standard in research on Fed text and a check on VADER. | Medium |
| Co-occurrence | Which words appear near a keyword, and how that changes ("transitory" giving way to "persistent"). | Medium |
| Change-point detection | Dates where a series shifts level, found objectively with CUSUM or `ruptures`. Directly supports the project aim of locating shifts in language. | Medium |

Notes:

- Minutes are released about three weeks after the meeting. Any comparison with market data must use the release date, not the meeting date. Add a release date column when that work starts.
- `ruptures` is a new dependency. Confirm before adding it.

Suggested order: EWMA, z-score and confidence intervals together, then net tone, then co-occurrence and change points.

## 3. Dot plot quantification

### Background

- The dot plot is part of the Summary of Economic Projections (SEP), published at 4 of the 8 meetings each year (March, June, September, December), from 2012 onward.
- Each dot is one official's projection of the federal funds rate at the end of the current year, the next two or three years, and the longer run.
- Individual dots appear in a table in the HTML version of each SEP. FRED carries the median, range and central tendency series.

### Data

- Scrape the dot table from each SEP into `output/dots.csv` with columns: SEP date, horizon, rate level, number of officials.
- Use the FRED series as a check on the scraped medians.
- The projected years move forward with each SEP. Store both the calendar year and the relative horizon (current year, next year, two years ahead, longer run), and compare across time by relative horizon.

### Metrics per SEP and horizon

- Median and mean projected rate.
- Spread: standard deviation and interquartile range, a measure of disagreement within the committee.
- Revision of the median since the previous SEP: a hawkish or dovish shift.
- Implied rate moves: (median minus current rate) divided by 0.25.
- Longer-run median: the committee's estimate of the neutral rate and its drift.

### Visualization

- A new panel on the shared timeline under the keyword panels: median projection for a chosen horizon with a shaded band for the spread.
- A heatmap of SEP date against rate level, shaded by number of dots, to show clustering and divergence over time.

### Linking dots to language

Questions the combined data can test:

- Does dot spread rise when "uncertainty" frequency rises?
- Do hawkish revisions follow more negative tone around "inflation"?
- Does the longer-run median move with language about the neutral rate?

Align by meeting date: the dots and the minutes describe the same meeting, even though the minutes are published later. With about 55 SEPs since 2012, report correlations with caution and treat them as prompts for reading the text, not as findings.

Dot plot code lives in `dots.py` and its tables in the DuckDB file (see section 0).

## Open decisions

- Primary text source: PDF, HTML, or HTML with PDF as fallback. Depends on 1.1 results.
- Context window: word window or sentence based. Depends on 1.6 comparison.
- EWMA as a replacement for the rolling mean, or shown beside it.
- New dependencies: `ruptures`, a Loughran-McDonald word list. Approved: uv, pytest (tests only), DuckDB.
