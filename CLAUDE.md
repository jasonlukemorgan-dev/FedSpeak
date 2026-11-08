# FedSpeak

Python tool that scans FOMC minutes (PDFs), measures how often chosen keywords appear, scores the sentiment of the language around them, and plots both over time in an interactive Plotly dashboard.

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
  src/
    fedspeak.py        single-file pipeline (extract, count, score, plot, summarize)
  docs/
    context.md         background, decisions, known issues
    changelog.md       what changed and why
    roadmap.md         planned work in priority order
    plan.md            detailed plan: verification, metrics, dot plot
```

Current focus: section 0 (environment, package layout, downloader) of `docs/plan.md`, then section 1 (data verification). The package restructure in section 0.2 is approved; the layout above will change to match it.

Keep the hierarchy strict: source in `src/`, documentation in `docs/`, nothing loose at the root beyond the files listed above. Generated outputs (`fomc_analysis.csv`, `fomc_dashboard.html`) should go in an `output/` folder if you add output handling.

## How it runs

- Windows machine, VS Code, plain Python managed by uv. Anaconda and Jupyter are no longer used. uv is installed at `~\.local\bin`.
- Input: folder of FOMC minutes PDFs, currently `D:\FOMC_Minutes`, searched recursively with `os.walk`. That folder lived on an external drive that is not available; the downloader in `docs/plan.md` section 0 replaces it.
- Filenames contain the meeting date as `YYYYMMDD` or `YYYY-MM-DD` (for example `fomcminutes20230201.pdf`). The date parser depends on this.
- Install: `uv sync`. Add packages with `uv add <name>` (or `uv add --dev <name>` for test tools), never pip.
- Run: `uv run python src/fedspeak.py`. Tests: `uv run pytest`.
- Outputs: `fomc_analysis.csv`, `fomc_dashboard.html`, console summary.

## Pipeline (all in `src/fedspeak.py`)

1. `process_pdfs` walks the folder, parses dates, calls the steps below per file.
2. `extract_text_from_pdf` uses pdfplumber.
3. `count_keywords` returns frequency per 1,000 words plus raw counts.
4. `keyword_sentiment` takes a 75-word window on each side of every keyword hit, scores it with VADER, and averages per keyword per meeting.
5. `build_dashboard` draws three panels: frequency over time, sentiment over time, frequency vs sentiment scatter.
6. `print_summary` prints a plain English guide to reading the charts plus a snapshot of the latest meeting.
7. `export_snippets` prints the most sentiment-charged snippets for one keyword as a sanity check.

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
6. Keywords are matched as single tokens, so multi-word phrases such as "price stability" will not match in `keyword_sentiment`.
7. Snippets are truncated to 200 characters when stored, so `export_snippets` re-scores truncated text and can disagree with the score used in the charts.
