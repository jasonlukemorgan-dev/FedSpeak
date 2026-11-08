"""VADER sentiment of the text around each keyword hit.

score_hits builds one record per hit: where it is, the exact context window that
was scored, how many words that window took on each side, and the score. The
score is computed once here and stored; nothing downstream re-scores text.
"""

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from fedspeak.config import CONTEXT_WINDOW
from fedspeak.match import find_hits

_ANALYZER = None


def _analyzer():
    global _ANALYZER
    if _ANALYZER is None:
        _ANALYZER = SentimentIntensityAnalyzer()
    return _ANALYZER


def score_hits(text, hits, window=CONTEXT_WINDOW):
    """One record per hit, in document order.

    The window is `window` words before the first matched word and after the last
    one, cut short only at the start or end of the document. `words_left` and
    `words_right` record what was actually taken. `window_overlap_words` counts
    words shared with the previous hit's window (any keyword), since nearby hits
    score overlapping text.
    """
    words = text.split()
    analyzer = _analyzer()
    records = []
    prev_end = None
    for hit in sorted(hits, key=lambda h: (h.start, h.keyword)):
        w_start = max(0, hit.word_start - window)
        w_end = min(len(words), hit.word_end + window + 1)   # exclusive
        context = " ".join(words[w_start:w_end])
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


def keyword_sentiment(text, keywords, window=CONTEXT_WINDOW, hits=None):
    """Average VADER score per keyword over its hits.

    Returns ({"<kw>_sentiment": avg or NaN if no hits, "<kw>_sentiment_n": hits}, records), where
    records come from score_hits. Hits come from match.find_hits, the same hits
    that frequency counts use.
    """
    if hits is None:
        hits = find_hits(text, keywords)
    records = score_hits(text, hits, window)

    avg_sentiments = {}
    for kw in keywords:
        scores = [r["score"] for r in records if r["keyword"] == kw]
        # No mentions means no tone to measure: NaN, not 0, which would read as neutral.
        avg_sentiments[f"{kw}_sentiment"] = sum(scores) / len(scores) if scores else float("nan")
        avg_sentiments[f"{kw}_sentiment_n"] = len(scores)

    return avg_sentiments, records
