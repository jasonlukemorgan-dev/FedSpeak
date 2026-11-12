# FedSpeak

Keyword frequency and sentiment analysis of Federal Reserve FOMC minutes, with an interactive dashboard.

## What it does

Point it at a folder of FOMC minutes PDFs and a list of keywords. For every meeting it calculates:

- How often each keyword appears, per 1,000 words, so meetings of different length are comparable.
- The average sentiment of the sentence containing each keyword, scored from -1 (very negative) to +1 (very positive) using VADER.

It then builds an interactive Plotly dashboard with three panels: frequency over time, sentiment over time, and a scatter of frequency against sentiment. With the optional stance model, a fourth panel shows a whole-meeting hawkish/dovish index.

## Setup

FedSpeak uses [uv](https://docs.astral.sh/uv/) to manage Python and dependencies. Install uv, then from the project folder:

```
uv sync
```

This creates a local `.venv` with the pinned Python version (3.12) and the exact package versions in `uv.lock`.

Download the minutes:

```
uv run fedspeak fetch
```

This downloads every set of FOMC minutes from 1993 onward from federalreserve.gov (HTML, plus PDF where the Fed publishes one) into `data/raw/minutes/`, records each meeting in `data/manifest.csv` with its meeting type, release date, source URLs and file checksums, and writes the cleaned text of each meeting to `data/text/`. Files already downloaded are skipped, so rerun it after each FOMC release to add the new minutes. Use `--start-year` and `--end-year` to limit the range.

The cleaned text is already in the repository, so the analysis runs without downloading anything. Text comes from the HTML version of the minutes: the PDFs for 2008 to 2024 use a two-column layout that PDF extraction splices together, and PDFs before 2020 include the Summary of Economic Projections. Details in `docs/context.md`.

Optional: for Loughran-McDonald finance-dictionary measures, download the Master Dictionary CSV from https://sraf.nd.edu/loughranmcdonald-master-dictionary/ and save it as `data/lexicon/external/Loughran-McDonald_MasterDictionary_1993-2025.csv`. It is free for academic research; commercial use needs a license from its authors. It is not included in this repository. Without it, the LM columns are left out.

Optional: hawkish/dovish stance from FOMC-RoBERTa (see [Stance model](#stance-model) below).

Choose what to analyze in `src/fedspeak/config.py`:

```python
KEYWORDS = ["uncertainty", "inflation", "employment", "recession", "tightening"]
START_DATE = None   # e.g. "2016-01-01"
END_DATE = None
CONTEXT_MODE = "clause"     # the keyword's clause; or "sentence", or "window" for CONTEXT_WINDOW words on each side
```

## Run

```
uv run fedspeak
```

Run tests with `uv run pytest`. Other commands:

- `uv run fedspeak extract --force` rebuilds `data/text/` from the downloaded HTML.
- `uv run fedspeak verify sources` compares PDF and HTML text; `uv run fedspeak verify context` compares word-window and sentence scoring.
- `uv run fedspeak audit` builds `output/audit/audit.html` for hand-labelling a random sample of hits; `uv run fedspeak audit --labels <csv>` scores the methods against those labels.

`output/hits.csv` lists every keyword hit with the exact text that was scored, so any number on the dashboard can be traced to its source sentences.

Outputs: `fomc_analysis.csv`, `fomc_dashboard.html`, and a plain English summary printed to the console.

## Reading the sentiment score

- Above about +0.05: positive tone around the keyword.
- Between -0.05 and +0.05: neutral.
- Below about -0.05: negative tone.
- Central bank language rarely reaches extremes, so a sustained move below zero matters more than the exact number.

Sentiment describes the tone of the surrounding language, not a forecast. Treat it as a prompt to read the underlying text, which `export_snippets` helps with.

## Stance model

Optional, and off by default. A fine-tuned language model reads each keyword's clause as hawkish, dovish or neutral, which tone dictionaries cannot do. Each hit gets the three probabilities and a stance score (hawkish minus dovish, -1 to +1). Each meeting gets the average per keyword and a whole-meeting index: (hawkish sentences - dovish sentences) / all sentences.

Setup:

1. Accept the model's terms at https://huggingface.co/gtfintechlab/FOMC-RoBERTa with your own Hugging Face account. Access is reviewed by the authors.
2. Log in once: `uvx --from huggingface_hub hf auth login`, with a read token.
3. Install torch and transformers: `uv sync --extra stance` (about 2.5 GB; CUDA build on Windows and Linux).
4. In `config.py`, set `STANCE_MODEL = "gtfintechlab/FOMC-RoBERTa"` and pin `STANCE_MODEL_REVISION` to a commit hash. Set `DASHBOARD_SENTIMENT = "stance"` to plot it.
5. Run with `uv run --extra stance fedspeak`. The first run downloads the 1.4 GB model; results are cached in `output/stance_cache.sqlite`, so reruns only score new text. Scoring every sentence takes minutes on a GPU and an hour or more on CPU; set `STANCE_DOCUMENT_INDEX = False` to score keyword clauses only.

### Attribution

The stance model is FOMC-RoBERTa by the Financial Services Innovation Lab, Georgia Tech, from Agam Shah, Suvan Paturi and Sudheer Chava, "Trillion Dollar Words: A New Financial Dataset, Task & Market Analysis", ACL 2023 (https://aclanthology.org/2023.acl-long.368). The model, its data and code are licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/): non-commercial use only, with attribution. The model is not included in this repository.

## Documentation

- `CLAUDE.md`: instructions and project state for Claude Code
- `docs/context.md`: background, design decisions, known issues
- `docs/changelog.md`: history of changes
- `docs/roadmap.md`: planned work
- `docs/plan.md`: detailed plan for verification, additional metrics and dot plot analysis
