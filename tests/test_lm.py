"""Loughran-McDonald measures. Uses a tiny stand-in dictionary so tests never need the licensed file."""

import pandas as pd
import pytest

from fedspeak.extract import text_filename
from fedspeak.lm import document_measures, hit_measures, load_lm, net_tone
from fedspeak.match import find_hits
from fedspeak.sentiment import score_hits

HEADER = "Word,Seq_num,Negative,Positive,Uncertainty,Litigious\n"


@pytest.fixture
def lm_file(tmp_path):
    rows = [
        "RECESSION,1,2009,0,0,0",
        "WEAK,2,2009,0,0,0",
        "STRONG,3,0,2009,0,0",
        "IMPROVED,4,0,2009,0,0",
        "UNCERTAINTY,5,0,0,2009,0",
        "MAY,6,0,0,2009,0",
        "OLDWORD,7,-2012,0,0,0",       # negative year: removed from the list
    ]
    p = tmp_path / "lm.csv"
    p.write_text(HEADER + "\n".join(rows) + "\n", encoding="utf-8")
    load_lm.cache_clear()
    yield p
    load_lm.cache_clear()


def test_loader_reads_categories_and_drops_removed_words(lm_file):
    lm = load_lm(lm_file)
    assert lm["negative"] == {"RECESSION", "WEAK"}
    assert lm["positive"] == {"STRONG", "IMPROVED"}
    assert lm["uncertainty"] == {"UNCERTAINTY", "MAY"}


def test_missing_file_means_no_lm(tmp_path):
    assert load_lm(tmp_path / "absent.csv") is None


def test_net_tone():
    assert net_tone(3, 1) == 0.5 and net_tone(0, 2) == -1 and net_tone(0, 0) == 0


def test_hit_measures_exclude_the_keyword(lm_file):
    lm = load_lm(lm_file)
    m = hit_measures("The recession may deepen despite strong demand.", "recession", lm)
    assert (m["lm_positive"], m["lm_negative"], m["lm_uncertainty"]) == (1, 0, 1)
    assert m["lm_tone"] == 1.0
    m2 = hit_measures("The recession may deepen despite strong demand.", "recession", lm, exclude_keyword=False)
    assert m2["lm_negative"] == 1 and m2["lm_tone"] == 0.0


def test_document_rates_per_thousand(lm_file):
    lm = load_lm(lm_file)
    text = "weak " * 2 + "strong " + "word " * 97      # 100 words
    d = document_measures(text, lm)
    assert d["doc_lm_negative"] == pytest.approx(20.0)
    assert d["doc_lm_positive"] == pytest.approx(10.0)
    assert d["doc_lm_tone"] == pytest.approx(-1 / 3)


def test_hit_records_carry_lm_fields_only_when_available(lm_file, tmp_path):
    text = "Growth improved. The recession was weak."
    hits = find_hits(text, ["recession"])
    (with_lm,) = score_hits(text, hits, mode="sentence", lm_path=lm_file)
    (without,) = score_hits(text, hits, mode="sentence", lm_path=tmp_path / "absent.csv")
    assert with_lm["lm_negative"] == 1 and with_lm["lm_tone"] == -1.0
    assert "lm_tone" not in without


def _corpus(tmp_path):
    d = tmp_path / "text"
    d.mkdir()
    (d / text_filename("2020-03-15")).write_text("Uncertainty may rise. The outlook was strong.", encoding="utf-8")
    return d


def test_pipeline_adds_lm_columns(lm_file, tmp_path):
    from fedspeak.pipeline import process_minutes
    df, hits = process_minutes(_corpus(tmp_path), ["uncertainty"], lm_path=lm_file)
    assert {"uncertainty_lm_tone", "uncertainty_lm_uncertainty", "doc_lm_uncertainty"} <= set(df.columns)
    assert df.loc[0, "uncertainty_lm_uncertainty"] == 1      # "may"; the keyword itself is excluded
    assert {"lm_tone", "lm_uncertainty"} <= set(hits.columns)
    assert df.loc[0, "doc_lm_uncertainty"] == pytest.approx(2 / 7 * 1000)   # "uncertainty", "may" in 7 words


def test_pipeline_runs_without_lm(tmp_path, capsys):
    from fedspeak.pipeline import process_minutes
    df, hits = process_minutes(_corpus(tmp_path), ["uncertainty"], lm_path=tmp_path / "absent.csv")
    assert "uncertainty_lm_tone" not in df.columns and "lm_tone" not in hits.columns
    assert "Loughran-McDonald dictionary not found" in capsys.readouterr().out
