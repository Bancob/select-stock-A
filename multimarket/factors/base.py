"""Factor computation interfaces."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

import pandas as pd

from ..markets.profiles import MarketProfile


@dataclass
class FactorContext:
    """Data bundle provided to factor instances."""

    pricing: Dict[str, pd.DataFrame]
    financial: Optional[pd.DataFrame] = None
    macro: Optional[pd.DataFrame] = None
    universe: Optional[Sequence[str]] = None
    market: Optional[MarketProfile] = None


class BaseFactor(ABC):
    """Abstract base class for factor computations."""

    name: str = "base"

    def __init__(self, params: Optional[dict] = None) -> None:
        self.params = params or {}

    @abstractmethod
    def compute(self, ctx: FactorContext) -> pd.Series:
        """Return factor values indexed by instrument code."""

    def post_process(self, series: pd.Series) -> pd.Series:
        return series


class FactorEngine:
    """Combine multiple factors and produce a unified ranking."""

    def __init__(
        self,
        factors: Sequence[BaseFactor],
        names: Sequence[str],
        weights: Optional[Sequence[float]] = None,
        ascending: Optional[Sequence[bool]] = None,
    ) -> None:
        self.factors = list(factors)
        self.names = list(names)
        if weights is None:
            weights = [1.0] * len(self.factors)
        if ascending is None:
            ascending = [False] * len(self.factors)
        if not (len(weights) == len(self.factors) == len(ascending) == len(self.names)):
            raise ValueError("factors, weights, ascending, names must share length")
        self.weights = list(weights)
        self.ascending = list(ascending)

    def compute(self, ctx: FactorContext) -> pd.Series:
        composite, _ = self.compute_with_details(ctx)
        return composite

    def compute_with_details(self, ctx: FactorContext) -> Tuple[pd.Series, Dict[str, pd.Series]]:
        if not self.factors:
            raise RuntimeError("No factors registered")
        prepared = []
        details: Dict[str, pd.Series] = {}
        total_weight = sum(abs(weight) for weight in self.weights) or 1.0
        for name, factor, weight, asc in zip(self.names, self.factors, self.weights, self.ascending):
            values = factor.compute(ctx)
            values = factor.post_process(values).dropna()
            ranked = values.rank(method="dense", ascending=asc, pct=True)
            prepared.append(ranked * weight)
            details[name] = values
        composite = sum(prepared) / total_weight
        return composite.sort_values(ascending=False), details
