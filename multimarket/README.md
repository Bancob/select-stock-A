# Multi-Market Backtrader Platform

This package wraps a reusable backtrader toolkit that adapts to A-shares, US, Hong Kong, and crypto markets. It provides:

- Market-aware configuration for trading hours, fees, and settlement.
- Dataset ingestion utilities with explicit schema guides for OHLCV, financial, and macro data.
- Factor registry compatible with existing factor libraries (extend ``BaseFactor``).
- Strategy runner that computes cross-sectional rankings, applies filters, and submits target allocations to backtrader.
- Timing overlay engines (dual moving average, Bollinger, trend slope).
- Analytics helpers for factor binning and trade inspection.

## Quick Start

1. Prepare datasets following the schemas described in ``multimarket.config.SCHEMA_GUIDE``.
2. Update ``examples/multimarket_config.py`` with your data paths, market, factors, filters, and timing choices.
3. Implement or wrap factors under ``Òò×Ó¿â`` (or any folder listed in ``factor_paths``) by subclassing ``BaseFactor``.
4. Run ``python examples/run_multimarket.py`` to execute the backtest.

## Factor Naming

- Factor definitions reference the class name inside the factor library.
- Filters can reference factor names (for factor-based constraints) or data fields (``close``, ``volume`` etc.).
- Composite score filters use ``FilterDefinition(name="composite", rule="pct:<=0.3")`` to keep the top 30% ranking results.

## Timing Overlay

Provide a data source descriptor such as ``pricing:close:SPY`` or ``macro:US_CPI``. The timing engine rescales portfolio weights between 0 and 1 based on the selected rule.

## Analytics

Use ``multimarket.analytics.factor_analysis.factor_binning`` for factor IC checks and ``multimarket.analytics.trade_viewer`` utilities to inspect trade logs after the backtest completes.
