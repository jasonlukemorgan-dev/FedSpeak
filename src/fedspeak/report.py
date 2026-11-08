"""Console output: plain English summary and snippet inspection."""

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


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
