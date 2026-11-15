# Review checklist

Failure modes specific to this repo. Code review (human or Claude) checks every change against this list, then looks for ordinary bugs. Report only real problems in the changed code; do not repeat a finding already raised on an earlier pass.

## Public repo

- **Nothing third-party or secret is committed:** no Loughran-McDonald files (`data/lexicon/external/` stays git-ignored), no model weights or stance cache, no Hugging Face tokens, no raw PDFs or HTML downloads.
- **No private plans in docs.** Long-term goals for the project stay out of the repo.
- **Licences are credited.** Code that uses FOMC-RoBERTa (CC BY-NC 4.0) or Loughran-McDonald keeps the attribution in README and `docs/context.md`.

## Correctness of the numbers

- **One matcher.** Every count and score comes from `match.find_hits`. A second keyword search anywhere else is a bug; the pipeline's check that counts and scored hits agree must stay.
- **Nothing hardcodes a keyword or a period.** Keywords come from `KEYWORDS`; dates from `START_DATE` and `END_DATE`.
- **NaN means "no mentions".** Code downstream of sentiment, LM, or stance handles NaN (no `fillna(0)`, no averages that drop meetings silently).
- **Extraction changes** to `extract.py` come with `uv run fedspeak extract --force` and the resulting `data/text/` diff in the same commit.
- **Fed word list edits** (`data/lexicon/fed_vader_overrides.csv`) have a reason in every row and a before/after note in `docs/context.md`.
- **Scoring choices** (context mode, thresholds, weighting, word lists) are stated with their alternatives in `docs/context.md`, not changed silently.
- **Stance runs are reproducible:** `STANCE_MODEL_REVISION` is pinned, and the cache key includes model, revision, and text.

## Tests and tooling

- **Tests make no network calls** and do not need torch or model weights (the real-model smoke test skips when they are missing).
- **New behavior gets a test** in `tests/`.
- **Packages via uv** (`uv add`), never pip. Heavy dependencies need the user's approval first.
- **Layout stays strict:** source in `src/fedspeak/`, docs in `docs/`, generated files in `output/`, nothing new at the root.

## Dashboard

- The settings listed under "Current dashboard settings" in `CLAUDE.md` are not reverted without asking.

## Prose

- Docs and comments: clean, direct, no em dashes.
