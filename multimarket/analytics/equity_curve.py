"""Equity curve visualization utilities."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import plotly.graph_objects as go


def render_equity_html(
    base_curve: pd.Series,
    timed_curve: pd.Series,
    output_path: Path,
    title: str = "再择时资金曲线对比",
    base_label: str = "原始资金曲线",
    timed_label: str = "再择时资金曲线",
) -> Path:
    """Render an interactive HTML containing equity and drawdown curves."""

    if base_curve.empty and timed_curve.empty:
        raise ValueError("At least one equity curve is required")

    df = pd.DataFrame()
    if not base_curve.empty:
        df[base_label] = base_curve
    if not timed_curve.empty:
        df[timed_label] = timed_curve
    df.index.name = "date"

    drawdowns = df.div(df.cummax()).fillna(1.0) - 1

    fig = go.Figure()
    for column in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df[column],
                mode="lines",
                name=column,
                hovertemplate="%{x|%Y-%m-%d}<br>%{y:.4f}<extra></extra>",
            )
        )

    for column in drawdowns.columns:
        fig.add_trace(
            go.Scatter(
                x=drawdowns.index,
                y=drawdowns[column],
                mode="lines",
                name=f"{column}回撤",
                yaxis="y2",
                hovertemplate="%{x|%Y-%m-%d}<br>%{y:.2%}<extra></extra>",
                line=dict(dash="dot"),
            )
        )

    fig.update_layout(
        title=title,
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(title="净值", tickformat=".2f"),
        yaxis2=dict(title="回撤", overlaying="y", side="right", tickformat=".0%"),
        margin=dict(l=60, r=60, t=60, b=40),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output_path), include_plotlyjs="cdn")
    return output_path
