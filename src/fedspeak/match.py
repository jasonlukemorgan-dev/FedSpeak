"""Keyword matching: one function finds every hit, and both frequency and sentiment use it.

Matching rules
- Case-insensitive, whole words only: "inflation" does not match "disinflation"
  or "inflationary".
- Multi-word keywords ("price stability") match across any whitespace, including
  line breaks.
- Dashes separate words: "inflation—as", "uncertainty--inflation" are hits.
- Hyphenated compounds ("Inflation-Protected Securities", "pre-recession",
  "maximum-employment") are hits only when `include_hyphenated` is True
  (config MATCH_HYPHENATED). A single hyphen joining two word characters marks a
  compound; a double hyphen or a dash does not.
"""

import re
from bisect import bisect_right
from dataclasses import dataclass

from fedspeak.config import MATCH_HYPHENATED


@dataclass(frozen=True)
class Hit:
    keyword: str        # the keyword as configured
    matched: str        # the exact text matched, original case and spacing
    start: int          # character offset in the text
    end: int            # character offset just past the match
    word_start: int     # index in text.split() of the word containing the first character
    word_end: int       # index in text.split() of the word containing the last character


def keyword_pattern(keyword, include_hyphenated=MATCH_HYPHENATED):
    words = [re.escape(w) for w in keyword.lower().split()]
    body = r"\s+".join(words)
    left, right = r"(?<!\w)", r"(?!\w)"
    if not include_hyphenated:
        # Not part of a compound: no "word-" before, no "-word" after.
        left += r"(?<!\w-)"
        right += r"(?!-\w)"
    return re.compile(left + body + right, re.IGNORECASE)


def find_hits(text, keywords, include_hyphenated=MATCH_HYPHENATED):
    """Every occurrence of every keyword in text, in document order."""
    word_starts = [m.start() for m in re.finditer(r"\S+", text)]
    hits = []
    for kw in keywords:
        for m in keyword_pattern(kw, include_hyphenated).finditer(text):
            hits.append(Hit(
                keyword=kw,
                matched=m.group(0),
                start=m.start(),
                end=m.end(),
                word_start=bisect_right(word_starts, m.start()) - 1,
                word_end=bisect_right(word_starts, m.end() - 1) - 1,
            ))
    hits.sort(key=lambda h: (h.start, h.keyword))
    return hits


def count_keywords(text, keywords, hits=None):
    """Frequency per 1,000 words for each keyword, plus raw counts under `<kw>_raw`.

    Pass `hits` from find_hits to reuse them; otherwise they are found here.
    """
    if hits is None:
        hits = find_hits(text, keywords)
    word_count = len(text.split())
    counts = {}
    for kw in keywords:
        raw = sum(h.keyword == kw for h in hits)
        counts[kw] = (raw / word_count) * 1000 if word_count > 0 else 0
        counts[f"{kw}_raw"] = raw
    return counts
