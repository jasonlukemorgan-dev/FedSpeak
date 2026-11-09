"""VADER sentiment of the text around each keyword hit.

score_hits builds one record per hit: where it is, the exact context that was
scored, how many words that context took on each side, and the score. The score is
computed once here and stored; nothing downstream re-scores text.

Three ways to choose the context (config CONTEXT_MODE):
- "window":   CONTEXT_WINDOW words on each side of the hit.
- "sentence": the sentence containing the hit, plus SENTENCE_NEIGHBORS sentences on
              each side. Keeps tone from unrelated sentences out of the score.
- "clause":   the hit's sentence split at contrast words ("but", "although", "while"
              and others, rules in clause_bounds), keeping only the hit's clause, so
              "inflation was low, but growth slowed" does not give "inflation" the tone
              of "growth slowed". SENTENCE_NEIGHBORS is ignored.

Vocabulary: VADER's general-English lexicon, adjusted for Fed language by the
reviewable word list at config FED_LEXICON (data/lexicon/fed_vader_overrides.csv).
"""

import copy
import csv
import re
from bisect import bisect_right

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from fedspeak.config import (
    CONTEXT_MODE, CONTEXT_WINDOW, EXCLUDE_KEYWORD_FROM_SCORE, FED_LEXICON, LM_DICTIONARY, SENTENCE_NEIGHBORS,
)
from fedspeak.lm import hit_measures, load_lm
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


# Clause splitting (plan option b). Rules were set from a sample of 1,264 keyword
# sentences (docs/context.md): sentence-initial "However", "Nonetheless" and "But"
# point back to the previous sentence; "yet" is almost always a time word; ", though,"
# is an adverb and "though minor," an aside; "while" without a comma before it usually
# means "at the same time".
SUBORDINATORS = {"although", "though", "whereas", "while"}   # can open "Although A, B."
AFTER_PUNCT = (",", ";", "—", "–", "--")
MIN_CLAUSE_WORDS = 3   # clause words besides the keyword; shorter clauses fall back to the sentence


def _core(word):
    return re.sub(r"^\W+|\W+$", "", word.lower())


def _contrast_at(words, i, start):
    """Length of the contrast phrase at words[i] that marks a clause boundary, else 0.

    `start` is the index of the sentence's first word.
    """
    core = _core(words[i])
    nxt = _core(words[i + 1]) if i + 1 < len(words) else ""
    prev = words[i - 1] if i > start else ""
    after_punct = prev.endswith(AFTER_PUNCT) or prev in ("—", "–", "--")
    if core == "but":
        return 1 if after_punct and nxt != "also" else 0
    if core == "however":
        return 1 if prev.endswith(";") else 0
    if core in ("although", "whereas"):
        return 1 if after_punct else 0
    if core == "even" and nxt in ("though", "as"):
        return 2 if after_punct else 0
    if core == "while":
        return 1 if (after_punct and not prev.endswith(("—", "–", "--"))
                     and not nxt.endswith("ing") and _core(prev) != "a") else 0
    if core == "though":
        if not after_punct or words[i].endswith(","):
            return 0
        aside = any(w.endswith(",") for w in words[i + 1:i + 4])
        return 0 if aside else 1
    return 0


def clause_bounds(words, start, end, word_start, word_end):
    """The clause of sentence words[start:end] containing words word_start..word_end.

    Returns (clause_start, clause_end, split_at). split_at names the contrast word(s)
    at the clause's edges ("but", "although/but"), or "" when the whole sentence is
    used. The contrast word itself is left out of the clause; VADER would otherwise
    weight every word after a leading "but" by 1.5.

    Boundaries:
    - "but" after a comma, semicolon or dash, except "but also".
    - "however" after a semicolon. Not ", however," or a sentence-initial "However".
    - "although", "whereas", "even though", "even as" after punctuation.
    - "while" after a comma or semicolon, unless the next word ends in -ing
      ("while maintaining") or it follows "a" ("for a while").
    - "though" after a comma or semicolon, unless it is ", though," (an adverb) or an
      aside closed by a comma within three words ("though minor,").
    - "Although", "Though", "Whereas" or "While" opening the sentence: the first clause
      runs to the first comma. Wrong when that clause has its own comma (known limit).
    Falls back to the whole sentence when the clause would have fewer than
    MIN_CLAUSE_WORDS words besides the keyword.
    """
    cuts = []   # (first dropped word, first word of next clause, contrast word)
    if _core(words[start]) in SUBORDINATORS:
        comma = next((j for j in range(start + 1, end - 1) if words[j].endswith(",")), None)
        if comma is not None:
            cuts += [(start, start + 1, _core(words[start])), (comma + 1, comma + 1, _core(words[start]))]
    for i in range(start + 1, end):
        n = _contrast_at(words, i, start)
        if n:
            cuts.append((i, i + n, " ".join(_core(w) for w in words[i:i + n])))
    cuts.sort()

    # Pieces between cuts, each with the contrast words on its left and right edges.
    pieces, pos, left = [], start, ""
    for a, b, word in cuts:
        if a > pos:
            pieces.append((pos, a, left, word))
        pos, left = max(pos, b), word
    if end > pos:
        pieces.append((pos, end, left, ""))

    inside = [p for p in pieces if p[1] > word_start and p[0] <= word_end]
    if not inside or inside[0][0] > word_start or inside[-1][1] <= word_end:
        return start, end, ""   # hit falls on a contrast word
    c_start, c_end = inside[0][0], inside[-1][1]
    if (c_start, c_end) == (start, end):
        return start, end, ""
    if (c_end - c_start) - (word_end - word_start + 1) < MIN_CLAUSE_WORDS:
        return start, end, ""
    split_at = "/".join(dict.fromkeys(w for w in (inside[0][2], inside[-1][3]) if w))
    return c_start, c_end, split_at

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
               lexicon_path=FED_LEXICON, exclude_keyword=EXCLUDE_KEYWORD_FROM_SCORE, lm_path=LM_DICTIONARY):
    """One record per hit, in document order.

    mode "window": `window` words before the first matched word and after the last
    one, cut short only at the start or end of the document.
    mode "sentence": the sentence(s) containing the hit plus `neighbors` sentences
    on each side.
    mode "clause": the hit's clause within its sentence (clause_bounds); records get
    `split_at`, the contrast word(s) the clause was cut at, "" if not split.
    `words_left` and `words_right` record what was actually taken.
    `window_overlap_words` counts words shared with the previous hit's context (any
    keyword), since nearby hits score overlapping text.
    Scoring uses VADER with the Fed lexicon at `lexicon_path` (None for plain VADER).
    With `exclude_keyword`, the hit's own keyword words carry no tone, so a sentence
    about "recession" is not negative merely because it says "recession"; other
    keywords in the sentence still count.
    When the Loughran-McDonald dictionary is available (`lm_path`), each record also
    gets lm_positive, lm_negative, lm_uncertainty and lm_tone for the same context.
    """
    lm = load_lm(lm_path) if lm_path else None
    if mode not in ("window", "sentence", "clause"):
        raise ValueError(f"CONTEXT_MODE must be 'window', 'sentence' or 'clause', not {mode!r}")
    words = text.split()
    if mode in ("sentence", "clause"):
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
            if mode == "clause":
                # A hit across a sentence break (rare) keeps both sentences unsplit.
                if first == last:
                    w_start, w_end, split_at = clause_bounds(words, *spans[first], hit.word_start, hit.word_end)
                else:
                    w_start, w_end, split_at = spans[first][0], spans[last][1], ""
            else:
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
            **({"split_at": split_at} if mode == "clause" else {}),
            "score": analyzer.polarity_scores(context)["compound"],
            **(hit_measures(context, hit.keyword, lm, exclude_keyword) if lm else {}),
            "context": context,
        })
        prev_end = w_end if prev_end is None else max(prev_end, w_end)
    return records


def keyword_sentiment(text, keywords, window=CONTEXT_WINDOW, hits=None, mode=CONTEXT_MODE,
                      neighbors=SENTENCE_NEIGHBORS, lm_path=LM_DICTIONARY):
    """Average VADER score per keyword over its hits.

    Returns ({"<kw>_sentiment": avg or NaN if no hits, "<kw>_sentiment_n": hits}, records), where
    records come from score_hits. Hits come from match.find_hits, the same hits
    that frequency counts use.
    """
    if hits is None:
        hits = find_hits(text, keywords)
    records = score_hits(text, hits, window, mode=mode, neighbors=neighbors, lm_path=lm_path)

    avg_sentiments = {}
    for kw in keywords:
        scores = [r["score"] for r in records if r["keyword"] == kw]
        # No mentions means no tone to measure: NaN, not 0, which would read as neutral.
        avg_sentiments[f"{kw}_sentiment"] = sum(scores) / len(scores) if scores else float("nan")
        avg_sentiments[f"{kw}_sentiment_n"] = len(scores)
        kw_records = [r for r in records if r["keyword"] == kw]
        if records and "lm_tone" in records[0]:
            avg_sentiments[f"{kw}_lm_tone"] = (sum(r["lm_tone"] for r in kw_records) / len(kw_records)
                                               if kw_records else float("nan"))
            avg_sentiments[f"{kw}_lm_uncertainty"] = (sum(r["lm_uncertainty"] for r in kw_records) / len(kw_records)
                                                      if kw_records else float("nan"))

    return avg_sentiments, records
