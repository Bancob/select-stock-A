"""Configuration for a small-cap A-share strategy using Quantclass data."""
from datetime import date
from pathlib import Path

from multimarket.config import (
    DataSourceConfig,
    ExecutionConfig,
    FactorDefinition,
    FilterDefinition,
    PlatformConfig,
    StrategyConfig,
    TimingConfig,
)


DATA_ROOT = Path(r"D:\quantclass-data")
FACTOR_LIBRARY = Path("multimarket/factors/builtins.py")

platform_config = PlatformConfig(
    market="cn",
    start_date=date(2021, 1, 1),
    end_date=date(2024, 12, 31),
    factor_paths=[FACTOR_LIBRARY],
    data_sources=[
        DataSourceConfig(
            name="daily_bar",
            path=DATA_ROOT / "stock-trading-data",
            loader="quantcsv",
            metadata={
                "pattern": "*.csv",
                "prefixes": ["sh", "sz"],
            },
        ),
    ],
    strategy=StrategyConfig(
        name="SmallCapAlpha",
        hold_period="1M",
        select_count=30,
        factors=[
            FactorDefinition(name="FloatMarketCap", ascending=False, weight=0.7),
            FactorDefinition(name="Momentum", ascending=False, params={"window": 60}, weight=0.3),
        ],
        filters=[
            FilterDefinition(name="close", params=None, rule="val:>=3"),
        ],
    ),
    timing=None,
    execution=ExecutionConfig(
        initial_cash=10_000_000,
        commission_rate=0.0003,
        stamp_duty=0.001,
        max_weight=0.05,
    ),
)
