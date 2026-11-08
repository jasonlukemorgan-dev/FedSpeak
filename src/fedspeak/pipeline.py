"""Walk the PDF folder and run extraction, counting and sentiment per meeting."""

import os
from collections import defaultdict

import pandas as pd
from tqdm import tqdm

from fedspeak.extract import extract_date_from_filename, extract_text_from_pdf
from fedspeak.match import count_keywords
from fedspeak.sentiment import keyword_sentiment


def process_pdfs(pdf_dir, keywords):
    results = []
    all_snippets = defaultdict(list)

    # Walk all subdirectories (covers YYYY/MM folder structure)
    files = [
        os.path.join(root, f)
        for root, dirs, filenames in os.walk(pdf_dir)
        for f in filenames if f.endswith(".pdf")
    ]

    if not files:
        print(f"No PDFs found under {pdf_dir}. Check the path and try again.")
        return pd.DataFrame(), {}

    print(f"Found {len(files)} PDFs under {pdf_dir}\n")

    for filepath in tqdm(sorted(files), desc="Processing PDFs"):
        filename = os.path.basename(filepath)
        date = extract_date_from_filename(filename)
        if not date:
            print(f"  Skipping {filename}: couldn't parse date.")
            continue

        text = extract_text_from_pdf(filepath)
        freq = count_keywords(text, keywords)
        sentiments, snippets = keyword_sentiment(text, keywords)

        for kw, snips in snippets.items():
            for s in snips:
                all_snippets[kw].append({"date": date, "snippet": s})

        results.append({"date": date, "filename": filename, **freq, **sentiments})

    df = pd.DataFrame(results).sort_values("date").reset_index(drop=True)
    return df, all_snippets
