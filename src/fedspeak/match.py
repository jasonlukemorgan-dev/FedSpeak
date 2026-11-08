"""Keyword matching and frequency.

Verification work (docs/plan.md section 1.2) replaces this with a single
matcher that produces hit records for both frequency and sentiment.
"""

import re


def count_keywords(text, keywords):
    """Frequency per 1,000 words for each keyword, plus raw counts under `<kw>_raw`."""
    lower_text = text.lower()
    words = lower_text.split()
    word_count = len(words)
    counts = {}
    for kw in keywords:
        pattern = rf'\b{re.escape(kw.lower())}\b'
        raw = len(re.findall(pattern, lower_text))
        counts[kw] = (raw / word_count) * 1000 if word_count > 0 else 0
        counts[f"{kw}_raw"] = raw
    return counts
