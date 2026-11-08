"""Audit page build and label scoring (plan 1.5)."""

import pandas as pd

from fedspeak.audit import build_audit, score_audit
from fedspeak.extract import text_filename


def corpus(tmp_path):
    d = tmp_path / "text"
    d.mkdir()
    texts = {
        "2020-01-29": "Growth was solid. Uncertainty about the outlook was elevated and worrying. Inflation stayed low.",
        "2021-06-16": "Inflation rose sharply. Participants welcomed the strong recovery. Uncertainty had diminished.",
    }
    for date, t in texts.items():
        (d / text_filename(date)).write_text(t, encoding="utf-8")
    return d


def test_build_audit_is_reproducible_and_complete(tmp_path):
    text_dir = corpus(tmp_path)
    page, n = build_audit(["uncertainty", "inflation"], per_keyword=5, seed=1,
                          out_dir=tmp_path / "a", text_dir=text_dir)
    sample = pd.read_csv(tmp_path / "a" / "audit_sample.csv")
    assert n == len(sample) == 4                     # only 2 hits per keyword exist
    html = page.read_text(encoding="utf-8")
    assert html.count('<section class="item"') == 4
    assert "<mark>Uncertainty</mark>" in html
    page2, _ = build_audit(["uncertainty", "inflation"], per_keyword=5, seed=1,
                           out_dir=tmp_path / "b", text_dir=text_dir)
    assert pd.read_csv(tmp_path / "b" / "audit_sample.csv").id.tolist() == sample.id.tolist()


def test_sentence_bounds_in_sample_are_the_hit_sentence(tmp_path):
    text_dir = corpus(tmp_path)
    build_audit(["uncertainty"], per_keyword=5, seed=1, out_dir=tmp_path / "a", text_dir=text_dir)
    s = pd.read_csv(tmp_path / "a" / "audit_sample.csv").iloc[0]
    words = (text_dir / "fomcminutes20200129.txt").read_text(encoding="utf-8").split()
    assert " ".join(words[s.sentence_start:s.sentence_end]) == \
        "Uncertainty about the outlook was elevated and worrying."


def test_score_audit_reports_agreement(tmp_path, capsys):
    text_dir = corpus(tmp_path)
    build_audit(["uncertainty"], per_keyword=5, seed=1, out_dir=tmp_path / "a", text_dir=text_dir)
    sample = pd.read_csv(tmp_path / "a" / "audit_sample.csv")
    labels = tmp_path / "labels.csv"
    pd.DataFrame({"id": sample.id, "keyword": sample.keyword, "match_ok": ["yes", "yes"],
                  "tone": ["negative", "positive"], "note": ["", ""]}).to_csv(labels, index=False)
    df = score_audit(labels, tmp_path / "a" / "audit_sample.csv")
    out = capsys.readouterr().out
    assert len(df) == 2
    assert "Labelled hits: 2 of 2" in out and "sentence" in out and "window75" in out
