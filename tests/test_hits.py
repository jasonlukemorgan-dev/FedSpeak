"""Hit records (plan 1.3): every field must be checkable against the text."""

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from fedspeak.match import find_hits
from fedspeak.sentiment import score_hits

TEXT = ("Inflation remained elevated. " + " ".join(f"w{i}" for i in range(40)) +
        " Participants saw recession risks and uncertainty about inflation. " +
        " ".join(f"v{i}" for i in range(40)))
KW = ["inflation", "recession", "uncertainty"]


def records(window=10):
    return score_hits(TEXT, find_hits(TEXT, KW), window=window)


def test_offsets_point_at_the_matched_text():
    for r in records():
        assert TEXT[r["char_start"]:r["char_end"]] == r["matched"]
        assert r["matched"].lower() == r["keyword"]


def test_words_taken_each_side_are_recorded_and_correct():
    n_words = len(TEXT.split())
    for r in records(window=10):
        assert r["words_left"] == min(10, r["word_start"])
        assert r["words_right"] == min(10, n_words - 1 - r["word_end"])
        assert len(r["context"].split()) == r["words_left"] + (r["word_end"] - r["word_start"] + 1) + r["words_right"]
        assert r["context"].split()[r["words_left"]].strip(".").lower() == r["keyword"]


def test_first_hit_window_is_cut_at_document_start():
    first = records(window=10)[0]
    assert first["word_start"] == 0 and first["words_left"] == 0 and first["words_right"] == 10


def test_stored_score_is_the_score_of_the_stored_context():
    analyzer = SentimentIntensityAnalyzer()
    for r in records():
        assert r["score"] == analyzer.polarity_scores(r["context"])["compound"]


def test_context_is_the_exact_full_window():
    # Previously snippets were cut to 200 characters and re-scored later.
    words = TEXT.split()
    for r in records(window=40):
        start = r["word_start"] - r["words_left"]
        end = r["word_end"] + r["words_right"] + 1
        assert r["context"] == " ".join(words[start:end])


def test_overlap_between_nearby_hits_is_reported():
    recs = records(window=10)
    by_kw = {r["keyword"]: r for r in recs[1:]}
    # "recession", "uncertainty" and the second "inflation" sit within a few words of each other.
    assert recs[0]["window_overlap_words"] == 0
    assert by_kw["recession"]["window_overlap_words"] == 0      # 40 filler words after the first hit
    assert by_kw["uncertainty"]["window_overlap_words"] > 15
    assert recs[-1]["window_overlap_words"] > 15
