"""Read the cleaned minutes text and run counting and sentiment per meeting."""

from collections import defaultdict
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from fedspeak.extract import extract_date_from_filename
from fedspeak.match import count_keywords
from fedspeak.sentiment import keyword_sentiment


def process_minutes(text_dir, keywords, start_date=None, end_date=None, manifest_path=None):
    """Process every meeting's text file in text_dir, optionally limited to meetings
    between start_date and end_date (inclusive, "YYYY-MM-DD" or None).

    When a manifest is given, each row also gets the meeting type and release date.
    """
    start = pd.Timestamp(start_date) if start_date else None
    end = pd.Timestamp(end_date) if end_date else None
    results = []
    all_snippets = defaultdict(list)

    files = sorted(Path(text_dir).glob("*.txt"))
    if not files:
        print(f"No minutes text found in {text_dir}. Run `fedspeak fetch` (or `fedspeak extract`) first.")
        return pd.DataFrame(), {}

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
        return pd.DataFrame(), {}

    print(f"Analyzing {len(selected)} meetings ({selected[0][0].date()} to {selected[-1][0].date()})\n")

    for date, path in tqdm(selected, desc="Analyzing minutes"):
        text = path.read_text(encoding="utf-8")
        freq = count_keywords(text, keywords)
        sentiments, snippets = keyword_sentiment(text, keywords)

        for kw, snips in snippets.items():
            for s in snips:
                all_snippets[kw].append({"date": date, "snippet": s})

        results.append({"date": date, "filename": path.name, **freq, **sentiments})

    df = pd.DataFrame(results).sort_values("date").reset_index(drop=True)

    if manifest_path and Path(manifest_path).exists():
        manifest = pd.read_csv(manifest_path, dtype=str).fillna("")
        meta = manifest[["meeting_date", "meeting_type", "release_date"]].assign(
            date=lambda m: pd.to_datetime(m.meeting_date)).drop(columns="meeting_date")
        df = df.merge(meta, on="date", how="left")
        cols = ["date", "meeting_type", "release_date"]
        df = df[cols + [c for c in df.columns if c not in cols]]

    return df, all_snippets
