"""VADER sentiment of the text around each keyword hit."""

import re
from collections import defaultdict

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from fedspeak.config import CONTEXT_WINDOW


def keyword_sentiment(text, keywords, window=CONTEXT_WINDOW):
    """
    For each keyword, find every occurrence, extract `window` words of context
    on each side, run VADER sentiment on that snippet, and average the scores.
    Returns ({"<kw>_sentiment": avg, "<kw>_sentiment_n": hits}, {kw: [snippets]}).
    """
    analyzer = SentimentIntensityAnalyzer()
    words = text.split()
    sentiment_scores = defaultdict(list)
    snippet_log = defaultdict(list)

    for i, word in enumerate(words):
        clean_word = re.sub(r'[^a-z]', '', word.lower())
        for kw in keywords:
            if clean_word == kw.lower():
                start = max(0, i - window)
                end = min(len(words), i + window + 1)
                snippet = " ".join(words[start:end])
                score = analyzer.polarity_scores(snippet)["compound"]
                sentiment_scores[kw].append(score)
                snippet_log[kw].append(snippet[:200])

    avg_sentiments = {}
    for kw in keywords:
        scores = sentiment_scores[kw]
        avg_sentiments[f"{kw}_sentiment"] = sum(scores) / len(scores) if scores else 0
        avg_sentiments[f"{kw}_sentiment_n"] = len(scores)

    return avg_sentiments, dict(snippet_log)
