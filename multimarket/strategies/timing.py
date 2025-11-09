"""Timing overlay components."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Sequence

import numpy as np
import pandas as pd


class TimingEngine(ABC):
    """Base class for post-processing equity curves."""

    def __init__(self, params: Sequence[float]) -> None:
        self.params = list(params)

    @abstractmethod
    def compute_signal(self, series: pd.Series) -> pd.Series:
        """Return a signal series in the range [0, 1] indicating exposure."""


class MovingAverageTiming(TimingEngine):
    """Dual moving average filter."""

    def compute_signal(self, series: pd.Series) -> pd.Series:  # type: ignore[override]
        fast, slow = (int(self.params[0]), int(self.params[1])) if len(self.params) >= 2 else (5, 20)
        fast_ma = series.rolling(fast, min_periods=1).mean()
        slow_ma = series.rolling(slow, min_periods=1).mean()
        signal = (fast_ma > slow_ma).astype(float)
        return signal


class BollingerTiming(TimingEngine):
    """Bollinger band exposure controller."""

    def compute_signal(self, series: pd.Series) -> pd.Series:  # type: ignore[override]
        window = int(self.params[0]) if self.params else 20
        std_mult = float(self.params[1]) if len(self.params) > 1 else 2.0
        ma = series.rolling(window, min_periods=1).mean()
        std = series.rolling(window, min_periods=1).std().fillna(0.0)
        upper = ma + std_mult * std
        lower = ma - std_mult * std
        signal = pd.Series(0.0, index=series.index)
        signal[series > ma] = np.clip((series - ma) / (upper - ma + 1e-6), 0.0, 1.0)
        signal[series <= ma] = np.clip((series - lower) / (ma - lower + 1e-6), 0.0, 1.0)
        return signal


class TrendSlopeTiming(TimingEngine):
    """Linear regression slope based exposure."""

    def compute_signal(self, series: pd.Series) -> pd.Series:  # type: ignore[override]
        window = int(self.params[0]) if self.params else 60
        exposure = []
        values = series.values
        for idx in range(len(series)):
            start = max(0, idx - window + 1)
            slice_values = values[start : idx + 1]
            if len(slice_values) < 2:
                exposure.append(0.0)
                continue
            x = np.arange(len(slice_values))
            slope, _ = np.polyfit(x, slice_values, 1)
            exposure.append(float(np.clip(0.5 + slope, 0.0, 1.0)))
        return pd.Series(exposure, index=series.index)


def build_timing_engine(name: Optional[str], params: Sequence[float]) -> Optional[TimingEngine]:
    if not name:
        return None
    lower = name.lower()
    if lower in {"ma", "ma_double"}:
        return MovingAverageTiming(params)
    if lower in {"bollinger", "bb"}:
        return BollingerTiming(params)
    if lower in {"trend", "slope"}:
        return TrendSlopeTiming(params)
    raise KeyError(f"Unknown timing engine '{name}'")
