"""Interactive Plotly dashboard: frequency, sentiment, and frequency vs sentiment.

When the results include the stance model's whole-document index (doc_stance_index),
a fourth panel shows it on the shared timeline, and the figure grows to fit.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from fedspeak.config import DASHBOARD_HTML, DASHBOARD_SENTIMENT

MEASURES = {
    "vader": ("_sentiment", "VADER with Fed vocabulary", "is the Fed lexicon set?"),
    "lm": ("_lm_tone", "Loughran-McDonald net tone", "is the dictionary installed?"),
    "stance": ("_stance", "FOMC-RoBERTa stance, hawkish minus dovish", "is STANCE_MODEL set and the model reachable?"),
}
INDEX_COLOR = "#E9C46A"


def build_dashboard(df, keywords, measure=DASHBOARD_SENTIMENT, show=True):
    if measure not in MEASURES:
        raise ValueError(f"DASHBOARD_SENTIMENT must be one of {list(MEASURES)}, not {measure!r}")
    suffix, measure_label, missing_hint = MEASURES[measure]
    if f"{keywords[0]}{suffix}" not in df.columns:
        raise ValueError(f"No {measure_label} columns in the results; {missing_hint}")
    with_index = "doc_stance_index" in df.columns
    scatter_row = 4 if with_index else 3
    colors = [
        "#E63946", "#457B9D", "#2A9D8F", "#E9C46A", "#F4A261",
        "#A8DADC", "#6A4C93", "#1D3557"
    ]

    # Add 4-period rolling averages
    for kw in keywords:
        df[f"{kw}_roll"] = df[kw].rolling(4, min_periods=1).mean()
        df[f"{kw}{suffix}_roll"] = df[f"{kw}{suffix}"].rolling(4, min_periods=1).mean()

    titles = [
        "📈 Keyword Frequency (per 1,000 words)",
        f"🎭 Sentiment of Keyword Sentences ({measure_label}, -1 to +1)",
        "🔗 Frequency vs. Sentiment Scatter (select keyword from legend)",
    ]
    if with_index:
        titles.insert(2, "🦅 Whole-Meeting Stance Index ((hawkish - dovish sentences) / all, FOMC-RoBERTa)")
    fig = make_subplots(
        rows=len(titles), cols=1,
        shared_xaxes=True,
        # 3 panels: 0.12, increased from 0.06 so year labels do not overlap subplot titles.
        # 4 panels: 0.09 of a taller figure keeps about the same gap in pixels.
        vertical_spacing=0.09 if with_index else 0.12,
        subplot_titles=titles,
        row_heights=[0.29, 0.29, 0.21, 0.21] if with_index else [0.38, 0.38, 0.24]
    )

    if with_index:
        index_roll = df["doc_stance_index"].rolling(4, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["doc_stance_index"],
            mode="lines+markers",
            name="stance index",
            line=dict(color=INDEX_COLOR, width=1.5, dash="dot"),
            marker=dict(size=5),
            opacity=0.5,
            showlegend=False,
            hovertemplate="<b>Stance index</b><br>Date: %{x|%Y-%m-%d}<br>Index: %{y:.3f}<extra></extra>"
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=df["date"], y=index_roll,
            mode="lines",
            name="stance index (4-mtg avg)",
            line=dict(color=INDEX_COLOR, width=2.5),
            showlegend=False,
            hovertemplate="<b>Stance index rolling avg</b><br>%{y:.3f}<extra></extra>"
        ), row=3, col=1)
        fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)", row=3, col=1)

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
            x=df["date"], y=df[f"{kw}{suffix}"],
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
            x=df["date"], y=df[f"{kw}{suffix}_roll"],
            mode="lines",
            name=f"{kw} sentiment (4-mtg avg)",
            line=dict(color=color, width=2.5),
            legendgroup=kw,
            showlegend=False,
            hovertemplate=f"<b>{kw} sentiment rolling avg</b><br>%{{y:.3f}}<extra></extra>"
        ), row=2, col=1)

        # --- Row 3: Scatter freq vs sentiment ---
        fig.add_trace(go.Scatter(
            x=df[kw], y=df[f"{kw}{suffix}"],
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
        ), row=scatter_row, col=1)

    # Zero line for sentiment
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)", row=2, col=1)

    timeline_rows = [1, 2, 3] if with_index else [1, 2]

    # Shade COVID recession (no annotation text, to keep charts clean)
    for row in timeline_rows:
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
        height=1450 if with_index else 1100,   # 1100 was increased from 950 to compensate for added spacing
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

    # Year labels on the timeline panels
    for row in timeline_rows:
        fig.update_xaxes(
            tickformat="%Y",
            dtick="M12",
            tickangle=-45,
            showticklabels=True,
            row=row, col=1
        )

    # Scatter axis labels
    fig.update_xaxes(title_text="Frequency (per 1k words)", row=scatter_row, col=1)
    fig.update_yaxes(title_text="Sentiment Score", row=scatter_row, col=1)

    DASHBOARD_HTML.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(DASHBOARD_HTML)
    print(f"Dashboard saved to {DASHBOARD_HTML}")
    if show:
        fig.show()
    return fig
