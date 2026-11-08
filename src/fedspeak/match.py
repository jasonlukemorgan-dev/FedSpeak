"""Keyword matching: one function finds every hit, and both frequency and sentiment use it.

Matching rules
- Case-insensitive, whole words only: "inflation" does not match "disinflation"
  or "inflationary".
- Multi-word keywords ("price stability") match across any whitespace, including
  line breaks.
- Dashes separate words: "inflation—as", "uncertainty--inflation" are hits.
- Hyphenated compounds ("Inflation-Protected Securities", "pre-recession",
  "employment-to-population") are not hits by default: they mostly name a
  security, a statistic or a time period rather than discuss the topic. A single
  hyphen joining two word characters marks a compound; a double hyphen or a dash
  does not.
- Compounds listed in `hyphenated_exceptions` (config HYPHENATED_EXCEPTIONS) are
  still hits, for example "maximum-employment", the Fed's mandate language.
- Set `include_hyphenated` (config MATCH_HYPHENATED) to True to count all compounds.
"""

import re
from bisect import bisect_right
from dataclasses import dataclass

from fedspeak.config import HYPHENATED_EXCEPTIONS, MATCH_HYPHENATED

COMPOUND = re.compile(r"\w+(?:-\w+)+")


@dataclass(frozen=True)
class Hit:
    keyword: str        # the keyword as configured
    matched: str        # the exact text matched, original case and spacing
    start: int          # character offset in the text
    end: int            # character offset just past the match
    word_start: int     # index in text.split() of the word containing the first character
    word_end: int       # index in text.split() of the word containing the last character


def keyword_pattern(keyword):
    """Whole-word, case-insensitive pattern; compounds are filtered in find_hits."""
    words = [re.escape(w) for w in keyword.lower().split()]
    return re.compile(r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)", re.IGNORECASE)


def _compound_around(text, start, end):
    """The hyphenated compound a match sits in, lowercased, or None if it is not in one."""
    if not (re.search(r"\w-$", text[max(0, start - 2):start]) or re.match(r"-\w", text[end:end + 2])):
        return None
    lo, hi = start, end
    for m in COMPOUND.finditer(text, max(0, start - 200), min(len(text), end + 200)):
        if m.start() < end and m.end() > start:
            lo, hi = min(lo, m.start()), max(hi, m.end())
    return text[lo:hi].lower()


def find_hits(text, keywords, include_hyphenated=MATCH_HYPHENATED,
              hyphenated_exceptions=HYPHENATED_EXCEPTIONS):
    """Every occurrence of every keyword in text, in document order."""
    exceptions = {e.lower() for e in hyphenated_exceptions}
    word_starts = [m.start() for m in re.finditer(r"\S+", text)]
    hits = []
    for kw in keywords:
        for m in keyword_pattern(kw).finditer(text):
            if not include_hyphenated:
                compound = _compound_around(text, m.start(), m.end())
                if compound is not None and compound not in exceptions:
                    continue
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
