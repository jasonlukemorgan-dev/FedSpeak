"""Read the cleaned minutes text and run counting and sentiment per meeting."""

from pathlib import Path

import pandas as pd
from tqdm import tqdm

from fedspeak.config import LM_DICTIONARY
from fedspeak.extract import extract_date_from_filename
from fedspeak.lm import DOWNLOAD_HINT, document_measures, load_lm
from fedspeak.match import count_keywords, find_hits
from fedspeak.sentiment import keyword_sentiment

HIT_COLUMNS = [
    "date", "meeting_type", "filename", "keyword", "matched", "char_start", "char_end",
    "word_start", "word_end", "words_left", "words_right", "window_overlap_words", "score",
    "lm_positive", "lm_negative", "lm_uncertainty", "lm_tone", "context",
]


def process_minutes(text_dir, keywords, start_date=None, end_date=None, manifest_path=None,
                    lm_path=LM_DICTIONARY):
    """Process every meeting's text file in text_dir, optionally limited to meetings
    between start_date and end_date (inclusive, "YYYY-MM-DD" or None).

    Returns (meetings, hits):
    - meetings: one row per meeting with frequency and average sentiment per keyword
      (plus meeting type and release date when a manifest is given).
    - hits: one row per keyword hit with its position, scored context and score.
      Every number in `meetings` can be traced to rows here.
    """
    start = pd.Timestamp(start_date) if start_date else None
    end = pd.Timestamp(end_date) if end_date else None
    results = []
    hit_rows = []

    files = sorted(Path(text_dir).glob("*.txt"))
    if not files:
        print(f"No minutes text found in {text_dir}. Run `fedspeak fetch` (or `fedspeak extract`) first.")
        return pd.DataFrame(), pd.DataFrame(columns=HIT_COLUMNS)

    selected = []
    for path in files:
        date = extract_date_from_filename(path.name)
        if not date:
            print(f"  Skipping {path.name}: couldn't parse date.")
            continue
        if (start is not None and date < start) or (end is not None and date > end):
            continue
        selected.append((date, path))

    if not selected:
        print("No meetings fall inside the selected date range.")
        return pd.DataFrame(), pd.DataFrame(columns=HIT_COLUMNS)

    print(f"Analyzing {len(selected)} meetings ({selected[0][0].date()} to {selected[-1][0].date()})\n")
    lm = load_lm(lm_path) if lm_path else None
    if lm is None:
        print(DOWNLOAD_HINT.format(path=lm_path) + "\n")

    for date, path in tqdm(selected, desc="Analyzing minutes"):
        text = path.read_text(encoding="utf-8")
        hits = find_hits(text, keywords)
        freq = count_keywords(text, keywords, hits=hits)
        sentiments, records = keyword_sentiment(text, keywords, hits=hits, lm_path=lm_path if lm else None)
        for kw in keywords:
            # Frequency and sentiment must describe the same hits (plan 1.2).
            if freq[f"{kw}_raw"] != sentiments[f"{kw}_sentiment_n"]:
                raise RuntimeError(f"{path.name}: {kw} has {freq[f'{kw}_raw']} frequency hits "
                                   f"but {sentiments[f'{kw}_sentiment_n']} sentiment hits")

        hit_rows += [{"date": date, "filename": path.name, **r} for r in records]
        doc = document_measures(text, lm) if lm else {}
        results.append({"date": date, "filename": path.name, **freq, **sentiments, **doc})

    df = pd.DataFrame(results).sort_values("date").reset_index(drop=True)
    hit_cols = [c for c in HIT_COLUMNS if c != "meeting_type" and (lm or not c.startswith("lm_"))]
    hits_df = pd.DataFrame(hit_rows, columns=hit_cols)

    if manifest_path and Path(manifest_path).exists():
        manifest = pd.read_csv(manifest_path, dtype=str).fillna("")
        meta = manifest[["meeting_date", "meeting_type", "release_date"]].assign(
            date=lambda m: pd.to_datetime(m.meeting_date)).drop(columns="meeting_date")
        df = df.merge(meta, on="date", how="left")
        cols = ["date", "meeting_type", "release_date"]
        df = df[cols + [c for c in df.columns if c not in cols]]
        hits_df = hits_df.merge(meta[["date", "meeting_type"]], on="date", how="left")
    else:
        hits_df["meeting_type"] = ""

    return df, hits_df[[c for c in HIT_COLUMNS if c in hits_df.columns]]
