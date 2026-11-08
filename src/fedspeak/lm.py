"""Loughran-McDonald (LM) finance dictionary measures.

LM word lists come from corporate filings and are the standard dictionary in finance
research. They are used unmodified so results stay comparable with that literature.

Terms (sraf.nd.edu, checked 2026-11-08): free for academic research; commercial use
needs a license from the authors (loughranmcdonald@gmail.com). Redistribution is not
addressed, so the file is not committed: it lives in data/lexicon/external/ (git-
ignored). Without it, LM columns are simply left out.

Measures
- Per hit sentence: counts of LM positive, negative and uncertainty words (the hit's
  own keyword excluded, as for VADER) and net tone = (positive - negative) /
  (positive + negative), 0 when the sentence has no tone words.
- Per meeting document: positive, negative and uncertainty words per 1,000 words.
"""

import csv
import re
from functools import lru_cache
from pathlib import Path

from fedspeak.config import LM_DICTIONARY

CATEGORIES = {"positive": "Positive", "negative": "Negative", "uncertainty": "Uncertainty"}
TOKEN = re.compile(r"[A-Za-z]+")
DOWNLOAD_HINT = ("Loughran-McDonald dictionary not found at {path}. Download the Master Dictionary CSV from "
                 "https://sraf.nd.edu/loughranmcdonald-master-dictionary/ (free for academic research; "
                 "commercial use needs a license) and save it there to add LM measures.")


@lru_cache(maxsize=4)
def load_lm(path=LM_DICTIONARY):
    """{category: frozenset of uppercase words}, or None if the file is missing.

    A word belongs to a category when its column holds a positive year (the year it
    was added); a negative year means it was removed and is excluded.
    """
    path = Path(path) if path else None
    if path is None or not path.exists():
        return None
    words = {k: set() for k in CATEGORIES}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for key, column in CATEGORIES.items():
                if int(float(row[column] or 0)) > 0:
                    words[key].add(row["Word"].upper())
    return {k: frozenset(v) for k, v in words.items()}


def lm_available(path=LM_DICTIONARY):
    return load_lm(path) is not None


def count_categories(text, lm, exclude=()):
    """Counts of LM category words in text, ignoring words in `exclude`."""
    excluded = {w.upper() for w in exclude}
    tokens = [t.upper() for t in TOKEN.findall(text)]
    counts = {k: 0 for k in CATEGORIES}
    for t in tokens:
        if t in excluded:
            continue
        for k in CATEGORIES:
            if t in lm[k]:
                counts[k] += 1
    return counts, len(tokens)


def net_tone(positive, negative):
    return (positive - negative) / (positive + negative) if positive + negative else 0.0


def hit_measures(context, keyword, lm, exclude_keyword=True):
    counts, _ = count_categories(context, lm, keyword.split() if exclude_keyword else ())
    return {
        "lm_positive": counts["positive"],
        "lm_negative": counts["negative"],
        "lm_uncertainty": counts["uncertainty"],
        "lm_tone": net_tone(counts["positive"], counts["negative"]),
    }


def document_measures(text, lm):
    """Whole-document LM rates per 1,000 words, the classic measures in the literature."""
    counts, n = count_categories(text, lm)
    per_k = (lambda c: c / n * 1000) if n else (lambda c: float("nan"))
    return {
        "doc_lm_positive": per_k(counts["positive"]),
        "doc_lm_negative": per_k(counts["negative"]),
        "doc_lm_uncertainty": per_k(counts["uncertainty"]),
        "doc_lm_tone": net_tone(counts["positive"], counts["negative"]),
    }
