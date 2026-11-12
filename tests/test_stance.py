"""Stance model plumbing (plan section 4), tested with a fake classifier: no network, no torch."""

import pandas as pd
import pytest

from fedspeak.extract import text_filename
from fedspeak.pipeline import process_minutes
from fedspeak.stance import (
    HIT_COLUMNS, StanceScorer, document_index, keyword_stance, scorer_from_config, stance_record,
)

HAWKISH = {"dovish": 0.1, "hawkish": 0.7, "neutral": 0.2}
DOVISH = {"dovish": 0.6, "hawkish": 0.1, "neutral": 0.3}
NEUTRAL = {"dovish": 0.2, "hawkish": 0.2, "neutral": 0.6}


class FakeClassifier:
    """Hawkish for text with "rise", dovish for "fall", neutral otherwise. Records every call."""

    def __init__(self):
        self.calls = []

    def __call__(self, texts):
        self.calls.append(list(texts))
        return [HAWKISH if "rise" in t else DOVISH if "fall" in t else NEUTRAL for t in texts]


def scorer(tmp_path=None, classify=None, revision="abc123"):
    return StanceScorer(classify or FakeClassifier(), "test/model", revision,
                        tmp_path / "cache.sqlite" if tmp_path else None)


def test_record_has_label_probabilities_and_score():
    r = stance_record(HAWKISH)
    assert list(r) == HIT_COLUMNS
    assert r["stance_label"] == "hawkish"
    assert (r["p_hawkish"], r["p_dovish"], r["p_neutral"]) == (0.7, 0.1, 0.2)
    assert r["stance_score"] == pytest.approx(0.7 - 0.1)
    assert stance_record(DOVISH)["stance_score"] == pytest.approx(-0.5)
    assert stance_record(NEUTRAL)["stance_label"] == "neutral"


def test_score_keeps_order_and_classifies_each_text_once():
    fake = FakeClassifier()
    s = scorer(classify=fake)
    out = s.score(["rates will rise", "rates will fall", "rates will rise", "the meeting began"])
    assert [r["stance_label"] for r in out] == ["hawkish", "dovish", "hawkish", "neutral"]
    assert sorted(fake.calls[0]) == sorted(["rates will rise", "rates will fall", "the meeting began"])


def test_cache_is_reused_without_calling_the_classifier(tmp_path):
    first = scorer(tmp_path)
    expected = first.score(["rates will rise", "rates will fall"])
    first.close()

    def must_not_run(texts):
        raise AssertionError(f"classifier called for {texts}")

    again = scorer(tmp_path, classify=must_not_run)
    assert again.score(["rates will fall", "rates will rise"]) == expected[::-1]
    again.close()


def test_cache_scores_only_new_text(tmp_path):
    scorer(tmp_path).score(["rates will rise"])
    fake = FakeClassifier()
    scorer(tmp_path, classify=fake).score(["rates will rise", "rates will fall"])
    assert fake.calls == [["rates will fall"]]


def test_cache_is_keyed_by_revision(tmp_path):
    scorer(tmp_path, revision="abc123").score(["rates will rise"])
    fake = FakeClassifier()
    scorer(tmp_path, classify=fake, revision="def456").score(["rates will rise"])
    assert fake.calls == [["rates will rise"]]


def test_classifier_returning_wrong_count_raises():
    with pytest.raises(RuntimeError, match="1 results for 2 texts"):
        scorer(classify=lambda texts: [NEUTRAL]).score(["a", "b"])


def test_keyword_stance_is_mean_and_nan_without_hits():
    records = [{"keyword": "inflation", "stance_score": 0.6}, {"keyword": "inflation", "stance_score": -0.2}]
    out = keyword_stance(records, ["inflation", "recession"])
    assert out["inflation_stance"] == pytest.approx(0.2)
    assert pd.isna(out["recession_stance"])


def test_document_index_counts_sentence_labels():
    text = "Rates will rise. Rates will rise. Prices may fall. The meeting began at noon."
    out = document_index(text, scorer())
    assert out == {"doc_stance_index": pytest.approx((2 - 1) / 4), "doc_stance_hawkish": 2,
                   "doc_stance_dovish": 1, "doc_stance_sentences": 4}


def test_document_index_of_empty_text_is_nan():
    assert pd.isna(document_index("", scorer())["doc_stance_index"])


def make_corpus(tmp_path):
    text_dir = tmp_path / "text"
    text_dir.mkdir()
    for date, text in [
        ("2022-06-15", "Participants expected inflation to rise further. The staff reviewed the outlook."),
        ("2020-03-15", "Inflation was likely to fall. Recession risks were seen as likely to rise."),
    ]:
        (text_dir / text_filename(date)).write_text(text, encoding="utf-8")
    return text_dir


def test_pipeline_adds_stance_columns_and_averages(tmp_path):
    df, hits = process_minutes(make_corpus(tmp_path), ["inflation", "recession"], stance=scorer())
    assert list(hits.columns)[-len(HIT_COLUMNS) - 1:] == HIT_COLUMNS + ["context"]
    assert list(hits.stance_label) == ["dovish", "hawkish", "hawkish"]   # 2020 inflation, 2020 recession, 2022
    means = hits.groupby(["date", "keyword"]).stance_score.mean()
    for (date, kw), mean in means.items():
        assert df.set_index("date").loc[date, f"{kw}_stance"] == pytest.approx(mean)
    june = df.set_index("date").loc[pd.Timestamp("2022-06-15")]
    assert pd.isna(june["recession_stance"])                 # no hits: NaN, not neutral
    assert june["doc_stance_index"] == pytest.approx(1 / 2)  # one hawkish sentence of two
    assert june["doc_stance_sentences"] == 2


def test_pipeline_document_index_can_be_turned_off(tmp_path):
    fake = FakeClassifier()
    df, _ = process_minutes(make_corpus(tmp_path), ["inflation"], stance=scorer(classify=fake), stance_document=False)
    assert "inflation_stance" in df.columns
    assert not any(c.startswith("doc_stance") for c in df.columns)
    assert all(len(call) <= 1 for call in fake.calls)   # only hit clauses were classified


def test_pipeline_output_unchanged_with_stance_off(tmp_path):
    text_dir = make_corpus(tmp_path)
    df_off, hits_off = process_minutes(text_dir, ["inflation", "recession"])
    df_on, hits_on = process_minutes(text_dir, ["inflation", "recession"], stance=scorer())
    assert not any("stance" in c for c in list(df_off.columns) + list(hits_off.columns))
    pd.testing.assert_frame_equal(df_off, df_on[df_off.columns])
    pd.testing.assert_frame_equal(hits_off, hits_on[hits_off.columns])


def test_scorer_from_config_is_off_by_default():
    assert scorer_from_config(model_id=None) is None


def test_scorer_from_config_explains_missing_libraries(monkeypatch, capsys):
    import fedspeak.stance as stance
    monkeypatch.setattr(stance, "stance_available", lambda: False)
    assert scorer_from_config(model_id="test/model") is None
    assert "uv sync --extra stance" in capsys.readouterr().out


def test_dashboard_adds_index_panel_only_with_index(tmp_path, monkeypatch):
    import fedspeak.dashboard as dashboard
    monkeypatch.setattr(dashboard, "DASHBOARD_HTML", tmp_path / "dash.html")
    df, _ = process_minutes(make_corpus(tmp_path), ["inflation"], stance=scorer())
    with_index = dashboard.build_dashboard(df.copy(), ["inflation"], measure="stance", show=False)
    assert len(with_index.layout.annotations) == 4 and with_index.layout.height == 1450
    without = dashboard.build_dashboard(df.drop(columns=[c for c in df if c.startswith("doc_stance")]),
                                        ["inflation"], measure="stance", show=False)
    assert len(without.layout.annotations) == 3 and without.layout.height == 1100


def test_dashboard_stance_measure_needs_stance_columns(tmp_path):
    from fedspeak.dashboard import build_dashboard
    df, _ = process_minutes(make_corpus(tmp_path), ["inflation"])
    with pytest.raises(ValueError, match="STANCE_MODEL"):
        build_dashboard(df, ["inflation"], measure="stance", show=False)


def test_real_model_smoke():
    """Optional: runs only when torch, transformers and the cached weights are present."""
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    from huggingface_hub import try_to_load_from_cache
    from fedspeak.config import STANCE_MODEL_REVISION
    model = "gtfintechlab/FOMC-RoBERTa"
    cached = [try_to_load_from_cache(model, f, revision=STANCE_MODEL_REVISION)
              for f in ("model.safetensors", "pytorch_model.bin")]
    if not any(isinstance(p, str) for p in cached):
        pytest.skip("FOMC-RoBERTa weights not in the Hugging Face cache")
    from fedspeak.stance import load_classifier
    classify = load_classifier(model, STANCE_MODEL_REVISION)
    out = StanceScorer(classify, model).score([
        "the Committee decided to raise the target range to combat persistent inflation pressures",
        "the Committee decided to lower the target range to support employment amid weak demand",
    ])
    assert out[0]["stance_score"] > out[1]["stance_score"]
