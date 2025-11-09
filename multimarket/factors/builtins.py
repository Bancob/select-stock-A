"""Built-in example factors for the multi-market platform."""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

try:  # pragma: no cover
    from .base import BaseFactor, FactorContext
except ImportError:  # pragma: no cover - module loaded as standalone
    from multimarket.factors.base import BaseFactor, FactorContext  # type: ignore


class Momentum(BaseFactor):
    """Price momentum measured by trailing return."""

    name = "Momentum"

    def compute(self, ctx: FactorContext) -> pd.Series:  # type: ignore[override]
        window = int(self.params.get("window", 60))
        closes = ctx.pricing.get("close")
        if closes is None or len(closes) <= window:
            return pd.Series(dtype=float)
        pct = closes.pct_change(periods=window, fill_method=None).iloc[-1]
        return pct.replace([np.inf, -np.inf], np.nan)


class AverageTurnover(BaseFactor):
    """Average turnover (成交额) over a trailing window."""

    name = "AverageTurnover"

    def compute(self, ctx: FactorContext) -> pd.Series:  # type: ignore[override]
        amounts = ctx.pricing.get("amount")
        if amounts is None:
            return pd.Series(dtype=float)
        window = int(self.params.get("window", 20))
        if len(amounts) < window:
            return amounts.iloc[-1]
        return amounts.rolling(window).mean().iloc[-1]


class Volatility(BaseFactor):
    """Rolling standard deviation of returns."""

    name = "Volatility"

    def compute(self, ctx: FactorContext) -> pd.Series:  # type: ignore[override]
        closes = ctx.pricing.get("close")
        if closes is None:
            return pd.Series(dtype=float)
        window = int(self.params.get("window", 30))
        if len(closes) <= window:
            return pd.Series(dtype=float)
        returns = closes.pct_change(fill_method=None).iloc[-window:]
        return returns.std()

    def post_process(self, series: pd.Series) -> pd.Series:  # type: ignore[override]
        return series


class LowVolatility(BaseFactor):
    """Inverse volatility as a defensive factor."""

    name = "LowVolatility"

    def compute(self, ctx: FactorContext) -> pd.Series:  # type: ignore[override]
        vol = Volatility(self.params).compute(ctx)
        return 1 / (vol + 1e-9)


class FloatMarketCap(BaseFactor):
    """Negative float market value for small-cap preference."""

    name = "FloatMarketCap"

    def compute(self, ctx: FactorContext) -> pd.Series:  # type: ignore[override]
        floats = ctx.pricing.get("float_mv")
        if floats is None or floats.empty:
            return pd.Series(dtype=float)
        latest = floats.iloc[-1]
        return (-latest).replace([np.inf, -np.inf], np.nan)
