# Roadmap

Ordered by value for effort. Items marked (fix) correct existing behavior.

See `docs/plan.md` for the detailed plan covering data verification, additional metrics and dot plot quantification. Verification work there comes before the items below.

## 1. Correctness fixes

- (fix) Return NaN, not 0, for sentiment when a keyword has no mentions in a meeting. Use `_sentiment_n` to size markers or mask low-count points.
- (fix) Make the rolling window and its label consistent. Eight meetings a year means four meetings is about six months.
- (fix) Remove the hardcoded `"uncertainty"` in the run block. Loop over `KEYWORDS` or accept a parameter.
- (fix) Store each snippet's score with the snippet instead of re-scoring truncated text.
- Support multi-word phrases in `keyword_sentiment`.

## 2. Analytical quality

- Apply a Fed-specific lexicon override on top of VADER (tightening, accommodative, headwinds, resilient, and similar). Consider the Loughran-McDonald finance dictionary as an alternative or comparison.
- Compare VADER against a finance-specific model such as FinBERT on a sample of snippets to check agreement.
- Configurable event shading: list of (label, start, end) for COVID, 2022 inflation surge, hiking cycles, taper tantrum.
- Overlay a market series (fed funds rate, VIX, 10-year yield) to test whether language leads or lags.
- Optional stemming so related word forms are counted together.

## 3. Performance

- Write outputs to an `output/` folder.

## 4. Usability

- Move configuration (path, keywords, window) to command line arguments or a config file instead of editing source.
- Keyword selector in the dashboard, or small multiples, so many keywords stay readable.
- Optional automatic download of minutes from federalreserve.gov.

## 5. Public app

- Streamlit front end: keyword text box, window slider, run button, charts update in place.
- Host on Streamlit Community Cloud. Needs cached or downloadable text because the hosted app cannot see local files.
