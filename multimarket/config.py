"""Configuration models for the multi-market backtrader platform."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from .markets.profiles import MARKET_PROFILES, MarketProfile


@dataclass
class DataSourceConfig:
    """Definition of an input dataset.

    Attributes
    ----------
    name:
        Logical identifier used by the platform (e.g. "daily_bar", "financial").
    path:
        Root folder or database connection string that stores the dataset.
    loader:
        Loader alias registered in ``data.loader`` ("auto", "csv", "parquet", "clickhouse" etc.).
    calendar:
        Optional trading calendar identifier; defaults to the active market calendar.
    frequency:
        Data frequency string compatible with pandas offsets ("1d", "60min" ...).
    columns:
        Expected columns in the dataset; used for validation during ingestion.
    metadata:
        Extra loader-specific configuration (e.g. file pattern, SQL, credentials key).
    """

    name: str
    path: Union[str, Path]
    loader: str = "auto"
    calendar: Optional[str] = None
    frequency: str = "1d"
    columns: Sequence[str] = field(default_factory=tuple)
    metadata: Dict[str, Union[str, int, float]] = field(default_factory=dict)

    def as_path(self) -> Path:
        """Return the dataset path as a :class:`Path` instance."""

        return Path(self.path)


@dataclass
class FactorDefinition:
    """User-defined factor specification."""

    name: str
    ascending: bool = False
    params: Optional[Union[Tuple, Dict]] = None
    weight: float = 1.0


@dataclass
class FilterDefinition:
    """Factor filter rule applied before ranking."""

    name: str
    params: Optional[Union[int, float, Tuple, Sequence, Dict]] = None
    rule: str = "val:>=0"
    use_rank: bool = False


@dataclass
class StrategyConfig:
    """Selection and portfolio construction configuration."""

    name: str
    hold_period: str = "1M"
    select_count: Union[int, float] = 10
    factors: Sequence[FactorDefinition] = field(default_factory=tuple)
    filters: Sequence[FilterDefinition] = field(default_factory=tuple)
    universe: Optional[Sequence[str]] = None
    rebalance_offset_days: int = 0


@dataclass
class TimingConfig:
    """Portfolio-level timing overlay configuration."""

    name: Optional[str] = None
    params: Sequence[Union[int, float]] = field(default_factory=tuple)
    data_source: str = "equity_curve"


@dataclass
class ExecutionConfig:
    """Trading cost and slippage parameters."""

    initial_cash: float = 1_000_000.0
    commission_rate: float = 0.00012
    stamp_duty: float = 0.001
    slippage: float = 0.0
    cash_target: float = 0.0
    max_weight: float = 0.1
    allow_short: bool = False


@dataclass
class PlatformConfig:
    """Top-level configuration object consumed by the runner."""

    market: str
    strategy: StrategyConfig
    data_sources: Sequence[DataSourceConfig]
    timing: Optional[TimingConfig] = None
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    factor_paths: Sequence[Union[str, Path]] = field(default_factory=tuple)
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    def market_profile(self) -> MarketProfile:
        """Return the :class:`MarketProfile` associated with the market code."""

        code = self.market.lower()
        if code not in MARKET_PROFILES:
            raise KeyError(f"Unknown market code '{self.market}'. Available: {list(MARKET_PROFILES)}")
        return MARKET_PROFILES[code]

    def data_map(self) -> Dict[str, DataSourceConfig]:
        """Dictionary access to data sources keyed by their name."""

        return {src.name: src for src in self.data_sources}


SCHEMA_GUIDE: Dict[str, Dict[str, Union[str, Sequence[str]]]] = {
    "daily_bar": {
        "description": "OHLCV plus adjustment factors; one row per instrument per session.",
        "required_columns": [
            "ts_code",
            "trade_date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "adj_factor",
        ],
        "file_layout": "Partition by market/year/month inside the configured path.",
        "example_path": ".../daily_bar/US/2024/daily_bar_202401.csv",
    },
    "minute_bar": {
        "description": "Intraday OHLCV data if short term strategies are needed.",
        "required_columns": [
            "ts_code",
            "trade_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ],
        "file_layout": "Partition by market/symbol/date.",
    },
    "financial": {
        "description": "Company level financial statement snapshots.",
        "required_columns": [
            "ts_code",
            "report_date",
            "fiscal_period",
            "field",
            "value",
            "currency",
        ],
        "notes": "Wide-to-long format recommended for flexibility; pivot when computing factors.",
    },
    "macro": {
        "description": "Macro series indexed by release date.",
        "required_columns": [
            "indicator",
            "release_time",
            "value",
            "region",
        ],
        "notes": "Support multiple regions for cross-market macro overlay.",
    },
}
