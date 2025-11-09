"""Structured dataset schema helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class DailyBarRecord:
    """Normalized OHLCV bar representation."""

    symbol: str
    trade_date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    adj_factor: float = 1.0


@dataclass(frozen=True)
class FinancialRecord:
    """Company financial metric snapshot."""

    symbol: str
    report_date: datetime
    fiscal_period: str
    field: str
    value: float
    currency: str


@dataclass(frozen=True)
class MacroRecord:
    """Macro-economic indicator observation."""

    indicator: str
    release_time: datetime
    value: float
    region: str
    reference: Optional[str] = None
