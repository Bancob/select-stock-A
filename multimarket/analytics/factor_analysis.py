"""Factor analysis utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import matplotlib.pyplot as plt
import pandas as pd


@dataclass
class BinningResult:
    bins: pd.IntervalIndex
    data: pd.DataFrame


def factor_binning(
    factor: pd.Series,
    forward_return: pd.Series,
    bins: int = 10,
    method: Literal["quantile", "equal"] = "quantile",
) -> BinningResult:
    """Bin factor values and aggregate forward returns."""

    aligned = pd.concat([factor.rename("factor"), forward_return.rename("return")], axis=1).dropna()
    if aligned.empty:
        raise ValueError("No overlapping data between factor and forward_return")
    if method == "quantile":
        labels = pd.qcut(aligned["factor"], q=bins, duplicates="drop")
    else:
        labels = pd.cut(aligned["factor"], bins=bins)
    grouped = aligned.groupby(labels)["return"].agg(["mean", "median", "count"])
    grouped["ic"] = aligned.groupby(labels).apply(
        lambda frame: frame["factor"].corr(frame["return"], method="spearman")
    )
    return BinningResult(bins=grouped.index, data=grouped)


def plot_binning(result: BinningResult, ax: Optional[plt.Axes] = None) -> plt.Axes:
    """Visualize binning outcome."""

    ax = ax or plt.gca()
    result.data["mean"].plot(kind="bar", ax=ax, color="steelblue")
    ax.set_title("Factor Binning Mean Return")
    ax.set_ylabel("Return")
    return ax


def cumulative_return_view(equity_curve: pd.Series) -> pd.DataFrame:
    """Return a table with cumulative stats for quick diagnostics."""

    df = pd.DataFrame({"equity": equity_curve})
    df["drawdown"] = df["equity"].div(df["equity"].cummax()) - 1
    df["rolling_return_20"] = df["equity"].pct_change(20)
    return df
