"""Text corpus build and the analysis loop over data/text."""

import pandas as pd
import pytest

from fedspeak.extract import build_text_corpus, text_filename
from fedspeak.pipeline import process_minutes

KW = ["inflation", "recession"]


def make_corpus(tmp_path):
    text_dir = tmp_path / "text"
    text_dir.mkdir()
    for date, text in [
        ("2020-01-29", "Inflation remained low. " * 10),
        ("2020-03-15", "Participants saw a risk of recession and weak inflation. " * 5),
        ("2021-01-27", "Inflation was expected to rise. " * 8),
    ]:
        (text_dir / text_filename(date)).write_text(text, encoding="utf-8")
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame({
        "meeting_date": ["2020-01-29", "2020-03-15", "2021-01-27"],
        "meeting_type": ["scheduled", "unscheduled", "scheduled"],
        "release_date": ["2020-02-19", "2020-04-08", "2021-02-17"],
    }).to_csv(manifest, index=False)
    return text_dir, manifest


def test_reads_every_meeting_and_adds_manifest_fields(tmp_path):
    text_dir, manifest = make_corpus(tmp_path)
    df, _ = process_minutes(text_dir, KW, manifest_path=manifest)
    assert list(df.date.dt.strftime("%Y-%m-%d")) == ["2020-01-29", "2020-03-15", "2021-01-27"]
    assert list(df.meeting_type) == ["scheduled", "unscheduled", "scheduled"]
    assert df.loc[1, "release_date"] == "2020-04-08"
    assert df.loc[1, "recession_raw"] == 5


def test_no_mentions_gives_missing_sentiment_not_zero(tmp_path):
    # Known issue 3: a 0 here looked identical to genuinely neutral tone.
    text_dir, manifest = make_corpus(tmp_path)
    df, _ = process_minutes(text_dir, KW, manifest_path=manifest)
    jan = df.iloc[0]
    assert jan["recession_raw"] == 0 and jan["recession_sentiment_n"] == 0
    assert pd.isna(jan["recession_sentiment"])
    assert not pd.isna(df.iloc[1]["recession_sentiment"])


def test_summary_reports_no_mentions(tmp_path, capsys):
    from fedspeak.report import print_summary
    text_dir, manifest = make_corpus(tmp_path)
    df, _ = process_minutes(text_dir, KW, manifest_path=manifest)
    print_summary(df, KW)   # latest meeting (2021) has no "recession"
    out = capsys.readouterr().out
    assert "recession       freq: 0.00/1k words   sentiment: none (not mentioned)" in out
    assert "about six months" in out


def test_date_range_is_inclusive(tmp_path):
    text_dir, manifest = make_corpus(tmp_path)
    df, _ = process_minutes(text_dir, KW, start_date="2020-03-15", end_date="2021-01-27")
    assert list(df.date.dt.strftime("%Y-%m-%d")) == ["2020-03-15", "2021-01-27"]


def test_empty_range_returns_empty_frame(tmp_path):
    text_dir, _ = make_corpus(tmp_path)
    df, hits = process_minutes(text_dir, KW, start_date="2030-01-01")
    assert df.empty and hits.empty


def test_hit_table_matches_meeting_counts(tmp_path):
    text_dir, manifest = make_corpus(tmp_path)
    df, hits = process_minutes(text_dir, KW, manifest_path=manifest)
    for kw in KW:
        per_meeting = hits[hits.keyword == kw].groupby("date").size()
        expected = df.set_index("date")[f"{kw}_raw"]
        assert per_meeting.reindex(expected.index, fill_value=0).tolist() == expected.tolist()
        # Average sentiment per meeting is exactly the mean of the stored hit scores.
        means = hits[hits.keyword == kw].groupby("date").score.mean()
        for date, mean in means.items():
            assert df.set_index("date").loc[date, f"{kw}_sentiment"] == pytest.approx(mean)
    assert set(hits.meeting_type) == {"scheduled", "unscheduled"}


def test_hit_table_records_clause_split(tmp_path):
    # Default CONTEXT_MODE is "clause": hits.csv says where each sentence was cut.
    text_dir = tmp_path / "text"
    text_dir.mkdir()
    (text_dir / text_filename("2022-06-15")).write_text(
        "Growth slowed sharply in the quarter, but inflation remained very high and broad.", encoding="utf-8")
    _, hits = process_minutes(text_dir, ["inflation"])
    assert hits.loc[0, "split_at"] == "but"
    assert hits.loc[0, "context"] == "inflation remained very high and broad."
    assert list(hits.columns).index("split_at") == list(hits.columns).index("window_overlap_words") + 1


def test_build_text_corpus_uses_html_and_skips_existing(tmp_path, monkeypatch):
    import fedspeak.config as config
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    (tmp_path / "a.htm").write_text("<html><body><div id='article'><p>Inflation rose.</p></div></body></html>")
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame({"meeting_date": ["2023-02-01", "1993-02-03"], "html_path": ["a.htm", ""]}).to_csv(manifest, index=False)
    out = tmp_path / "text"
    assert build_text_corpus(manifest, out) == 1          # 1993 row has no HTML and is skipped
    assert (out / "fomcminutes20230201.txt").read_text(encoding="utf-8") == "Inflation rose.\n"
    assert build_text_corpus(manifest, out) == 0          # already there
    assert build_text_corpus(manifest, out, force=True) == 1
