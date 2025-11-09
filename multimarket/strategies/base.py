"""Core strategy classes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import backtrader as bt
import pandas as pd

from ..config import ExecutionConfig


@dataclass
class TargetAllocation:
    """Holds the portfolio weights for a specific rebalance date."""

    date: pd.Timestamp
    weights: Dict[str, float]


class MultiMarketStrategy(bt.Strategy):
    """Executes pre-computed target weights on their scheduled dates."""

    params = dict(
        execution=None,
        allocations=(),
        log=False,
    )

    def __init__(self) -> None:
        self.execution: ExecutionConfig = self.p.execution or ExecutionConfig()
        self._allocation_cursor = 0
        self._current_target: Optional[TargetAllocation] = None
        self._allocations = sorted(self.p.allocations, key=lambda item: item.date)
        self._data_by_name = {data._name: data for data in self.datas}

    def next(self) -> None:
        if not self._allocations:
            return
        dt = pd.Timestamp(self.datetime.date(0))
        next_target = self._allocations[self._allocation_cursor]
        if dt < next_target.date:
            return
        if dt > next_target.date:
            while self._allocation_cursor + 1 < len(self._allocations) and dt > next_target.date:
                self._allocation_cursor += 1
                next_target = self._allocations[self._allocation_cursor]
            if dt < next_target.date:
                return
        self._current_target = next_target
        self._rebalance(next_target.weights)
        if self._allocation_cursor + 1 < len(self._allocations):
            self._allocation_cursor += 1

    def _rebalance(self, weights: Dict[str, float]) -> None:
        max_weight = self.execution.max_weight if self.execution.max_weight > 0 else 1.0
        cash_target = self.execution.cash_target
        desired: Dict[str, float] = {}
        for data in self.datas:
            symbol = data._name
            target_weight = weights.get(symbol, 0.0)
            bounded_weight = max(min(target_weight, max_weight), -max_weight)
            if not self.execution.allow_short and bounded_weight <= 0:
                desired[symbol] = 0.0
            else:
                desired[symbol] = bounded_weight
        if self.execution.allow_short:
            scale = 1 - cash_target
        else:
            positive_total = sum(w for w in desired.values() if w > 0)
            scale = (1 - cash_target) / positive_total if positive_total > 0 else 0.0
        for data in self.datas:
            symbol = data._name
            weight = desired.get(symbol, 0.0)
            if not self.execution.allow_short and weight <= 0:
                self.order_target_percent(data=data, target=0.0)
                continue
            target_percent = weight * scale
            self.order_target_percent(data=data, target=target_percent)

    def notify_order(self, order: bt.Order) -> None:
        if not self.p.log:
            return
        if order.status in [order.Submitted, order.Accepted]:
            return
        symbol = order.data._name if order.data else "CASH"
        if order.status == order.Completed:
            direction = "BUY" if order.isbuy() else "SELL"
            self.log(f"{direction} {symbol} size={order.executed.size} price={order.executed.price}")
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f"ORDER FAIL {symbol} status={order.getstatusname()}")

    def notify_trade(self, trade: bt.Trade) -> None:
        if self.p.log and trade.isclosed:
            self.log(
                f"TRADE {trade.data._name} pnl={trade.pnl:.2f} pnl_net={trade.pnlcomm:.2f}"
            )

    def log(self, message: str) -> None:
        dt = bt.num2date(self.datas[0].datetime[0])
        print(f"{dt:%Y-%m-%d} {message}")
