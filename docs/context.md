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
5. Partly fixed in version 6: a Fed word list adjusts VADER (see Fed vocabulary for VADER above). "tightening" and "accommodative" were deliberately left unscored, since their tone depends on context. Sentence constructions a word list cannot read remain.
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

### 1.4 Zero mentions (2026-11-08)

Sentiment is now NaN when a keyword is not mentioned. With the default keywords this removed fake 0.000 "neutral" scores from 191 of 270 meetings for "recession", 59 for "tightening" and 13 for "uncertainty".

### 1.6 Window vs sentence context (2026-11-08)

`fedspeak verify context` scores all 17,153 hits three ways. Results in `output/verify/context_modes.csv`.

| | 75-word window | Sentence | Sentence plus one each side |
|---|---|---|---|
| Median words scored | 151 | 32 | 91 |
| Hits overlapping previous context | 84% | 27% (same sentence only) | 72% |
| Tone positive / neutral / negative | 72% / 2% / 26% | 47% / 20% / 33% | 66% / 4% / 30% |
| Scores at or beyond plus or minus 0.9 | 22% | 1% | 9% |
| Same tone label as window | | 55% | 80% |

Per-meeting averages correlate with the window at 0.48 to 0.72 (sentence) and 0.81 to 0.92 (sentence plus one), by keyword.

Reading: VADER's compound score saturates on long passages, so the window labels almost nothing neutral and pushes a fifth of hits to the extremes. Sentence scoring fixes the clearest failures: "Participants continued to see the uncertainty surrounding the economic outlook as elevated" moves from +0.876 to -0.340; three separate "major source of uncertainty in the outlook" sentences move to -0.19, -0.67 and -0.73 (window: +0.99, -0.97, +0.91). Sentence scoring still inherits VADER's general vocabulary, for example "inflation ... still were low" reads negative because "low" is a negative word in general English (known issue: finance lexicon).

The sentence splitter (`sentiment.sentence_spans`) handles titles, initials, "U.S.", "a.m." and similar; 61,612 sentences, median 26 words. A few attendance lists and tables form very long sentences (up to 1,039 words); keyword hits there are rare.

Decision (2026-11-08): default `CONTEXT_MODE` is now "sentence", on the corpus evidence above. The user chose not to label the audit first; the audit page remains available as a later confirmation (`fedspeak audit`, then `--labels`). The window stays available as a setting.

Effect on corpus averages (mean of per-meeting sentiment, window to sentence): uncertainty +0.27 to -0.16, recession +0.03 to -0.31, inflation +0.39 to +0.09, employment +0.41 to +0.20, tightening +0.43 to +0.13. Under the window, "uncertainty" and "recession" read as positive or neutral on average, which the text does not support. Results from before this change are not comparable.

Remaining weakness: VADER's general vocabulary. "Subject to substantial uncertainty" scored +0.96 because the same sentence contains "dissipate" and "increasing"; "inflation ... still were low" reads negative. Next step on the roadmap: a Fed-specific lexicon or Loughran-McDonald comparison.

### Fed vocabulary for VADER (2026-11-08)

Method: counted every VADER lexicon word in the 17,153 keyword sentences and ranked by total pull (count times valence). The top of that list showed systematic misreadings, which `data/lexicon/fed_vader_overrides.csv` corrects. Each row has the new valence, VADER's original, a category and a reason.

- Finance nouns VADER treats as emotion are set to no tone: interest (+2.0, "interest rates"), energy, crude (-2.7, "crude oil"), credit, securities, asset(s), treasury, united ("United States").
- Topic and procedural words: growth (+1.6; "growth slowed" is not positive, the modifier carries tone), demand, agreed, commitment, lags, well.
- Direction words whose tone depends on the subject: increase(d), low, lower, lowest. VADER was inconsistent here: "increase" +1.3 but "rise" and "decline" unscored, so "inflation increased" read positive and "inflation rose" neutral.
- Fed terms VADER lacks, added with moderate values: elevated (-0.8, 1,017 uses), deterioration and deteriorated (-1.5), unanchored (-1.5), anchored (+0.8), headwinds (-1.0), tailwinds (+1.0), resilient and resilience (+1.2).
- Left unscored on purpose because their tone depends on what they describe: subdued, moderate, firming, upside, slack, transitory, persistent, accommodative, restrictive.

Keyword self-exclusion (`EXCLUDE_KEYWORD_FROM_SCORE = True`): VADER scores "uncertainty" -1.4, "recession" -1.8 and "unemployment" -1.9, so every sentence about those topics started negative before any surrounding language counted. The hit's own keyword is now removed from the lexicon when scoring its sentence; other keywords in the sentence still count. This changes what the sentiment of a keyword means: it is now the tone of the language around the word ("reduced uncertainty" positive, "elevated uncertainty" negative), consistent with the project's definition. It can be switched off.

Effect on all hits (sentence mode; mean score, then positive / neutral / negative share):

| | Plain VADER | Fed words | Fed words and self-exclusion |
|---|---|---|---|
| uncertainty | -0.19, 27/5/69% | -0.34, 15/4/82% | -0.04, 33/23/44% |
| inflation | +0.09, 47/21/32% | +0.00, 33/34/33% | +0.00, 33/34/33% |
| employment | +0.21, 55/23/22% | +0.12, 44/32/24% | +0.12, 44/32/24% |
| recession | -0.33, 22/2/77% | -0.45, 12/2/86% | -0.13, 30/16/54% |
| tightening | +0.11, 51/17/31% | -0.02, 33/30/37% | -0.02, 33/30/37% |
| all hits | +0.09, 47/20/33% | -0.01, 33/31/36% | +0.02, 35/33/33% |

25 percent of hits changed tone label. Spot checks: descriptive and procedural sentences now read neutral; "elevated" and "upside risks" language reads negative; "inflation ... still were low" is no longer negative.

Limits a word list cannot fix: "How soon the gloom ... would dissipate was subject to substantial uncertainty" still scores +0.92 (from "pickup", "profits"); "a major source of uncertainty ... the strength of such investment" scores +0.23 once the keyword is excluded. The Statement on Longer-Run Goals, repeated in minutes since 2012, contributes the same boilerplate sentences each year. Loughran-McDonald (a finance dictionary) is free for academic research but needs a license for commercial use (sraf.nd.edu, checked 2026-11-08) and is not included.

### Loughran-McDonald measures (2026-11-08)

Added as a second, standard measure alongside Fed-adjusted VADER. Word lists are used unmodified so results stay comparable with the finance literature. Terms (sraf.nd.edu): free for academic research, commercial use needs a license; the user's work is non-commercial for now. The file is not committed (redistribution is not addressed); it sits in `data/lexicon/external/` and the pipeline runs without it.

Per hit: LM positive, negative and uncertainty word counts in the hit's sentence (keyword excluded) and net tone (positive - negative) / (positive + negative). Per meeting: `<kw>_lm_tone`, `<kw>_lm_uncertainty`, and whole-document rates per 1,000 words (`doc_lm_positive`, `doc_lm_negative`, `doc_lm_uncertainty`, `doc_lm_tone`).

How LM reads Fed vocabulary: it already treats "crude", "low", "increase", "growth" and "inflation" as neutral, but it was built from corporate filings, so it marks "easing" and "tightening" negative and lacks "elevated", "headwinds" and "anchored".

First results:
- Per hit, LM and Fed-adjusted VADER correlate at 0.48 and give the same tone label 54 percent of the time; 46 percent of hit sentences contain no LM tone words. Per meeting, correlation by keyword is 0.42 to 0.63. They measure different things and should be read side by side, not averaged.
- Whole-document LM tone is most negative in 2001 (-0.48), 2007 (-0.40) and 2008 (-0.62); negative words peak at 30.2 per 1,000 in 2001 and 27.7 in 2008. This matches the recessions and is a basic validity check.
- LM uncertainty peaks in 2007 (20.1 per 1,000) but is lowest in 2020 to 2023 (about 14). The uncertainty list includes hedging words ("may", "could", "depend"), so it tracks drafting style as well as uncertainty. Treat it with caution and read the text behind any movement.

### Clause scoring at contrast words (2026-11-09)

Problem: a sentence such as "Inflation remained subdued, but growth was disappointing" gives "inflation" the tone of the other half. `CONTEXT_MODE = "clause"` splits the hit's sentence at contrast words and scores only the keyword's clause, leaving the contrast word out (VADER weights everything after a leading "but" by 1.5).

Rules were set from a sample of 20 meetings (1,264 hits; 24 percent of keyword sentences contain a contrast word):
- "However" opened the sentence in 53 of 85 cases and "nonetheless" and "nevertheless" nearly always do. There they refer back to the previous sentence, so they do not split. "however" splits only after a semicolon.
- "yet" was a time word in every case ("not yet", "yet to be realized") and never splits.
- "while" splits after a comma or semicolon or at the start of a sentence. Without a comma it usually means "at the same time" ("depreciated against the yen while depreciating against the Canadian dollar"). Also excluded: "while" followed by an -ing word, and "a while".
- "though" splits after a comma or semicolon, except ", though," (an adverb: "Others, though, saw") and short asides closed by a comma within three words ("the probability, though minor, of a fall").
- "but" splits after a comma, semicolon or dash, not in "modest but rising" or "but also".
- A sentence opening with "Although", "Though", "Whereas" or "While" is cut at the first comma.
- A clause with fewer than three words besides the keyword falls back to the whole sentence.

Corpus results (17,153 hits, Fed-adjusted VADER, keyword excluded; `fedspeak verify context`):
- 2,423 hits (14 percent) are split: but 883, while 762, although 532, though 160, however 54, others under 20.
- Median words scored: 29 (sentence 32). Tone positive / neutral / negative: 33 / 35 / 32 percent (sentence 35 / 33 / 33).
- Of split hits, 72 percent keep the same tone label. Most changes go to neutral (314 positive and 219 negative become neutral); 119 flip sign.
- Mean score of split hits, sentence to clause: uncertainty +0.08 to +0.02, inflation +0.04 to +0.03, employment +0.06 to +0.08, recession -0.31 to -0.14 (20 hits), tightening unchanged.
- Per-meeting averages correlate with sentence mode at 0.93 to 0.98 by keyword; the largest single meeting shift is 0.83.

Spot checks (random sample of 15 split hits): most clauses are the right unit. "Recent developments had increased ... uncertainties ..., most members felt the risks continued to point toward rising inflation" moves from -0.67 to -0.27 once the uncertainty clause is dropped; "substantial uncertainty surrounded the outlook ... inflation", previously +0.15 from the clause before "however", now reads -0.38.

Known limits:
- A pronoun carries the keyword into the next clause: "Although inflation had moderated ..., it remained well above the Committee's goal" scores only "inflation had moderated" (0.00) and loses the main point.
- Elliptical clauses: "expect inflation to remain low ..., but to rise to 2 percent" keeps only the first half for "inflation".
- A sentence-initial clause with its own comma is cut too early ("Although energy prices, which are volatile, rose, ...").
- Shorter clauses contain fewer tone words, so more hits read neutral. Part of that is correct (the tone belonged to the other clause), part is VADER missing words ("concerns ... had increased appreciably" scores 0.00).

Decision (2026-11-09): default `CONTEXT_MODE` is now "clause", on the corpus evidence and spot checks above, again without audit labels (`fedspeak audit` shows the clause score beside the others for a later check). "sentence" stays available as a setting.

Effect on corpus averages (mean of per-meeting sentiment, sentence to clause; Fed-adjusted VADER): uncertainty -0.014 to -0.030, inflation +0.003 to +0.001, employment +0.103 to +0.104, recession -0.107 to -0.075, tightening -0.012 to -0.009. Loughran-McDonald net tone moves by at most 0.03 (tightening -0.34 to -0.30). Largest single-meeting shifts: recession 0.83, uncertainty 0.45, tightening 0.44. Frequency is unchanged. The change is small on average and concentrated in individual meetings, so results from before it are broadly but not exactly comparable.

### Stance model, FOMC-RoBERTa (2026-11-12, not yet run on the corpus)

Why: VADER and Loughran-McDonald measure tone, not policy direction. "Inflation remained elevated" is negative in tone and hawkish in stance; a dictionary cannot tell those apart. A model fine-tuned on FOMC text can.

Model and attribution: `gtfintechlab/FOMC-RoBERTa`, Financial Services Innovation Lab, Georgia Tech; Shah, Paturi and Chava, "Trillion Dollar Words: A New Financial Dataset, Task & Market Analysis", ACL 2023 (https://aclanthology.org/2023.acl-long.368). Model, data and code are CC BY-NC 4.0: non-commercial use with attribution, which matches how the project is used now. Recheck if that changes. Access is gated and reviewed by the authors; the user requested access on 2026-11-12 (reviews happen about every 14 days).

Decisions (2026-11-12):
- CUDA build of torch, as an optional extra, so a plain `uv sync` stays light. The laptop's RTX 4050 (6 GB, driver CUDA 12.9) runs the model at half precision.
- Scope: per-hit stance and the whole-meeting index.
- Dashboard: `"stance"` as a `DASHBOARD_SENTIMENT` option and a fourth panel for the index. The user left the panel choice to Claude; the index is keyword-free, so it has no place in the per-keyword sentiment panel, and the plan's validity check (hawkish around 1994, 2004 to 2006 and 2022, dovish in 2001, 2008 and 2020) needs it on the timeline. The panel appears only when the index is in the results, so the three-panel layout settings are unchanged; with four panels the figure is 1450 high with spacing 0.09, about the same gap in pixels as before.
- Input: the same clause VADER scores, keyword kept in (the model needs the whole clause). The document index uses every sentence from `sentiment.sentence_spans`, labelled by the most likely class.
- Cache keyed by a hash of model, revision and text in `output/stance_cache.sqlite`. Only the small model config is fetched at startup, to confirm access; the weights load only when some text is not cached.

Still to do after access is granted: pin `STANCE_MODEL_REVISION`, first corpus run, the checks in plan section 4 (index history, correlation with VADER and LM, 20 to 30 hand-read clauses), confirm the paper's training data range, clause splitting and reported F1, and `fedspeak verify stance`.

## Session log

### 2026-11-12

- Project folder moved to `Projects\Automation Projects\FedSpeak` during a PC reorganization. Two local commits (clause scoring, stance scoping) were pushed after a check that they held nothing sensitive.
- GitHub repo made public, after a scan of the code and history for secrets and third-party files (none found; the LM dictionary is git-ignored). It is linked from the user's GitHub profile.
- Stance model plumbing built and tested with a fake classifier (decisions and reasoning in "Stance model" above). Nothing was tried and abandoned.
- Fragile: `uv run` without `--extra stance` keeps torch installed today but a strict `uv sync` removes it; always pass the extra for stance runs. The Hugging Face access request is the only blocker for the first real run.

## Interpreting results with care

VADER measures lexical tone of the surrounding sentence, not the Fed's view or a market signal. A negative score around "inflation" can reflect description of a problem the Fed is addressing rather than concern about its own stance. Use `export_snippets` to read the text behind any pattern before drawing conclusions.

## Deployment idea (not started)

Streamlit app so a user can type keywords into a box and see charts update, hosted free on Streamlit Community Cloud with a public URL. Constraint: the hosted app cannot read local files, and the PDFs are large. Options are to download minutes from federalreserve.gov at runtime, or precompute text and ship a compact dataset. Caching the extracted text (issue 9) is a prerequisite.
