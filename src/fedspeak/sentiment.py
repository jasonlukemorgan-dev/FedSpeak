"""VADER sentiment of the text around each keyword hit.

score_hits builds one record per hit: where it is, the exact context that was
scored, how many words that context took on each side, and the score. The score is
computed once here and stored; nothing downstream re-scores text.

Two ways to choose the context (config CONTEXT_MODE):
- "window":   CONTEXT_WINDOW words on each side of the hit.
- "sentence": the sentence containing the hit, plus SENTENCE_NEIGHBORS sentences on
              each side. Keeps tone from unrelated sentences out of the score.

Vocabulary: VADER's general-English lexicon, adjusted for Fed language by the
reviewable word list at config FED_LEXICON (data/lexicon/fed_vader_overrides.csv).
"""

import copy
import csv
import re
from bisect import bisect_right

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from fedspeak.config import (
    CONTEXT_MODE, CONTEXT_WINDOW, EXCLUDE_KEYWORD_FROM_SCORE, FED_LEXICON, SENTENCE_NEIGHBORS,
)
from fedspeak.match import find_hits

# Tokens ending in "." that do not end a sentence in the minutes. Single capital
# letters (initials such as "Brian F. Madigan") are handled separately.
ABBREVIATIONS = {
    "mr.", "ms.", "mrs.", "mses.", "messrs.", "dr.", "st.", "jr.", "sr.", "gov.",
    "u.s.", "u.k.", "a.m.", "p.m.", "e.g.", "i.e.", "no.", "nos.", "vs.", "inc.",
    "co.", "corp.", "ltd.", "jan.", "feb.", "aug.", "sept.", "oct.", "nov.", "dec.",
}
SENTENCE_END = re.compile(r"[.!?][\"'”’)\]]*$")
SENTENCE_START = re.compile(r"[\"'“‘(\[]*[A-Z0-9]")


def sentence_spans(words):
    """Split a list of words into sentences. Returns [(first_word, last_word + 1), ...].

    A word ends a sentence when it ends in . ! or ? (optionally followed by a closing
    quote or bracket), is not a known abbreviation or a single-letter initial, and
    the next word starts with a capital letter, a digit, or an opening quote/bracket.
    """
    spans, start = [], 0
    for i, word in enumerate(words[:-1]):
        if not SENTENCE_END.search(word):
            continue
        bare = word.lower().rstrip("\"'”’)]")
        if bare in ABBREVIATIONS or re.fullmatch(r"[a-z]\.", bare):
            continue
        if SENTENCE_START.match(words[i + 1]):
            spans.append((start, i + 1))
            start = i + 1
    if words:
        spans.append((start, len(words)))
    return spans

_BASE_ANALYZER = None
_ANALYZERS = {}


def load_lexicon_overrides(path):
    """{word: valence} from a Fed lexicon CSV (columns: word, valence, ...)."""
    with open(path, newline="", encoding="utf-8") as f:
        return {row["word"].strip().lower(): float(row["valence"]) for row in csv.DictReader(f)}


def get_analyzer(lexicon_path=FED_LEXICON, exclude_words=()):
    """A VADER analyzer with Fed lexicon overrides applied and some words removed.

    Overrides with valence 0 remove the word from VADER's lexicon (it no longer
    carries tone); other overrides set or add the word's valence. `exclude_words`
    are removed as well, which is how a keyword is kept from scoring its own
    sentence. Analyzers are cached per combination.
    """
    global _BASE_ANALYZER
    key = (str(lexicon_path) if lexicon_path else None, frozenset(w.lower() for w in exclude_words))
    if key not in _ANALYZERS:
        if _BASE_ANALYZER is None:
            _BASE_ANALYZER = SentimentIntensityAnalyzer()
        lexicon = dict(_BASE_ANALYZER.lexicon)
        if lexicon_path:
            for word, valence in load_lexicon_overrides(lexicon_path).items():
                if valence == 0:
                    lexicon.pop(word, None)
                else:
                    lexicon[word] = valence
        for word in key[1]:
            lexicon.pop(word, None)
        analyzer = copy.copy(_BASE_ANALYZER)
        analyzer.lexicon = lexicon
        _ANALYZERS[key] = analyzer
    return _ANALYZERS[key]


def score_hits(text, hits, window=CONTEXT_WINDOW, mode=CONTEXT_MODE, neighbors=SENTENCE_NEIGHBORS,
               lexicon_path=FED_LEXICON, exclude_keyword=EXCLUDE_KEYWORD_FROM_SCORE):
    """One record per hit, in document order.

    mode "window": `window` words before the first matched word and after the last
    one, cut short only at the start or end of the document.
    mode "sentence": the sentence(s) containing the hit plus `neighbors` sentences
    on each side.
    `words_left` and `words_right` record what was actually taken.
    `window_overlap_words` counts words shared with the previous hit's context (any
    keyword), since nearby hits score overlapping text.
    Scoring uses VADER with the Fed lexicon at `lexicon_path` (None for plain VADER).
    With `exclude_keyword`, the hit's own keyword words carry no tone, so a sentence
    about "recession" is not negative merely because it says "recession"; other
    keywords in the sentence still count.
    """
    if mode not in ("window", "sentence"):
        raise ValueError(f"CONTEXT_MODE must be 'window' or 'sentence', not {mode!r}")
    words = text.split()
    if mode == "sentence":
        spans = sentence_spans(words)
        span_starts = [s for s, _ in spans]
    records = []
    prev_end = None
    for hit in sorted(hits, key=lambda h: (h.start, h.keyword)):
        if mode == "window":
            w_start = max(0, hit.word_start - window)
            w_end = min(len(words), hit.word_end + window + 1)   # exclusive
        else:
            first = bisect_right(span_starts, hit.word_start) - 1
            last = bisect_right(span_starts, hit.word_end) - 1
            w_start = spans[max(0, first - neighbors)][0]
            w_end = spans[min(len(spans) - 1, last + neighbors)][1]
        context = " ".join(words[w_start:w_end])
        analyzer = get_analyzer(lexicon_path, hit.keyword.split() if exclude_keyword else ())
        records.append({
            "keyword": hit.keyword,
            "matched": hit.matched,
            "char_start": hit.start,
            "char_end": hit.end,
            "word_start": hit.word_start,
            "word_end": hit.word_end,
            "words_left": hit.word_start - w_start,
            "words_right": w_end - 1 - hit.word_end,
            "window_overlap_words": max(0, prev_end - w_start) if prev_end is not None else 0,
            "score": analyzer.polarity_scores(context)["compound"],
            "context": context,
        })
        prev_end = w_end if prev_end is None else max(prev_end, w_end)
    return records


def keyword_sentiment(text, keywords, window=CONTEXT_WINDOW, hits=None, mode=CONTEXT_MODE,
                      neighbors=SENTENCE_NEIGHBORS):
    """Average VADER score per keyword over its hits.

    Returns ({"<kw>_sentiment": avg or NaN if no hits, "<kw>_sentiment_n": hits}, records), where
    records come from score_hits. Hits come from match.find_hits, the same hits
    that frequency counts use.
    """
    if hits is None:
        hits = find_hits(text, keywords)
    records = score_hits(text, hits, window, mode=mode, neighbors=neighbors)

    avg_sentiments = {}
    for kw in keywords:
        scores = [r["score"] for r in records if r["keyword"] == kw]
        # No mentions means no tone to measure: NaN, not 0, which would read as neutral.
        avg_sentiments[f"{kw}_sentiment"] = sum(scores) / len(scores) if scores else float("nan")
        avg_sentiments[f"{kw}_sentiment_n"] = len(scores)

    return avg_sentiments, records
