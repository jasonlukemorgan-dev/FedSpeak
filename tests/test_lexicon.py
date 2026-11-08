"""Fed vocabulary adjustments and keyword self-exclusion."""

import csv

import pytest

from fedspeak.config import FED_LEXICON
from fedspeak.match import find_hits
from fedspeak.sentiment import get_analyzer, load_lexicon_overrides, score_hits


def score(text, keyword, **kw):
    (r,) = score_hits(text, find_hits(text, [keyword]), mode="sentence", **kw)
    return r["score"]


def test_lexicon_file_is_well_formed():
    with open(FED_LEXICON, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    words = [r["word"] for r in rows]
    assert len(words) == len(set(words)), "duplicate words"
    for r in rows:
        assert r["category"] and r["reason"], f"{r['word']} needs a category and a reason"
        assert -4 <= float(r["valence"]) <= 4


def test_finance_nouns_no_longer_carry_tone():
    plain = get_analyzer(None)
    fed = get_analyzer(FED_LEXICON)
    s = "Interest rates on Treasury securities and crude oil prices were unchanged."
    assert plain.polarity_scores(s)["compound"] != 0
    assert fed.polarity_scores(s)["compound"] == 0


def test_direction_words_are_neutral():
    fed = get_analyzer(FED_LEXICON)
    assert fed.polarity_scores("Inflation was low.")["compound"] == 0
    assert fed.polarity_scores("Inflation increased.")["compound"] == 0


def test_fed_terms_added():
    fed = get_analyzer(FED_LEXICON)
    assert fed.polarity_scores("Inflation expectations became unanchored.")["compound"] < 0
    assert fed.polarity_scores("The economy remained resilient.")["compound"] > 0


def test_keyword_does_not_score_its_own_sentence():
    s = "The staff discussed the recession in the second quarter."
    assert score(s, "recession", exclude_keyword=True) == 0
    assert score(s, "recession", exclude_keyword=False) < 0


def test_other_keywords_in_the_sentence_still_count():
    s = "Inflation fell, but the recession deepened."
    # Scoring the "inflation" hit: "recession" is not the target, so its tone counts.
    assert score(s, "inflation", exclude_keyword=True) < 0


def test_elevated_uncertainty_reads_negative_without_the_keyword_itself():
    # December 2020. Plain VADER's negative score here came only from the word
    # "uncertainty" itself; with self-exclusion the tone must come from "elevated".
    s = ("Participants continued to see the uncertainty surrounding the economic outlook as elevated, "
         "with the path of the economy highly dependent on the course of the virus.")
    assert score(s, "uncertainty") < 0


def test_override_loader():
    overrides = load_lexicon_overrides(FED_LEXICON)
    assert overrides["interest"] == 0 and overrides["elevated"] < 0
    with pytest.raises(FileNotFoundError):
        load_lexicon_overrides("missing.csv")
