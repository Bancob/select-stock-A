"""Tools for visualizing trades and holdings."""
from __future__ import annotations

from typing import Iterable, List

import pandas as pd


def trades_to_frame(trades: Iterable) -> pd.DataFrame:
    """Convert backtrader trade iterables into a pandas DataFrame."""

    records: List[dict] = []
    for trade in trades:
        record = {
            "data": trade.data._name,
            "size": trade.size,
            "price": trade.price,
            "value": trade.value,
            "pnl": trade.pnl,
            "pnlcomm": trade.pnlcomm,
            "bar_open": trade.baropen,
            "bar_close": trade.barclose,
        }
        records.append(record)
    return pd.DataFrame.from_records(records)


def position_snapshot(strategy) -> pd.DataFrame:
    """Take a snapshot of current positions in a strategy."""

    rows: List[dict] = []
    for data in strategy.datas:
        pos = strategy.getposition(data)
        rows.append(
            {
                "asset": data._name,
                "size": pos.size,
                "price": data.close[0],
                "value": pos.size * data.close[0],
            }
        )
    return pd.DataFrame(rows)


def trade_summary(trade_frame: pd.DataFrame) -> pd.Series:
    """Return aggregate statistics for a trade DataFrame."""

    if trade_frame.empty:
        return pd.Series()
    return pd.Series(
        {
            "total_trades": len(trade_frame),
            "win_rate": (trade_frame["pnl"] > 0).mean(),
            "avg_pnl": trade_frame["pnl"].mean(),
            "max_drawdown_trade": trade_frame["pnl"].min(),
        }
    )
