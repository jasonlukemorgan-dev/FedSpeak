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
