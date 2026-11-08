"""VADER sentiment of the text around each keyword hit."""

from collections import defaultdict

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from fedspeak.config import CONTEXT_WINDOW
from fedspeak.match import find_hits


def keyword_sentiment(text, keywords, window=CONTEXT_WINDOW, hits=None):
    """
    For each keyword hit, take `window` words of context on each side of the matched
    words, run VADER on that snippet, and average the scores per keyword.
    Hits come from match.find_hits, the same hits that frequency counts use.
    Returns ({"<kw>_sentiment": avg, "<kw>_sentiment_n": hits}, {kw: [snippets]}).
    """
    if hits is None:
        hits = find_hits(text, keywords)
    analyzer = SentimentIntensityAnalyzer()
    words = text.split()
    sentiment_scores = defaultdict(list)
    snippet_log = defaultdict(list)

    for hit in hits:
        start = max(0, hit.word_start - window)
        end = min(len(words), hit.word_end + window + 1)
        snippet = " ".join(words[start:end])
        score = analyzer.polarity_scores(snippet)["compound"]
        sentiment_scores[hit.keyword].append(score)
        snippet_log[hit.keyword].append(snippet[:200])

    avg_sentiments = {}
    for kw in keywords:
        scores = sentiment_scores[kw]
        avg_sentiments[f"{kw}_sentiment"] = sum(scores) / len(scores) if scores else 0
        avg_sentiments[f"{kw}_sentiment_n"] = len(scores)

    return avg_sentiments, dict(snippet_log)
