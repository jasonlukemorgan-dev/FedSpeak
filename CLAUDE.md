# FedSpeak

Python tool that scans FOMC minutes (1993 onward, text taken from the Fed's HTML pages), measures how often chosen keywords appear, scores the sentiment of the language around them, and plots both over time in an interactive Plotly dashboard.

Project aim: read the institutional psychology of the Federal Reserve across time. The tool is meant to surface how the language, tone and preoccupations of policymakers shift before, during and after major economic events, not just what policy decisions were made.

Read `docs/context.md` for the full history, design decisions and known issues before making changes.

## Layout

```
FedSpeak/
  CLAUDE.md
  README.md
  pyproject.toml       dependencies (managed by uv)
  uv.lock              exact resolved versions, committed
  .python-version      pinned Python version (3.12)
  src/fedspeak/
    config.py          run settings (paths, keywords, date range, window, output names)
    fetch.py           downloads minutes (HTML + PDF) from federalreserve.gov, writes the manifest
    extract.py         date from filename, text from PDF and HTML, character normalization
    verify.py          verification checks (`fedspeak verify`: PDF vs HTML comparison)
    match.py           find_hits (the one keyword matcher) and frequency
    sentiment.py       VADER score around each keyword hit
    pipeline.py        reads data/text and runs counting and sentiment per meeting
    dashboard.py       Plotly dashboard
    report.py          console summary and snippet inspection
    cli.py             entry point (`fedspeak`, `python -m fedspeak`)
  tests/               pytest suite
  data/
    manifest.csv       one row per meeting: dates, type, URLs, checksums (committed)
    text/              cleaned minutes text from HTML, one file per meeting (committed)
    raw/minutes/       html/ and pdf/ downloads (git-ignored, rebuilt by `fedspeak fetch`)
  docs/
    context.md         background, decisions, known issues
    changelog.md       what changed and why
    roadmap.md         planned work in priority order
    plan.md            detailed plan: verification, metrics, dot plot
```

Current focus: section 1 (data verification) of `docs/plan.md`. Section 0, 1.1 (text source) and 1.2 (shared matcher) are done; next is 1.3, full hit records written to output. Add new modules (`metrics.py`, `dots.py`) when their work starts, not as empty files.

Keep the hierarchy strict: source in `src/`, documentation in `docs/`, nothing loose at the root beyond the files listed above. Generated outputs (`fomc_analysis.csv`, `fomc_dashboard.html`) should go in an `output/` folder if you add output handling.

## How it runs

- Windows machine, VS Code, plain Python managed by uv. Anaconda and Jupyter are no longer used. uv is installed at `~\.local\bin`.
- Corpus: `uv run fedspeak fetch` downloads all minutes from 1993 onward (HTML and, from about 2008, PDF) into `data/raw/minutes/` and records each meeting in `data/manifest.csv`, including meeting type (scheduled, unscheduled, conference_call) and release date. It skips files already on disk, so rerunning picks up new releases. federalreserve.gov is the source of truth; the old `D:\FOMC_Minutes` folder is gone.
- Fetch range is not the analysis range. Users choose `KEYWORDS`, `START_DATE` and `END_DATE` in `config.py` at analysis time; nothing should hardcode a period.
- Text source is HTML, not PDF (decided 2026-11-08 after verification 1.1: 2008 to 2024 PDFs are spliced across columns and pre-2020 PDFs include the SEP). `fetch` writes cleaned text for new meetings to `data/text/`; `uv run fedspeak extract --force` rebuilds all of it and must be run after any change to `extract.py`, with the resulting text diff committed. PDFs are kept only for cross-checks (`fedspeak verify`).
- Downloaded and text files are named `fomcminutesYYYYMMDD.{pdf,htm,txt}`, using the last day of the meeting. The date parser depends on this.
- Install: `uv sync`. Add packages with `uv add <name>` (or `uv add --dev <name>` for test tools), never pip.
- Run: `uv run fedspeak fetch`, then `uv run fedspeak` (or `uv run python -m fedspeak`). Tests: `uv run pytest` (no network access in tests).
- Outputs: `fomc_analysis.csv`, `fomc_dashboard.html`, console summary.

## Pipeline (`src/fedspeak/`)

1. `fetch.fetch_minutes` downloads, then `extract.build_text_corpus` writes `data/text/` using `extract.extract_text_from_html`.
2. `pipeline.process_minutes` reads `data/text/`, applies the date range, calls the steps below per meeting, and adds meeting type and release date from the manifest.
3. `match.find_hits` finds every keyword hit once per meeting (rules in the module docstring; hyphenated compounds controlled by `MATCH_HYPHENATED`). Steps 4 and 5 both use these hits, and the pipeline raises an error if their counts ever differ.
4. `match.count_keywords` returns frequency per 1,000 words plus raw counts.
5. `sentiment.keyword_sentiment` takes a 75-word window on each side of every hit, scores it with VADER, and averages per keyword per meeting.
6. `dashboard.build_dashboard` draws three panels: frequency over time, sentiment over time, frequency vs sentiment scatter.
7. `report.print_summary` prints a plain English guide to reading the charts plus a snapshot of the latest meeting.
8. `report.export_snippets` prints the most sentiment-charged snippets for one keyword as a sanity check.

## Current dashboard settings (do not revert without asking)

- `vertical_spacing=0.12` and figure `height=1100`. Raised from 0.06 and 950 because year labels collided with subplot titles.
- Year tick labels on panels 1 and 2 only (`tickformat="%Y"`, `dtick="M12"`, `tickangle=-45`).
- COVID recession shading kept, annotation text removed deliberately to reduce clutter.
- Dark theme, 4-meeting rolling average drawn bold over a dotted raw line.

## Conventions

- Keep the keyword list driven by the `KEYWORDS` constant. Nothing downstream should hardcode a keyword.
- Prefer clean, direct code and prose. No em dashes in docs or comments.
- Ask before adding heavy dependencies or restructuring into multiple modules.

## Known issues to fix first

See `docs/context.md` for detail. Short list:

1. `export_snippets` is called with a hardcoded `"uncertainty"`.
2. Recession shading is hardcoded to COVID only.
3. Months with zero keyword mentions get a sentiment of 0, which looks identical to genuinely neutral tone. Should be NaN.
4. The "4-meeting average" label says about one year in the summary text, but the FOMC meets eight times a year, so four meetings is about six months.
5. VADER is a general-purpose lexicon, not a finance lexicon. Fed-specific word overrides are not yet applied.
6. Snippets are truncated to 200 characters when stored, so `export_snippets` re-scores truncated text and can disagree with the score used in the charts.
