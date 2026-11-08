"""Console output: plain English summary and snippet inspection."""

import math


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
average (about six months, as the FOMC meets eight times a
year) to smooth out noise.

Panel 2 (Sentiment): Shows the emotional tone of the
language surrounding each keyword, scored from -1 to +1.
Meetings where a keyword is not mentioned have no score and
appear as gaps, not as zero.

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
        if math.isnan(sent):
            print(f"  {kw:<15} freq: {freq:.2f}/1k words   sentiment: none (not mentioned)")
            continue
        tone = "negative" if sent < -0.05 else "positive" if sent > 0.05 else "neutral"
        print(f"  {kw:<15} freq: {freq:.2f}/1k words   sentiment: {sent:+.3f} ({tone})")
    print()


def export_snippets(hits, keyword, top_n=20, chars=160):
    """
    Print the most extreme sentiment snippets for a keyword. Useful for
    sanity-checking that VADER is picking up on the right context.

    Uses the scores stored on each hit record (the same scores behind the charts);
    the full context of every hit is in output/hits.csv. Console lines show the
    text around the keyword, shortened to `chars` characters.
    """
    rows = hits[hits.keyword == keyword]
    rows = rows.reindex(rows.score.abs().sort_values(ascending=False).index).head(top_n)

    print(f"\n--- Top {len(rows)} most sentiment-charged '{keyword}' snippets ---")
    for r in rows.itertuples():
        words = r.context.split()
        mid = r.words_left   # index of the keyword inside the context
        excerpt = " ".join(words[max(0, mid - 12):mid + 14])
        print(f"  [{r.date.date()}] score={r.score:+.3f}  \"...{excerpt[:chars]}...\"")
