# FedSpeak Project Context

## Purpose

The Federal Reserve communicates through careful, institutionally constrained language. A small wording change, such as dropping "transitory" or shifting from "patient" to "data-dependent", can signal a major policy shift, but those signals sit inside long documents most people never read in full. FedSpeak surfaces them systematically.

The deeper aim is to treat monetary policy as a narrative. The Fed sets rates, and it also manages expectations through language. The tool is meant to help answer questions such as:

- Did anxiety about inflation appear in the minutes before rate hikes?
- Did "resilient" appear more often as officials tried to project confidence during stress?
- Did sentiment around "employment" turn negative ahead of recession calls?

Episodes of interest: the 2013 taper tantrum, the 2018 rate path reversal, COVID, and the 2022 inflation surge.

Name: FedSpeak, an existing term for the deliberately vague language of central bankers.

## Current state

Originally run on roughly ten years of minutes (about 2016 to early 2026) stored in `D:\FOMC_Minutes`, an external drive that is no longer available. The 2016 start was chosen for a past research project and is not a project default.

Since version 6 the corpus is downloaded from federalreserve.gov with `fedspeak fetch` (1993 onward) and the analysis runs from VS Code with uv instead of Jupyter. Users choose keywords and date range per run.

Default keywords: uncertainty, inflation, employment, recession, tightening.

## Design decisions and reasoning

- **Frequency per 1,000 words.** Minutes vary in length, so raw counts mislead. Raw counts are still stored with a `_raw` suffix.
- **Word boundary regex.** `\b` matching avoids partial matches. Stemming (for example via nltk Porter) would also catch "uncertainties" and "inflationary" if wanted.
- **Sentiment from a context window.** For every keyword hit, take 75 words either side, score with VADER, and average per meeting. Window size is the main tunable: too narrow loses meaning, too wide dilutes the signal.
- **VADER.** Rule-based, no training or GPU, handles negation and intensifiers. Note it is tuned on social media and news style text, not central bank language, so a domain lexicon is recommended (see roadmap).
- **Rolling average of 4 meetings** overlaid on raw series to show trend without hiding meeting-to-meeting variation.
- **Recursive file search** with `os.walk` because the minutes sit in year or month subfolders.
- **Empty-data guard** so a wrong path exits with a clear message instead of a crash.
- **Plain English summary** printed after the dashboard, with a how-to for the sentiment score and a snapshot of the most recent meeting, chosen over on-chart annotations because the charts were already dense.
- **Annotations removed** from the COVID shading for the same reason.
- **Year labels** added to panels 1 and 2 so the timeframe is readable without hovering, then **spacing increased** (0.06 to 0.12, height 950 to 1100) after labels overlapped subplot titles.

## Dynamic behavior

Changing `KEYWORDS` updates frequency, sentiment and all three chart panels on the next run. Two things are still hardcoded: the keyword passed to `export_snippets`, and the COVID shading dates. There is no UI, so changing keywords means editing the list and rerunning.

## Known issues

1. `export_snippets(all_snippets, "uncertainty", ...)` hardcodes the keyword.
2. Recession shading covers only Feb to Apr 2020. Other episodes (2022 inflation surge, rate hike cycles) are not marked. Consider a configurable list of events.
3. Zero-mention meetings get sentiment 0, indistinguishable from neutral. The flat zero stretches visible on the dotted lines in panel 2 for rare words like "recession" and "tightening" are partly this artifact. Return NaN when there are no mentions and let Plotly leave gaps (or use `connectgaps=False`). The `_sentiment_n` column already holds mention counts and could drive marker size or filtering.
4. The summary text and earlier discussion describe the 4-meeting rolling average as about one year. The FOMC holds eight scheduled meetings a year, so four meetings is about six months. Either change the window to 8 or fix the wording.
5. VADER is not a finance lexicon. Words like "tightening" and "inflation" carry specific meaning in this setting. Suggested overrides: tightening -0.5, accommodative +0.4, headwinds -0.6, resilient +0.5, applied through `analyzer.lexicon.update(...)`.
6. `keyword_sentiment` compares single tokens, so multi-word keywords never match there even though `count_keywords` would match them. Needs phrase-aware matching.
7. Fixed in version 6: unused `import nltk` removed.
8. Stored snippets are cut at 200 characters, so `export_snippets` re-scores shortened text and can show scores that differ from those behind the charts. Store the score alongside the snippet instead of recomputing.
9. `process_pdfs` re-parses every PDF on every run. Parsing ten years takes minutes. Cache extracted text to disk.
10. Dashboard has a long, dense legend and many overlapping lines. A keyword selector or small multiples may read better as keyword count grows.

## Interpreting results with care

VADER measures lexical tone of the surrounding sentence, not the Fed's view or a market signal. A negative score around "inflation" can reflect description of a problem the Fed is addressing rather than concern about its own stance. Use `export_snippets` to read the text behind any pattern before drawing conclusions.

## Deployment idea (not started)

Streamlit app so a user can type keywords into a box and see charts update, hosted free on Streamlit Community Cloud with a public URL. Constraint: the hosted app cannot read local files, and the PDFs are large. Options are to download minutes from federalreserve.gov at runtime, or precompute text and ship a compact dataset. Caching the extracted text (issue 9) is a prerequisite.
