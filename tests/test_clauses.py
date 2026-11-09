"""Clause mode: score only the clause containing the keyword (contrast-word splitting)."""

import pytest

from fedspeak.match import find_hits
from fedspeak.sentiment import score_hits


def clause(text, keyword="inflation"):
    """(context, split_at) for each hit of keyword, plain VADER, no LM."""
    recs = score_hits(text, find_hits(text, [keyword]), mode="clause", lexicon_path=None, lm_path=None)
    return [(r["context"], r["split_at"]) for r in recs]


# --- Where sentences split ---

@pytest.mark.parametrize("text, expected", [
    ("Inflation remained subdued and stable, but growth slowed sharply in the quarter.",
     ("Inflation remained subdued and stable,", "but")),
    ("Growth slowed sharply in the quarter, but inflation remained subdued and stable.",
     ("inflation remained subdued and stable.", "but")),
    ("Growth was strong in most districts; however, inflation remained well below the objective.",
     ("inflation remained well below the objective.", "however")),
    ("Growth slowed in the quarter, while inflation remained near the committee's objective.",
     ("inflation remained near the committee's objective.", "while")),
    ("Core inflation remained low over the year, although energy prices rose sharply.",
     ("Core inflation remained low over the year,", "although")),
    ("Output rose again in the quarter, even though inflation stayed stubbornly high.",
     ("inflation stayed stubbornly high.", "even though")),
    ("Prices were contained in most sectors, though inflation expectations moved up again.",
     ("inflation expectations moved up again.", "though")),
])
def test_splits_at_contrast_words(text, expected):
    assert clause(text) == [expected]


@pytest.mark.parametrize("text", [
    "However, inflation remained well below the objective and growth slowed.",          # opens sentence
    "Nonetheless, inflation remained well below the objective and growth slowed.",      # never splits
    "Others, however, saw inflation remaining well below the objective for some time.", # ", however,"
    "Others, though, saw inflation remaining well below the objective for some time.",  # ", though,"
    "Inflation was not only elevated across sectors, but also broadening to services.", # "but also"
    "Inflation had been low for a while, and participants expected that to continue.",  # time word
    "Inflation fell in the quarter, while maintaining its earlier downward trend overall.",  # -ing
    "Inflation rose sharply while the dollar depreciated against the yen.",             # no comma
    "Inflation was a modest but rising concern for several participants at the meeting.",  # no comma
    "Inflation had not yet returned to the objective, and growth was slow.",            # "yet"
    "The probability of a fall in inflation, though minor, exceeded that of a rise.",   # aside
])
def test_does_not_split(text):
    ((context, split_at),) = clause(text)
    assert context == text and split_at == ""


# --- Sentence-initial subordinators ---

def test_initial_although_gives_each_side_its_own_clause():
    text = "Although inflation remained low through the year, unemployment rose to its highest level."
    assert clause(text, "inflation") == [("inflation remained low through the year,", "although")]
    assert clause(text, "unemployment") == [("unemployment rose to its highest level.", "although")]


def test_initial_while():
    text = "While economic growth had been strong, inflation was expected to ease over the year."
    assert clause(text) == [("inflation was expected to ease over the year.", "while")]


def test_initial_subordinator_cut_at_first_comma_known_limit():
    # The first clause has its own comma, so the cut lands too early. Documented limit.
    text = "Although energy prices, which are volatile, rose sharply, inflation remained contained overall."
    ((context, _),) = clause(text)
    assert context == "which are volatile, rose sharply, inflation remained contained overall."


# --- Edge cases ---

def test_keyword_in_both_clauses_scored_separately():
    text = ("Inflation in goods prices was falling rapidly and welcome, "
            "but inflation in services remained a serious worry.")
    recs = score_hits(text, find_hits(text, ["inflation"]), mode="clause", lexicon_path=None, lm_path=None)
    assert [r["context"] for r in recs] == [
        "Inflation in goods prices was falling rapidly and welcome,",
        "inflation in services remained a serious worry.",
    ]
    assert recs[0]["score"] > 0 > recs[1]["score"]
    assert recs[1]["window_overlap_words"] == 0


def test_several_split_points_take_the_middle_clause():
    text = ("Growth slowed sharply, but inflation stayed near the objective for now, "
            "although energy prices rose.")
    assert clause(text) == [("inflation stayed near the objective for now,", "but/although")]


def test_short_clause_falls_back_to_sentence():
    text = "Growth slowed sharply across most districts this year, but inflation rose."
    assert clause(text) == [(text, "")]


def test_contrast_word_not_in_context():
    text = "Growth slowed sharply in the quarter, but inflation remained subdued and stable."
    ((context, _),) = clause(text)
    assert not context.lower().startswith("but")


def test_record_positions_and_columns():
    text = "Output fell. Growth slowed sharply in the quarter, but participants saw inflation as subdued."
    (r,) = score_hits(text, find_hits(text, ["inflation"]), mode="clause", lexicon_path=None, lm_path=None)
    assert r["context"] == "participants saw inflation as subdued."
    assert (r["words_left"], r["words_right"], r["split_at"]) == (2, 2, "but")


def test_other_modes_have_no_split_column_and_are_unchanged():
    text = "Growth slowed sharply in the quarter, but inflation remained subdued and stable."
    (r,) = score_hits(text, find_hits(text, ["inflation"]), mode="sentence", lexicon_path=None, lm_path=None)
    assert "split_at" not in r and r["context"] == text


def test_clause_changes_the_score():
    text = "Inflation remained subdued and stable, but growth was terrible and deeply disappointing."
    kw = dict(lexicon_path=None, lm_path=None)
    (sent,) = score_hits(text, find_hits(text, ["inflation"]), mode="sentence", **kw)
    (cl,) = score_hits(text, find_hits(text, ["inflation"]), mode="clause", **kw)
    assert sent["score"] < 0 and cl["score"] >= 0
