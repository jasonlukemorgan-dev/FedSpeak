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

1. Fixed in version 6: snippets are printed for every keyword in `KEYWORDS`.
2. Recession shading covers only Feb to Apr 2020. Other episodes (2022 inflation surge, rate hike cycles) are not marked. Consider a configurable list of events.
3. Fixed in version 6: sentiment is NaN when a keyword has no mentions, and the dashboard leaves gaps. Across 270 meetings this removed fake 0.000 "neutral" scores from 191 meetings for "recession", 59 for "tightening" and 13 for "uncertainty". The `_sentiment_n` column could still drive marker size or filtering.
4. Fixed in version 6: the summary now describes the 4-meeting average as about six months.
5. VADER is not a finance lexicon. Words like "tightening" and "inflation" carry specific meaning in this setting. Suggested overrides: tightening -0.5, accommodative +0.4, headwinds -0.6, resilient +0.5, applied through `analyzer.lexicon.update(...)`.
6. Fixed in version 6: `match.find_hits` handles multi-word keywords, and frequency and sentiment share it.
7. Fixed in version 6: unused `import nltk` removed.
8. Fixed in version 6: each hit stores its full context and score; `export_snippets` uses the stored score.
9. Fixed in version 6: text is extracted once into `data/text/` and the analysis reads those files.
10. Dashboard has a long, dense legend and many overlapping lines. A keyword selector or small multiples may read better as keyword count grows.

## Verification findings

### 1.1 Text extraction, PDF vs HTML (2026-11-08)

Run with `fedspeak verify` on the 152 meetings that have both versions (mid-2007 onward). Results in `output/verify/pdf_vs_html.csv`.

**PDF extraction is unreliable for 2008 to 2024.**
- Those PDFs use a two-column layout. pdfplumber reads across both columns line by line, splicing unrelated passages together. Example from June 2019: "the eligibility of counterparties in weak fi- could be an important factor determining whether a fa- nancial condition". Page headers come out garbled ("M__in_u_t_es_ _o_f") and attendance-list names land mid-sentence.
- Median 130 to 240 words per meeting are split across line breaks ("tight- ening"), so keywords inside them are missed.
- On average 3 of the 5 default keywords get a different count from the HTML in each meeting.
- Context windows built from this text mix two unrelated passages, so sentiment scores for these years in the original version of the tool are not trustworthy.

**PDFs before mid-2020 include the Summary of Economic Projections; the HTML does not.** The PDF for an SEP meeting has 5,000 to 7,000 extra words of projections narrative and tables. This accounts for most of the "uncertainty" gap (2,216 mentions in PDFs vs 890 in HTML; 1,398 of the difference is in those meetings). From late 2020 neither version includes it. Mixing the two would make frequency jump up and down with the SEP schedule for reasons unrelated to the minutes themselves.

**HTML extraction agrees with clean PDFs.** In 2025 and 2026 the Fed's PDFs are single-column. There, PDF and HTML keyword counts match exactly in every meeting for all five keywords, an independent check that the HTML extractor captures the minutes text correctly.

**HTML issues found and fixed** (each has a test in `tests/test_extract_html.py`):
- Content block differs by site era (`#article`, `#leftText`, `#content`, or the whole page for 1996 to 2007).
- 1990s pages repeat "[Return to top]" after every section; cutting at the first one lost up to 90 percent of a meeting (1996-11-13 kept 539 of 4,800 words).
- Site footers vary ("FOMC Home | Monetary policy", "Last update:") and are cut only at the end of the page.
- Many older pages declare no character encoding and automatic detection can choose the wrong one. Decoding is now fixed: UTF-8, else Windows-1252 (12 pages).
- 26 pages from 1999 to 2007 contain broken characters (U+FFFD) in the Fed's own files, usually lost apostrophes. Restored as apostrophes between letters, otherwise spaces.
- Soft hyphens inside words in 2016 to 2024 pages ("al­though") split words for matching. Removed for all text, along with zero-width joiners; non-breaking hyphens become ordinary hyphens.

### 1.2 Shared matcher (2026-11-08)

Before: `count_keywords` used `\b` regex on the whole text, while `keyword_sentiment` stripped non-letters from each token and compared it to the keyword. Sentiment therefore missed dash-joined forms ("inflation—as"), possessives ("inflation's"), hyphenated compounds and every multi-word keyword. Across all 270 meetings, sentiment was built on fewer hits than frequency in 175 meetings for "inflation" and 98 for "employment"; 18 percent of "recession" mentions never reached a sentiment score.

After: `match.find_hits` is the only matcher. Frequency counts are unchanged; sentiment hit counts now equal them in every meeting, and the pipeline raises an error if they ever differ. Mean change in per-meeting sentiment was small (0.001 to 0.025 by keyword), but individual meetings moved by up to 0.77 ("recession", a meeting whose only mentions were "pre-recession").

Decision, hyphenated compounds (2026-11-08): keywords inside hyphenated compounds are not counted, because most compounds name a security, a statistic or a time period rather than discuss the topic, and counting them inflates hits. Most common in the corpus: "Treasury Inflation-Protected Securities" (102, a bond name), "employment-to-population ratio" (100, a statistic), "inflation-indexed" (38), "pre-recession" (23, a time reference). Exception: "maximum-employment" (82) still counts, as mandate language. Settings: `MATCH_HYPHENATED = False`, `HYPHENATED_EXCEPTIONS = ["maximum-employment"]`. Double hyphens ("inflation--which") are typed dashes, not compounds, and still count.

Effect across 270 meetings: inflation 12,474 to 12,312 hits (minus 1.3 percent), employment 2,830 to 2,724 (minus 3.7 percent), recession 151 to 125 (minus 17.2 percent); uncertainty and tightening unchanged. This is a deliberate change in what the frequency series measures, so results from before this decision are not directly comparable.

### 1.3 Hit records (2026-11-08)

`output/hits.csv` has one row per keyword hit (17,153 across 270 meetings with the default keywords): meeting, keyword, exact matched text, character offsets, word span, words actually taken left and right, overlap with the previous hit's window, the full scored context and its score. Per-meeting counts and average sentiment in `fomc_analysis.csv` are reproduced exactly from these rows (tested).

What the records show about the 75-word window:
- Overlap is the norm. 84 percent of hits share words with the previous hit's window, median 127 of 151 words. Dense passages are scored many times over, so they dominate a meeting's average.
- The window picks up tone from neighbouring sentences. December 2020 "uncertainty" averaged +0.69. Four of its seven hits are genuinely positive ("reduced uncertainty following the U.S. election", "favorable news on COVID-19 vaccines"), but "Participants continued to see the uncertainty surrounding the economic outlook as elevated" also scored +0.876. Among the most positive "uncertainty" hits overall is "a major source of uncertainty in the outlook" (+0.986, September 2003).
- Only 19 hits have a window cut short by the start or end of a document.

These findings are the evidence for plan 1.6 (sentence-based scoring).

## Interpreting results with care

VADER measures lexical tone of the surrounding sentence, not the Fed's view or a market signal. A negative score around "inflation" can reflect description of a problem the Fed is addressing rather than concern about its own stance. Use `export_snippets` to read the text behind any pattern before drawing conclusions.

## Deployment idea (not started)

Streamlit app so a user can type keywords into a box and see charts update, hosted free on Streamlit Community Cloud with a public URL. Constraint: the hosted app cannot read local files, and the PDFs are large. Options are to download minutes from federalreserve.gov at runtime, or precompute text and ship a compact dataset. Caching the extracted text (issue 9) is a prerequisite.
