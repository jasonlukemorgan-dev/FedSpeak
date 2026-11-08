"""Verification checks (docs/plan.md section 1).

compare_sources: for every meeting with both a PDF and an HTML version, extract both
and compare word counts, keyword counts, PDF line-break hyphenation, and the words
that appear in one version but not the other. The HTML is an independent rendering
of the same minutes, so differences point to extraction problems in one of them.
"""

import re
from collections import Counter
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from fedspeak.config import KEYWORDS, MANIFEST_CSV, PROJECT_ROOT
from fedspeak.extract import extract_text_from_html, extract_text_from_pdf
from fedspeak.match import count_keywords

VERIFY_DIR = PROJECT_ROOT / "output" / "verify"

# A word split across a line break in the PDF: "uncer-\ntainty".
LINE_BREAK_HYPHEN = re.compile(r"[A-Za-z]-\n[a-z]")
TOKEN = re.compile(r"[a-z]+(?:'[a-z]+)?")


def _tokens(text):
    return Counter(TOKEN.findall(text.lower()))


def compare_one(pdf_text, html_text, keywords):
    pdf_counts = count_keywords(pdf_text, keywords)
    html_counts = count_keywords(html_text, keywords)
    pdf_tokens, html_tokens = _tokens(pdf_text), _tokens(html_text)
    only_pdf = pdf_tokens - html_tokens
    only_html = html_tokens - pdf_tokens
    row = {
        "words_pdf": len(pdf_text.split()),
        "words_html": len(html_text.split()),
        "pdf_line_break_hyphens": len(LINE_BREAK_HYPHEN.findall(pdf_text)),
        "tokens_only_in_pdf": sum(only_pdf.values()),
        "tokens_only_in_html": sum(only_html.values()),
        "top_only_in_pdf": " ".join(f"{w}:{n}" for w, n in only_pdf.most_common(12)),
        "top_only_in_html": " ".join(f"{w}:{n}" for w, n in only_html.most_common(12)),
    }
    for kw in keywords:
        row[f"{kw}_pdf"] = pdf_counts[f"{kw}_raw"]
        row[f"{kw}_html"] = html_counts[f"{kw}_raw"]
    row["keyword_mismatches"] = sum(row[f"{kw}_pdf"] != row[f"{kw}_html"] for kw in keywords)
    return row


def compare_sources(keywords=KEYWORDS, manifest_path=MANIFEST_CSV, out_dir=VERIFY_DIR, save_text=True):
    manifest = pd.read_csv(manifest_path, dtype=str).fillna("")
    both = manifest[(manifest.pdf_path != "") & (manifest.html_path != "")]
    out_dir = Path(out_dir)
    text_dir = out_dir / "text"
    if save_text:
        text_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for rec in tqdm(both.itertuples(), total=len(both), desc="Comparing PDF and HTML"):
        pdf_text = extract_text_from_pdf(PROJECT_ROOT / rec.pdf_path)
        html_text = extract_text_from_html(PROJECT_ROOT / rec.html_path)
        if save_text:
            stem = rec.meeting_date.replace("-", "")
            (text_dir / f"{stem}_pdf.txt").write_text(pdf_text, encoding="utf-8")
            (text_dir / f"{stem}_html.txt").write_text(html_text, encoding="utf-8")
        rows.append({"meeting_date": rec.meeting_date, **compare_one(pdf_text, html_text, keywords)})

    df = pd.DataFrame(rows)
    df["word_ratio_pdf_to_html"] = (df.words_pdf / df.words_html).round(3)
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "pdf_vs_html.csv", index=False)
    return df


def print_comparison_summary(df, keywords=KEYWORDS):
    print(f"\nMeetings compared: {len(df)}")
    print(f"Word count ratio PDF/HTML: median {df.word_ratio_pdf_to_html.median():.3f}, "
          f"range {df.word_ratio_pdf_to_html.min():.3f} to {df.word_ratio_pdf_to_html.max():.3f}")
    print(f"PDF line-break hyphens: {df.pdf_line_break_hyphens.sum()} total, "
          f"median {df.pdf_line_break_hyphens.median():.0f} per meeting")
    print("Keyword totals (PDF vs HTML):")
    for kw in keywords:
        p, h = df[f"{kw}_pdf"].sum(), df[f"{kw}_html"].sum()
        n = (df[f"{kw}_pdf"] != df[f"{kw}_html"]).sum()
        print(f"  {kw:<15} PDF {p:>5}  HTML {h:>5}  meetings that differ: {n}")
