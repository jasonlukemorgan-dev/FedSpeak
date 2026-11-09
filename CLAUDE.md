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
    verify.py          verification checks (`fedspeak verify sources|context`)
    audit.py           human audit page and label scoring (`fedspeak audit`)
    match.py           find_hits (the one keyword matcher) and frequency
    sentiment.py       sentence splitting and VADER score for each keyword hit
    lm.py              Loughran-McDonald measures per hit and per document (optional dictionary)
    pipeline.py        reads data/text and runs counting and sentiment per meeting
    dashboard.py       Plotly dashboard
    report.py          console summary and snippet inspection
    cli.py             entry point (`fedspeak`, `python -m fedspeak`)
  tests/               pytest suite
  data/
    manifest.csv       one row per meeting: dates, type, URLs, checksums (committed)
    lexicon/           fed_vader_overrides.csv: Fed adjustments to VADER, one reason per word (committed)
      external/        Loughran-McDonald Master Dictionary CSV (git-ignored: third-party terms, never commit)
    text/              cleaned minutes text from HTML, one file per meeting (committed)
    raw/minutes/       html/ and pdf/ downloads (git-ignored, rebuilt by `fedspeak fetch`)
  docs/
    context.md         background, decisions, known issues
    changelog.md       what changed and why
    roadmap.md         planned work in priority order
    plan.md            detailed plan: verification, metrics, dot plot
```

Current focus: section 1 (data verification) of `docs/plan.md`. Section 0 and 1.1 to 1.3 (text source, shared matcher, hit records) are done; 1.4 to 1.6 are done; `CONTEXT_MODE` defaults to "clause": the hit's sentence split at contrast words (decided 2026-11-09, after "sentence" on 2026-11-08; both without audit labels; the audit page is an optional later check). Section 1 remaining: an audit labelling pass when the user wants one. Fed word list, keyword self-exclusion, Loughran-McDonald and clause splitting (option b) are in. Next step undecided; remaining options: (a) a stance model (hawkish/dovish) scoped in the plan, informed by Shah et al. 2023 "Trillion Dollar Words" (RoBERTa-large, CC BY-NC 4.0 data); or (c) section 2 metrics. Ask which before starting. Sentiment is NaN when a keyword has no mentions; code downstream must handle NaN. Add new modules (`metrics.py`, `dots.py`) when their work starts, not as empty files.

Keep the hierarchy strict: source in `src/`, documentation in `docs/`, nothing loose at the root beyond the files listed above. Generated outputs go in `output/` (git-ignored): `fomc_analysis.csv`, `hits.csv`, `fomc_dashboard.html`, `verify/`.

## How it runs

- Windows machine, VS Code, plain Python managed by uv. Anaconda and Jupyter are no longer used. uv is installed at `~\.local\bin`.
- Corpus: `uv run fedspeak fetch` downloads all minutes from 1993 onward (HTML and, from about 2008, PDF) into `data/raw/minutes/` and records each meeting in `data/manifest.csv`, including meeting type (scheduled, unscheduled, conference_call) and release date. It skips files already on disk, so rerunning picks up new releases. federalreserve.gov is the source of truth; the old `D:\FOMC_Minutes` folder is gone.
- Fetch range is not the analysis range. Users choose `KEYWORDS`, `START_DATE` and `END_DATE` in `config.py` at analysis time; nothing should hardcode a period.
- Text source is HTML, not PDF (decided 2026-11-08 after verification 1.1: 2008 to 2024 PDFs are spliced across columns and pre-2020 PDFs include the SEP). `fetch` writes cleaned text for new meetings to `data/text/`; `uv run fedspeak extract --force` rebuilds all of it and must be run after any change to `extract.py`, with the resulting text diff committed. PDFs are kept only for cross-checks (`fedspeak verify`).
- Downloaded and text files are named `fomcminutesYYYYMMDD.{pdf,htm,txt}`, using the last day of the meeting. The date parser depends on this.
- Install: `uv sync`. Add packages with `uv add <name>` (or `uv add --dev <name>` for test tools), never pip.
- Run: `uv run fedspeak fetch`, then `uv run fedspeak` (or `uv run python -m fedspeak`). Tests: `uv run pytest` (no network access in tests).
- Outputs in `output/`: `fomc_analysis.csv` (one row per meeting), `hits.csv` (one row per keyword hit with scored context, the audit trail behind every number), `fomc_dashboard.html`, console summary.

## Pipeline (`src/fedspeak/`)

1. `fetch.fetch_minutes` downloads, then `extract.build_text_corpus` writes `data/text/` using `extract.extract_text_from_html`.
2. `pipeline.process_minutes` reads `data/text/`, applies the date range, calls the steps below per meeting, and adds meeting type and release date from the manifest.
3. `match.find_hits` finds every keyword hit once per meeting (rules in the module docstring; hyphenated compounds are excluded except those in `HYPHENATED_EXCEPTIONS`, a decision recorded in `docs/context.md`). Steps 4 and 5 both use these hits, and the pipeline raises an error if their counts ever differ.
4. `match.count_keywords` returns frequency per 1,000 words plus raw counts.
5. `sentiment.score_hits` scores the clause containing every hit once (the sentence split at contrast words such as "but" and "although"; `CONTEXT_MODE = "sentence"` scores the whole sentence) with VADER adjusted by the Fed word list, ignoring the hit's own keyword (or a 75-word window if `CONTEXT_MODE = "window"`) and returns a full record per hit; `keyword_sentiment` averages those scores per keyword per meeting.
6. `dashboard.build_dashboard` draws three panels: frequency over time, sentiment over time, frequency vs sentiment scatter.
7. `report.print_summary` prints a plain English guide to reading the charts plus a snapshot of the latest meeting.
8. `report.export_snippets` prints the most sentiment-charged snippets for each keyword (stored scores, `SNIPPETS_PER_KEYWORD` each) as a sanity check.

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

1. Recession shading is hardcoded to COVID only.
2. VADER plus the Fed word list (`data/lexicon/fed_vader_overrides.csv`) still cannot read some sentence constructions. Changes to the word list need a reason per row and a before/after note in `docs/context.md`. Loughran-McDonald is used unmodified, free for academic use only; the user's work is non-commercial for now. Recheck its terms if that changes.
3. Sentence scoring has not been confirmed by a human audit yet (`fedspeak audit`).
