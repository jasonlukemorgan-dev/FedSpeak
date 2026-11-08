import pdfplumber
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re
import os
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from collections import defaultdict
from tqdm import tqdm

# --- Configuration ---
PDF_DIR = "D:\\FOMC_Minutes"
KEYWORDS = ["uncertainty", "inflation", "employment", "recession", "tightening"]
CONTEXT_WINDOW = 75       # words on each side of keyword to extract for sentiment
OUTPUT_CSV = "fomc_analysis.csv"

# --- Date Parser ---
def extract_date_from_filename(filename):
    patterns = [
        r'(\d{4})(\d{2})(\d{2})',
        r'(\d{4})-(\d{2})-(\d{2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            y, m, d = match.groups()
            return pd.Timestamp(f"{y}-{m}-{d}")
    return None

# --- PDF Extraction ---
def extract_text_from_pdf(filepath):
    text = ""
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + " "
    return text

# --- Keyword Frequency (normalized) ---
def count_keywords(text, keywords):
    lower_text = text.lower()
    words = lower_text.split()
    word_count = len(words)
    counts = {}
    for kw in keywords:
        pattern = rf'\b{re.escape(kw.lower())}\b'
        raw = len(re.findall(pattern, lower_text))
        counts[kw] = (raw / word_count) * 1000 if word_count > 0 else 0
        counts[f"{kw}_raw"] = raw
    return counts

# --- Sentiment Around Keywords ---
def keyword_sentiment(text, keywords, window=CONTEXT_WINDOW):
    """
    For each keyword, find every occurrence, extract `window` words of context
    on each side, run VADER sentiment on that snippet, and average the scores.
    Returns a dict of {keyword: avg_compound_score}.
    """
    analyzer = SentimentIntensityAnalyzer()
    words = text.split()
    sentiment_scores = defaultdict(list)
    snippet_log = defaultdict(list)

    for i, word in enumerate(words):
        clean_word = re.sub(r'[^a-z]', '', word.lower())
        for kw in keywords:
            if clean_word == kw.lower():
                start = max(0, i - window)
                end = min(len(words), i + window + 1)
                snippet = " ".join(words[start:end])
                score = analyzer.polarity_scores(snippet)["compound"]
                sentiment_scores[kw].append(score)
                snippet_log[kw].append(snippet[:200])

    avg_sentiments = {}
    for kw in keywords:
        scores = sentiment_scores[kw]
        avg_sentiments[f"{kw}_sentiment"] = sum(scores) / len(scores) if scores else 0
        avg_sentiments[f"{kw}_sentiment_n"] = len(scores)

    return avg_sentiments, dict(snippet_log)

# --- Main Processing Loop ---
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

# --- Interactive Plotly Dashboard ---
def build_dashboard(df, keywords):
    colors = [
        "#E63946", "#457B9D", "#2A9D8F", "#E9C46A", "#F4A261",
        "#A8DADC", "#6A4C93", "#1D3557"
    ]

    # Add 4-period rolling averages
    for kw in keywords:
        df[f"{kw}_roll"] = df[kw].rolling(4, min_periods=1).mean()
        df[f"{kw}_sentiment_roll"] = df[f"{kw}_sentiment"].rolling(4, min_periods=1).mean()

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.12,   # increased from 0.06 so year labels do not overlap subplot titles
        subplot_titles=(
            "📈 Keyword Frequency (per 1,000 words)",
            "🎭 Sentiment Around Keywords (VADER compound score, -1 to +1)",
            "🔗 Frequency vs. Sentiment Scatter (select keyword from legend)"
        ),
        row_heights=[0.38, 0.38, 0.24]
    )

    for i, kw in enumerate(keywords):
        color = colors[i % len(colors)]

        # --- Row 1: Frequency ---
        fig.add_trace(go.Scatter(
            x=df["date"], y=df[kw],
            mode="lines+markers",
            name=kw,
            line=dict(color=color, width=1.5, dash="dot"),
            marker=dict(size=5),
            opacity=0.5,
            legendgroup=kw,
            showlegend=True,
            hovertemplate=f"<b>{kw}</b><br>Date: %{{x|%Y-%m-%d}}<br>Freq: %{{y:.2f}} per 1k words<extra></extra>"
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=df["date"], y=df[f"{kw}_roll"],
            mode="lines",
            name=f"{kw} (4-mtg avg)",
            line=dict(color=color, width=2.5),
            legendgroup=kw,
            showlegend=False,
            hovertemplate=f"<b>{kw} rolling avg</b><br>Date: %{{x|%Y-%m-%d}}<br>Freq: %{{y:.2f}}<extra></extra>"
        ), row=1, col=1)

        # --- Row 2: Sentiment ---
        fig.add_trace(go.Scatter(
            x=df["date"], y=df[f"{kw}_sentiment"],
            mode="lines+markers",
            name=kw,
            line=dict(color=color, width=1.5, dash="dot"),
            marker=dict(size=5),
            opacity=0.5,
            legendgroup=kw,
            showlegend=False,
            hovertemplate=f"<b>{kw} sentiment</b><br>Date: %{{x|%Y-%m-%d}}<br>Score: %{{y:.3f}}<extra></extra>"
        ), row=2, col=1)

        fig.add_trace(go.Scatter(
            x=df["date"], y=df[f"{kw}_sentiment_roll"],
            mode="lines",
            name=f"{kw} sentiment (4-mtg avg)",
            line=dict(color=color, width=2.5),
            legendgroup=kw,
            showlegend=False,
            hovertemplate=f"<b>{kw} sentiment rolling avg</b><br>%{{y:.3f}}<extra></extra>"
        ), row=2, col=1)

        # --- Row 3: Scatter freq vs sentiment ---
        fig.add_trace(go.Scatter(
            x=df[kw], y=df[f"{kw}_sentiment"],
            mode="markers",
            name=kw,
            marker=dict(
                color=color, size=8, opacity=0.75,
                line=dict(width=1, color="white")
            ),
            text=df["date"].dt.strftime("%Y-%m-%d"),
            legendgroup=kw,
            showlegend=False,
            hovertemplate=f"<b>{kw}</b><br>Date: %{{text}}<br>Freq: %{{x:.2f}}<br>Sentiment: %{{y:.3f}}<extra></extra>"
        ), row=3, col=1)

    # Zero line for sentiment
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)", row=2, col=1)

    # Shade COVID recession (no annotation text, to keep charts clean)
    for row in [1, 2]:
        fig.add_vrect(
            x0="2020-02-01", x1="2020-04-30",
            fillcolor="rgba(255,100,100,0.1)",
            line_width=0,
            row=row, col=1
        )

    fig.update_layout(
        title=dict(
            text="FOMC Minutes: Keyword Frequency & Sentiment Analysis",
            font=dict(size=20, color="white"),
            x=0.5
        ),
        template="plotly_dark",
        height=1100,             # increased from 950 to compensate for added spacing
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            font=dict(size=11)
        ),
        hovermode="x unified",
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        font=dict(color="#c9d1d9")
    )

    fig.update_yaxes(gridcolor="rgba(255,255,255,0.07)")
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.07)")

    # Year labels on panels 1 and 2
    fig.update_xaxes(
        tickformat="%Y",
        dtick="M12",
        tickangle=-45,
        showticklabels=True,
        row=1, col=1
    )

    fig.update_xaxes(
        tickformat="%Y",
        dtick="M12",
        tickangle=-45,
        showticklabels=True,
        row=2, col=1
    )

    # Row 3 axis labels
    fig.update_xaxes(title_text="Frequency (per 1k words)", row=3, col=1)
    fig.update_yaxes(title_text="Sentiment Score", row=3, col=1)

    fig.write_html("fomc_dashboard.html")
    print("Dashboard saved to fomc_dashboard.html")
    fig.show()

# --- Plain English Summary ---
def print_summary(df, keywords):
    print("=" * 60)
    print("FEDSPEAK: READING YOUR RESULTS")
    print("=" * 60)

    print("""
HOW TO READ THE CHARTS
----------------------
Panel 1 (Frequency): Shows how often each keyword appears
per 1,000 words. A rising line means the Fed is talking
about that topic more. The bold line is a 4-meeting rolling
average (about 1 year) to smooth out noise.

Panel 2 (Sentiment): Shows the emotional tone of the
language surrounding each keyword, scored from -1 to +1.

  +1.0  Very positive  ("strong", "resilient", "confident")
   0.0  Neutral        (purely factual, no emotional charge)
  -1.0  Very negative  ("risk", "concern", "deteriorating")

The Fed rarely hits extremes. Scores around -0.2 to -0.4
are already meaningfully negative for institutional language.
A keyword crossing below zero and staying there is a signal
worth paying attention to.

Panel 3 (Scatter): Each dot is one FOMC meeting. Its
position shows the relationship between how often a word
appeared (x-axis) and the tone around it (y-axis). Dots
clustering in the bottom-right mean: mentioned frequently
AND in a negative context, which is often a sign of concern.

The faint red shading marks the COVID recession (Feb-Apr 2020).
""")

    print("SNAPSHOT: MOST RECENT MEETING")
    print("-" * 40)
    latest = df.iloc[-1]
    for kw in keywords:
        freq = latest[kw]
        sent = latest[f"{kw}_sentiment"]
        tone = "negative" if sent < -0.05 else "positive" if sent > 0.05 else "neutral"
        print(f"  {kw:<15} freq: {freq:.2f}/1k words   sentiment: {sent:+.3f} ({tone})")
    print()

# --- Export Snippets for Inspection ---
def export_snippets(all_snippets, keyword, top_n=20):
    """
    Print the most extreme sentiment snippets for a keyword. Useful for
    sanity-checking that VADER is picking up on the right context.
    """
    analyzer = SentimentIntensityAnalyzer()
    records = all_snippets.get(keyword, [])
    scored = []
    for r in records:
        score = analyzer.polarity_scores(r["snippet"])["compound"]
        scored.append({**r, "score": score})
    scored.sort(key=lambda x: abs(x["score"]), reverse=True)

    print(f"\n--- Top {top_n} most sentiment-charged '{keyword}' snippets ---")
    for rec in scored[:top_n]:
        print(f"  [{rec['date'].date()}] score={rec['score']:+.3f}  \"{rec['snippet'][:120]}...\"")

# --- Run ---
if __name__ == "__main__":
    df, all_snippets = process_pdfs(PDF_DIR, KEYWORDS)

    if df.empty:
        print("No data to process. Exiting.")
    else:
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"Saved to {OUTPUT_CSV}\n")
        print(df[["date"] + KEYWORDS + [f"{kw}_sentiment" for kw in KEYWORDS]].to_string(index=False))

        build_dashboard(df, KEYWORDS)
        print_summary(df, KEYWORDS)

        # Inspect top snippets for a keyword of interest
        export_snippets(all_snippets, "uncertainty", top_n=10)
