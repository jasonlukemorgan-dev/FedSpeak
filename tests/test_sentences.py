"""Sentence splitting and sentence-mode scoring (plan 1.6)."""

import pytest

from fedspeak.match import find_hits
from fedspeak.sentiment import score_hits, sentence_spans


def sentences(text):
    words = text.split()
    return [" ".join(words[s:e]) for s, e in sentence_spans(words)]


def test_splits_on_sentence_endings():
    assert sentences("Inflation rose. Employment fell! Was it temporary? Yes.") == [
        "Inflation rose.", "Employment fell!", "Was it temporary?", "Yes."]


def test_titles_initials_and_common_abbreviations_do_not_split():
    text = ("Mr. Powell and Ms. Yellen met at 9:00 a.m. Present were Messrs. Bullard and the "
            "St. Louis president. Brian F. Madigan noted U.S. exports rose. Inflation fell.")
    assert sentences(text) == [
        "Mr. Powell and Ms. Yellen met at 9:00 a.m. Present were Messrs. Bullard and the St. Louis president.",
        "Brian F. Madigan noted U.S. exports rose.",
        "Inflation fell.",
    ]


def test_lowercase_after_period_does_not_split():
    assert sentences("the rate was 2.5 percent. and so on") == ["the rate was 2.5 percent. and so on"]


def test_closing_quotes_and_opening_brackets():
    assert sentences('He said "inflation is low." (Others disagreed.) Next.') == [
        'He said "inflation is low."', "(Others disagreed.)", "Next."]


TEXT = ("Growth was strong and confidence high. Participants saw the uncertainty surrounding the "
        "outlook as elevated. Markets rallied on good news.")


def test_sentence_mode_scores_only_the_hit_sentence():
    (r,) = score_hits(TEXT, find_hits(TEXT, ["uncertainty"]), mode="sentence", neighbors=0)
    assert r["context"] == "Participants saw the uncertainty surrounding the outlook as elevated."
    assert r["words_left"] == 3 and r["words_right"] == 5


def test_sentence_mode_with_neighbors():
    (r,) = score_hits(TEXT, find_hits(TEXT, ["uncertainty"]), mode="sentence", neighbors=1)
    assert r["context"] == TEXT


def test_two_hits_in_one_sentence_share_context_and_report_overlap():
    text = "Inflation and inflation expectations rose. Output fell."
    recs = score_hits(text, find_hits(text, ["inflation"]), mode="sentence")
    assert recs[0]["context"] == recs[1]["context"] == "Inflation and inflation expectations rose."
    assert recs[1]["window_overlap_words"] == 5


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        score_hits(TEXT, find_hits(TEXT, ["uncertainty"]), mode="paragraph")
