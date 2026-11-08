"""The shared keyword matcher, and frequency and sentiment agreeing on it (plan 1.2, 1.4)."""

import pytest

from fedspeak.match import count_keywords, find_hits
from fedspeak.sentiment import keyword_sentiment


def kws(hits):
    return [h.keyword for h in hits]


@pytest.mark.parametrize("text, expected", [
    ("inflation rose", 1),
    ("Inflation rose. INFLATION fell.", 2),                 # case
    ("(inflation), inflation; inflation.", 3),              # punctuation
    ("the outlook for inflation—as noted", 1),          # em dash
    ("uncertainty--inflation risks", 1),                    # double hyphen
    ("disinflation and inflationary pressure", 0),          # partial words
    ("inflation's path", 1),                                # possessive
])
def test_matching_rules(text, expected):
    assert len(find_hits(text, ["inflation"])) == expected


def test_hyphenated_compounds_follow_setting():
    text = "Treasury Inflation-Protected Securities; pre-recession levels; anti-inflation stance"
    included = find_hits(text, ["inflation", "recession"], include_hyphenated=True)
    excluded = find_hits(text, ["inflation", "recession"], include_hyphenated=False)
    assert sorted(kws(included)) == ["inflation", "inflation", "recession"]
    assert excluded == []


def test_compounds_excluded_by_default_except_listed_ones():
    text = ("the employment-to-population ratio; the maximum-employment goal; "
            "Maximum-Employment mandate; self-employment income; employment rose")
    hits = find_hits(text, ["employment"])  # defaults: compounds excluded, maximum-employment allowed
    assert [h.matched for h in hits] == ["employment", "Employment", "employment"]
    assert text[hits[0].start - 8:hits[0].end] == "maximum-employment"


def test_exception_list_is_configurable():
    text = "pre-recession levels and a mild-recession scenario"
    hits = find_hits(text, ["recession"], include_hyphenated=False, hyphenated_exceptions=["mild-recession"])
    assert len(hits) == 1 and text[hits[0].start - 5:hits[0].end] == "mild-recession"


def test_dashes_still_count_when_compounds_excluded():
    text = "uncertainty--inflation and inflation—as noted"
    assert len(find_hits(text, ["inflation"], include_hyphenated=False)) == 2


def test_multi_word_keyword_across_line_break():
    text = "the goal of price\nstability and Price Stability"
    hits = find_hits(text, ["price stability"])
    assert [h.matched for h in hits] == ["price\nstability", "Price Stability"]


def test_hit_positions():
    text = "Some participants noted (inflation) risks."
    (hit,) = find_hits(text, ["inflation"])
    assert text[hit.start:hit.end] == "inflation"
    assert text.split()[hit.word_start] == "(inflation)"
    assert hit.word_start == hit.word_end == 3


def test_multi_word_hit_spans_two_words():
    (hit,) = find_hits("a b price stability c", ["price stability"])
    assert (hit.word_start, hit.word_end) == (2, 3)


def test_frequency_and_sentiment_use_the_same_hits():
    # Forms the old sentiment matcher missed: dash-joined, possessive, compound, phrase.
    text = ("Inflation—as expected—rose. The Committee's inflation-protected holdings and "
            "inflation's path. Price stability matters. ") * 3
    keywords = ["inflation", "price stability"]
    freq = count_keywords(text, keywords)
    sent, snippets = keyword_sentiment(text, keywords, window=5)
    for kw in keywords:
        assert freq[f"{kw}_raw"] == sent[f"{kw}_sentiment_n"] == len(snippets[kw])
    assert freq["inflation_raw"] == 6   # "inflation-protected" is a compound, excluded by default
    assert freq["price stability_raw"] == 3


def _window_words(text, keyword, window):
    _, snippets = keyword_sentiment(text, [keyword], window=window)
    return [s.split() for s in snippets[keyword]]


def test_window_takes_exact_words_each_side():
    words = [f"w{i}" for i in range(20)]
    words[10] = "inflation"
    (snippet,) = _window_words(" ".join(words), "inflation", window=3)
    assert snippet == ["w7", "w8", "w9", "inflation", "w11", "w12", "w13"]


def test_window_shortened_only_at_document_edges():
    first = "inflation " + " ".join(f"w{i}" for i in range(10))
    last = " ".join(f"w{i}" for i in range(10)) + " inflation"
    assert _window_words(first, "inflation", 3)[0] == ["inflation", "w0", "w1", "w2"]
    assert _window_words(last, "inflation", 3)[0] == ["w7", "w8", "w9", "inflation"]


def test_window_around_multi_word_keyword():
    (snippet,) = _window_words("a b c price stability d e f", "price stability", window=2)
    assert snippet == ["b", "c", "price", "stability", "d", "e"]
