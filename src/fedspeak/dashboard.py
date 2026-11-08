"""Interactive Plotly dashboard: frequency, sentiment, and frequency vs sentiment."""

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from fedspeak.config import DASHBOARD_HTML


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

    fig.write_html(DASHBOARD_HTML)
    print(f"Dashboard saved to {DASHBOARD_HTML}")
    fig.show()
