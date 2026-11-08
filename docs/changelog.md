# Changelog

Newest first.

## Version 6 (in progress): Foundation rebuild

- Environment moved from Anaconda and Jupyter to uv. `pyproject.toml`, `uv.lock` and `.python-version` (3.12) replace `requirements.txt`.
- Dependencies now resolve to pandas 3.1 and plotly 7.1. A smoke test on synthetic text confirmed counting, sentiment, dashboard, summary and date parsing run unchanged with no warnings.
- Removed unused `import nltk` (known issue 7). nltk was never in the requirements, so the import would fail in a clean environment.
- pytest added as a development dependency.
- `src/fedspeak.py` split into the `src/fedspeak/` package: `config`, `extract`, `match`, `sentiment`, `pipeline`, `dashboard`, `report`, `cli`. Code moved without changes to behavior. The only edit is that the dashboard filename now comes from `config.DASHBOARD_HTML` instead of being written inline.
- Equivalence check: the old script and the new package were run on the same synthetic meetings (three dated, one undated, nested subfolders). The data table, every snippet, the full console output, date parsing and the dashboard file size were identical.
- New entry points: `uv run fedspeak` and `python -m fedspeak`.
- First tests in `tests/test_basics.py`: date parsing, frequency per 1,000 words, case and partial-word matching, empty text.
- Downloader: `fedspeak fetch` collects minutes from 1993 onward. Links come from the FOMC calendar page (recent years) and the per-year historical pages (older years), read together with each meeting's heading and release date. Unscheduled meetings are included and tagged by `meeting_type`. Requests are spaced one second apart with retries, and files already on disk are skipped.
- `data/manifest.csv` records each meeting's date, label, type, release date, source URLs, local paths, SHA-256 checksums, sizes and fetch time.
- `PDF_DIR` now points at the downloaded PDFs. `START_DATE` and `END_DATE` in config limit the analysis to a date range (default: everything).
- Command line: `fedspeak run` (default) and `fedspeak fetch [--start-year] [--end-year] [--force]`.
- New dependencies: requests, beautifulsoup4. Parser tests in `tests/test_fetch.py` use fixtures copied from the real page layouts.
- HTML text extraction (`extract.extract_text_from_html`) for all site eras, with fixed encoding handling and shared character normalization (`normalize_text`) applied to PDF and HTML text.
- `fedspeak verify` compares PDF and HTML text for the 152 meetings with both. It found that 2008 to 2024 PDFs are spliced across columns and that pre-2020 PDFs include the Summary of Economic Projections. Full findings in `docs/context.md`.
- Text source switched from PDF to HTML for the whole pipeline. `data/text/` holds cleaned text for all 270 meetings (13 MB, committed), written by `fetch` for new meetings and rebuilt by `fedspeak extract --force`. `process_pdfs` is replaced by `process_minutes`, which reads `data/text/` and adds meeting type and release date to each row. The analysis now covers 1993 to 2026 instead of mid-2007 onward, and a full run takes about 17 seconds instead of several minutes.
- One keyword matcher, `match.find_hits`, now feeds both frequency and sentiment (plan 1.2). It returns each hit's position and word span, matches multi-word keywords, treats dashes as word separators, and handles hyphenated compounds per the new `MATCH_HYPHENATED` setting. Sentiment previously missed up to 18 percent of hits for some keywords; now every meeting's sentiment and frequency counts agree, enforced by a check in the pipeline. Tests in `tests/test_match.py`, including exact context-window boundaries.
- Keywords inside hyphenated compounds are no longer counted ("Inflation-Protected", "employment-to-population", "pre-recession"), except those in `HYPHENATED_EXCEPTIONS` ("maximum-employment"). Frequency falls 1.3 percent for inflation, 3.7 percent for employment and 17.2 percent for recession across the corpus. Reasoning in `docs/context.md`.
- Hit records (plan 1.3): `output/hits.csv` has one row per keyword hit with its position, words taken each side, overlap with the previous window, full context and stored score. Snippets are no longer truncated or re-scored, and snippets print for every keyword instead of a hardcoded "uncertainty". Outputs moved to `output/`. The records showed that 84 percent of windows overlap the previous one and that the window picks up tone from unrelated sentences; see `docs/context.md`.
- Sentiment is NaN, not 0, when a keyword is not mentioned (plan 1.4). The dashboard shows gaps and the summary says "not mentioned". Removed fake neutral scores from 191 of 270 meetings for "recession". Summary text now says the 4-meeting average is about six months, not one year.
- First run on real minutes (2020) worked end to end. It surfaced values the verification work must explain, for example `tightening` sentiment above +0.9 from single mentions and `uncertainty` reading +0.71 in December 2020.

## Version 5: Layout spacing

- `make_subplots` `vertical_spacing` raised from 0.06 to 0.12.
- Figure `height` raised from 950 to 1100.
- Reason: year labels added in version 4 overlapped the titles of the panels below. A further step to spacing 0.14 and height 1200 is available if still tight.

## Version 4: Year labels and plain English summary

- Year tick labels on panels 1 and 2 (`tickformat="%Y"`, `dtick="M12"`, `tickangle=-45`).
- Removed `annotation_text` and `annotation_position` from the COVID shading to reduce clutter. Shading stays.
- Added `print_summary(df, keywords)`: a guide to reading each panel, a sentiment score scale, and a snapshot of the latest meeting with a tone label per keyword.
- `print_summary` is called after `build_dashboard` in the run block.
- Removed decorative characters from the summary text. Removed the claim that bottom-right scatter points are historically a leading signal, since the project has not tested that.

## Version 3: Robustness updates

- `os.walk` replaces `os.listdir` so PDFs in year or month subfolders are found.
- Guard for an empty result: prints a message and exits instead of crashing.
- `PDF_DIR` set to `D:\FOMC_Minutes`.
- Run block wrapped in `if __name__ == "__main__"`.

## Version 2: Sentiment and interactivity

- VADER sentiment scored on a 75-word window around each keyword hit.
- Plotly dashboard replaces the static matplotlib chart: frequency panel, sentiment panel, frequency vs sentiment scatter.
- 4-meeting rolling averages.
- `export_snippets` helper for sanity-checking sentiment.
- Hover templates, legend grouping so one click toggles all of a keyword's traces, dark theme, COVID shading.

## Version 1: Initial script

- pdfplumber text extraction.
- Regex keyword counts normalized per 1,000 words.
- Date parsing from filenames (`YYYYMMDD` or `YYYY-MM-DD`).
- Matplotlib line chart.

## Setup notes from Jupyter and Anaconda use

- `pdfplumber`, `vaderSentiment` and `plotly` are not in base Anaconda. If `ModuleNotFoundError` persists after install, use the kernel's own interpreter:
  ```python
  import sys
  !{sys.executable} -m pip install pdfplumber vaderSentiment plotly
  ```
  then restart the kernel.
- For inline charts in a notebook: `import plotly.io as pio` and `pio.renderers.default = "notebook"`.
