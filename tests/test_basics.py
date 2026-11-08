"""Behavior that later verification work must keep."""

import pandas as pd
import pytest

from fedspeak.extract import extract_date_from_filename
from fedspeak.match import count_keywords


@pytest.mark.parametrize("filename, expected", [
    ("fomcminutes20230201.pdf", "2023-02-01"),
    ("fomcminutes2023-02-01.pdf", "2023-02-01"),
    ("2023/02/fomcminutes20230201.pdf", "2023-02-01"),
])
def test_date_parsed_from_filename(filename, expected):
    assert extract_date_from_filename(filename) == pd.Timestamp(expected)


def test_undated_filename_returns_none():
    assert extract_date_from_filename("notes.pdf") is None


def test_frequency_is_per_thousand_words():
    text = "inflation " + "word " * 499  # 1 hit in 500 words
    counts = count_keywords(text, ["inflation"])
    assert counts["inflation_raw"] == 1
    assert counts["inflation"] == pytest.approx(2.0)


def test_matching_ignores_case_and_partial_words():
    text = "Inflation rose. INFLATION fell. Disinflation continued."
    assert count_keywords(text, ["inflation"])["inflation_raw"] == 2


def test_empty_text_gives_zero_frequency():
    counts = count_keywords("", ["inflation"])
    assert counts["inflation"] == 0
    assert counts["inflation_raw"] == 0
