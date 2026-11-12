"""Hawkish or dovish stance from a fine-tuned language model (plan section 4).

Model: gtfintechlab/FOMC-RoBERTa, a RoBERTa-large fine-tune from Shah, Paturi and
Chava (2023), "Trillion Dollar Words: A New Financial Dataset, Task & Market
Analysis", ACL 2023 (https://aclanthology.org/2023.acl-long.368). Model, data and code
are licensed CC BY-NC 4.0: non-commercial use with attribution. Access is gated on
Hugging Face: accept the terms with your own account, then run `hf auth login` once.

Measures
- Per hit: the probabilities of the three labels for the hit's clause (the same
  context VADER scores, keyword kept in), the most likely label, and
  stance_score = p_hawkish - p_dovish, from -1 (dovish) to +1 (hawkish).
- Per meeting and keyword: mean stance_score over the keyword's hits, NaN without hits.
- Per meeting document: the paper's index, (hawkish sentences - dovish sentences) /
  all sentences, using each sentence's most likely label. Keyword-free.

The model sits behind a plain function, texts -> [{"dovish": p, "hawkish": p,
"neutral": p}, ...], so tests use a fake classifier and need neither torch nor the
weights. Results are cached in SQLite keyed by a hash of (model, revision, text), so
reruns and keyword changes only score text the model has not seen.
"""

import hashlib
import importlib.util
import sqlite3
from pathlib import Path

from fedspeak.config import STANCE_BATCH_SIZE, STANCE_CACHE, STANCE_MODEL, STANCE_MODEL_REVISION
from fedspeak.sentiment import sentence_spans

LABELS = ("dovish", "hawkish", "neutral")   # model output order: LABEL_0, LABEL_1, LABEL_2
HIT_COLUMNS = ["stance_label", "p_hawkish", "p_dovish", "p_neutral", "stance_score"]
INSTALL_HINT = ("Stance model is on (STANCE_MODEL) but torch and transformers are not installed. "
                "Run `uv sync --extra stance` and start runs with `uv run --extra stance fedspeak`. "
                "Skipping stance.")
ACCESS_HINT = ("Could not load {model} from Hugging Face: {error}\n"
               "Access is gated: accept the terms at https://huggingface.co/{model} with your own account "
               "and run `hf auth login` once. Skipping stance.")
UNPINNED_HINT = ("STANCE_MODEL_REVISION is not set, so results follow whatever the model's main branch holds. "
                 "Pin a commit hash in config.py for reproducible results.")


def stance_available():
    return all(importlib.util.find_spec(m) is not None for m in ("torch", "transformers"))


def load_classifier(model_id, revision=None, batch_size=STANCE_BATCH_SIZE, device=None):
    """A classify(texts) function backed by the real model. GPU at half precision when
    available, CPU otherwise. Texts longer than 512 tokens are truncated."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    dtype = torch.float16 if device == "cuda" else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
    model = AutoModelForSequenceClassification.from_pretrained(model_id, revision=revision, dtype=dtype)
    model = model.to(device).eval()
    if model.config.num_labels != len(LABELS):
        raise ValueError(f"{model_id} has {model.config.num_labels} labels, expected {len(LABELS)}")

    def classify(texts):
        # Similar lengths batched together waste less padding.
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        probs = [None] * len(texts)
        with torch.inference_mode():
            for b in range(0, len(order), batch_size):
                idx = order[b:b + batch_size]
                batch = tokenizer([texts[i] for i in idx], padding=True, truncation=True, max_length=512,
                                  return_tensors="pt").to(device)
                p = torch.softmax(model(**batch).logits.float(), dim=-1).cpu().tolist()
                for i, row in zip(idx, p):
                    probs[i] = dict(zip(LABELS, row))
        return probs

    return classify


def stance_record(probs):
    """Hit columns from one {"dovish", "hawkish", "neutral"} probability dict."""
    return {
        "stance_label": max(LABELS, key=lambda k: probs[k]),
        "p_hawkish": probs["hawkish"],
        "p_dovish": probs["dovish"],
        "p_neutral": probs["neutral"],
        "stance_score": probs["hawkish"] - probs["dovish"],
    }


class StanceScorer:
    """Scores texts with `classify`, reading and writing the cache at `cache_path`
    (None for no cache). Each distinct uncached text is classified once."""

    CHUNK = 1024   # texts classified between cache writes, so an interrupted run keeps its work

    def __init__(self, classify, model_id, revision=None, cache_path=None):
        self.classify = classify
        self.model_id = model_id
        self.revision = revision or "main"
        self.db = None
        if cache_path:
            Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(cache_path)
            self.db.execute("CREATE TABLE IF NOT EXISTS stance "
                            "(key TEXT PRIMARY KEY, dovish REAL, hawkish REAL, neutral REAL)")

    def _key(self, text):
        return hashlib.sha256(f"{self.model_id}\0{self.revision}\0{text}".encode("utf-8")).hexdigest()

    def _cached(self, keys):
        found = {}
        if self.db is None:
            return found
        keys = list(keys)
        for i in range(0, len(keys), 500):   # stay under SQLite's limit on query parameters
            part = keys[i:i + 500]
            rows = self.db.execute(f"SELECT key, dovish, hawkish, neutral FROM stance "
                                   f"WHERE key IN ({','.join('?' * len(part))})", part)
            found.update({k: dict(zip(LABELS, p)) for k, *p in rows})
        return found

    def probabilities(self, texts):
        """[{"dovish", "hawkish", "neutral"}, ...] for texts, in order."""
        keys = [self._key(t) for t in texts]
        probs = self._cached(set(keys))
        todo = list({k: t for k, t in zip(keys, texts) if k not in probs}.items())
        for i in range(0, len(todo), self.CHUNK):
            part = todo[i:i + self.CHUNK]
            new = self.classify([t for _, t in part])
            if len(new) != len(part):
                raise RuntimeError(f"classifier returned {len(new)} results for {len(part)} texts")
            probs.update({k: p for (k, _), p in zip(part, new)})
            if self.db is not None:
                with self.db:
                    self.db.executemany("INSERT OR REPLACE INTO stance VALUES (?, ?, ?, ?)",
                                        [(k, *(p[label] for label in LABELS)) for (k, _), p in zip(part, new)])
        return [probs[k] for k in keys]

    def score(self, texts):
        """Hit columns (stance_record) for each text, in order."""
        return [stance_record(p) for p in self.probabilities(texts)]

    def close(self):
        if self.db is not None:
            self.db.close()
            self.db = None


def keyword_stance(records, keywords):
    """{"<kw>_stance": mean stance_score over the keyword's hits, NaN without hits}."""
    out = {}
    for kw in keywords:
        scores = [r["stance_score"] for r in records if r["keyword"] == kw]
        out[f"{kw}_stance"] = sum(scores) / len(scores) if scores else float("nan")
    return out


def document_index(text, scorer):
    """The paper's per-document index over every sentence: (hawkish - dovish) / all."""
    words = text.split()
    sentences = [" ".join(words[a:b]) for a, b in sentence_spans(words)]
    labels = [r["stance_label"] for r in scorer.score(sentences)]
    hawkish, dovish = labels.count("hawkish"), labels.count("dovish")
    return {
        "doc_stance_index": (hawkish - dovish) / len(labels) if labels else float("nan"),
        "doc_stance_hawkish": hawkish,
        "doc_stance_dovish": dovish,
        "doc_stance_sentences": len(labels),
    }


def scorer_from_config(model_id=STANCE_MODEL, revision=STANCE_MODEL_REVISION, cache_path=STANCE_CACHE):
    """A StanceScorer for the configured model, or None (with a printed reason) when
    stance is off, the libraries are missing, or the model cannot be reached.

    Only the small model config is fetched here, which confirms access. The 1.4 GB
    weights load on the first text that is not already cached.
    """
    if not model_id:
        return None
    if not stance_available():
        print(INSTALL_HINT + "\n")
        return None
    from transformers import AutoConfig
    try:
        AutoConfig.from_pretrained(model_id, revision=revision)
    except Exception as error:   # gated access, no login, no network: report and run without stance
        print(ACCESS_HINT.format(model=model_id, error=error) + "\n")
        return None
    if revision is None:
        print(UNPINNED_HINT + "\n")

    loaded = None

    def classify(texts):
        nonlocal loaded
        if loaded is None:
            loaded = load_classifier(model_id, revision)
        return loaded(texts)

    return StanceScorer(classify, model_id, revision, cache_path)
