"""High level orchestration for multi-market backtests."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import backtrader as bt
import pandas as pd

from .config import (
    ExecutionConfig,
    FilterDefinition,
    PlatformConfig,
)
from .data.loader import GenericPandasData, REGISTRY as DATA_LOADERS
from .factors.base import FactorContext, FactorEngine
from .factors.registry import FactorRegistry, GLOBAL_FACTOR_REGISTRY
from .markets.profiles import MarketProfile
from .strategies.base import MultiMarketStrategy, TargetAllocation
from .strategies.timing import build_timing_engine
from .utils.calendar import rebalance_schedule, trading_sessions


@dataclass
class DataBundle:
    pricing: Dict[str, pd.DataFrame]
    financial: Optional[pd.DataFrame]
    macro: Optional[pd.DataFrame]

    def slice(self, field: str, end_date: pd.Timestamp) -> pd.Series:
        frame = self.pricing[field]
        frame = frame.loc[:end_date]
        return frame.iloc[-1]

    def historical(self, field: str, end_date: pd.Timestamp) -> pd.DataFrame:
        frame = self.pricing[field]
        return frame.loc[:end_date]


FIELD_ALIASES = {
    "close": {"close", "closeprice", "收盘价"},
    "open": {"open", "开盘价"},
    "high": {"high", "最高价"},
    "low": {"low", "最低价"},
    "volume": {"volume", "成交量"},
    "amount": {"amount", "成交额"},
}


class BacktestRunner:
    """Construct, configure, and execute a backtrader engine."""

    def __init__(self, config: PlatformConfig) -> None:
        self.config = config
        self.market: MarketProfile = config.market_profile()
        self.registry: FactorRegistry = GLOBAL_FACTOR_REGISTRY
        self._load_factor_paths()
        self.data_bundle: Optional[DataBundle] = None
        self.allocations: List[TargetAllocation] = []
        self.execution: ExecutionConfig = config.execution
        self._strategies: list[bt.Strategy] = []
        self._cerebro: Optional[bt.Cerebro] = None
        self.timing_source: Optional[pd.Series] = None
        self.timing_engine = build_timing_engine(
            config.timing.name if config.timing else None,
            config.timing.params if config.timing else (),
        )

    def _load_factor_paths(self) -> None:
        for path in self.config.factor_paths:
            p = Path(path)
            if p.exists():
                self.registry.load_path(p)
        default_path = Path("因子库")
        if default_path.exists():
            self.registry.load_path(default_path)

    def prepare(self) -> None:
        self.data_bundle = self._load_sources()
        self._prepare_timing_source()
        sessions = self._sessions()
        schedule = rebalance_schedule(
            sessions,
            self.config.strategy.hold_period,
            self.config.strategy.rebalance_offset_days,
        )
        self.allocations = self._build_allocations(schedule)

    def run(self) -> tuple[bt.Cerebro, list[bt.Strategy]]:
        if not self.allocations:
            self.prepare()
        cerebro = bt.Cerebro()
        cerebro.broker.setcash(self.execution.initial_cash)
        cerebro.broker.setcommission(
            commission=self.execution.commission_rate,
            stocklike=True,
        )
        if self.execution.stamp_duty and hasattr(cerebro.broker, 'setstamp'):
            cerebro.broker.setstamp(self.execution.stamp_duty)
        for name, frame in self._asset_frames().items():
            data = GenericPandasData(dataname=frame)
            cerebro.adddata(data, name=name)
        cerebro.addstrategy(
            MultiMarketStrategy,
            execution=self.execution,
            allocations=self.allocations,
            log=True,
        )
        cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="returns")
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
        strategies = cerebro.run()
        self._strategies = strategies
        self._cerebro = cerebro
        return cerebro, strategies

    def _load_sources(self) -> DataBundle:
        pricing_frames: Dict[str, pd.DataFrame] = {}
        financial = None
        macro = None
        for source in self.config.data_sources:
            frame = DATA_LOADERS.load(source, start=self._start(), end=self._end())
            if source.name == "daily_bar":
                pricing_frames.update(self._normalize_daily_bars(frame))
            elif source.name == "financial":
                financial = frame
            elif source.name == "macro":
                macro = frame
        if "close" not in pricing_frames:
            raise RuntimeError("Daily bar data with close prices is required")
        return DataBundle(pricing=pricing_frames, financial=financial, macro=macro)

    def _normalize_daily_bars(self, frame: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        df = frame.copy()
        if "trade_date" not in df.columns:
            if isinstance(df.index, pd.DatetimeIndex):
                index_name = df.index.name or 'trade_date'
                df = df.reset_index().rename(columns={index_name: 'trade_date'})
            else:
                raise RuntimeError("daily_bar dataset must contain 'trade_date'")
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.tz_localize(None)
        df = df.sort_values("trade_date")
        df = df[df["trade_date"].notnull()]
        symbol_field = "ts_code" if "ts_code" in df.columns else "symbol"
        pivots = {}
        for field in ["open", "high", "low", "close", "volume", "amount", "preclose", "float_mv", "total_mv", "adj_factor"]:
            if field not in df.columns:
                continue
            pivot = df.pivot_table(index="trade_date", columns=symbol_field, values=field)
            pivots[field] = pivot
        return pivots

    def _sessions(self) -> pd.DatetimeIndex:
        if not self.data_bundle:
            raise RuntimeError("Call prepare() before accessing sessions")
        pricing = self.data_bundle.pricing["close"]
        start = self._start() or pricing.index[0]
        end = self._end() or pricing.index[-1]
        return trading_sessions(self.market, start, end)

    def _build_allocations(self, schedule: Sequence[pd.Timestamp]) -> List[TargetAllocation]:
        if not self.data_bundle:
            raise RuntimeError("Data bundle missing, call prepare() first")
        pricing = self.data_bundle.pricing
        financial = self.data_bundle.financial
        macro = self.data_bundle.macro
        factors, ascending, weights, names = self._instantiate_factors()
        engine = FactorEngine(factors=factors, names=names, ascending=ascending, weights=weights)
        allocations: List[TargetAllocation] = []
        used_symbols = set()
        for date in schedule:
            ctx = FactorContext(
                pricing={field: frame.loc[:date] for field, frame in pricing.items()},
                financial=self._slice_financial(financial, date),
                macro=self._slice_macro(macro, date),
                universe=self.config.strategy.universe,
                market=self.market,
            )
            composite, details = engine.compute_with_details(ctx)
            filtered = self._apply_filters(date, composite, details, pricing)
            if filtered.empty:
                continue
            target = self._compose_weights(filtered)
            multiplier = self._timing_multiplier(date)
            if multiplier is not None:
                target = {k: v * multiplier for k, v in target.items()}
            allocations.append(TargetAllocation(date=date.normalize(), weights=target))
            used_symbols.update(target.keys())
        self._selected_symbols = sorted(used_symbols) if used_symbols else list(pricing["close"].columns)
        return allocations

    def _instantiate_factors(self) -> Tuple[List, List[bool], List[float], List[str]]:
        factors = []
        ascending = []
        weights = []
        names = []
        for definition in self.config.strategy.factors:
            factor_cls = self.registry.get(definition.name)
            params = definition.params
            if params and not isinstance(params, dict):
                params = {"value": params}
            factor = factor_cls(params=params)
            factors.append(factor)
            ascending.append(definition.ascending)
            weights.append(definition.weight)
            names.append(definition.name)
        return factors, ascending, weights, names

    def _apply_filters(
        self,
        date: pd.Timestamp,
        composite: pd.Series,
        details: Dict[str, pd.Series],
        pricing: Dict[str, pd.DataFrame],
    ) -> pd.Series:
        eligible = composite.copy()
        if not self.config.strategy.filters:
            return eligible
        for flt in self.config.strategy.filters:
            field_type, op, threshold = self._parse_rule(flt.rule)
            series = self._resolve_filter_series(flt, composite, details, pricing, date)
            if series is None or series.empty:
                continue
            if field_type == "pct":
                rank = series.rank(pct=True)
                mask = self._apply_operator(rank, op, threshold)
            else:
                mask = self._apply_operator(series, op, threshold)
            eligible = eligible.loc[eligible.index.intersection(series.index[mask])]
        return eligible

    def _resolve_filter_series(
        self,
        flt: FilterDefinition,
        composite: pd.Series,
        details: Dict[str, pd.Series],
        pricing: Dict[str, pd.DataFrame],
        date: pd.Timestamp,
    ) -> Optional[pd.Series]:
        if flt.name in {"composite", "score"}:
            return composite
        if flt.name in details:
            return details[flt.name]
        field_key = self._alias_to_field(flt.name)
        if field_key and field_key in pricing:
            frame = pricing[field_key].loc[:date]
            if frame.empty:
                return None
            return frame.iloc[-1]
        return None

    def _compose_weights(self, ranked: pd.Series) -> Dict[str, float]:
        count = self.config.strategy.select_count
        total_candidates = len(ranked)
        if total_candidates == 0:
            return {}
        if 0 < count < 1:
            take = max(1, int(total_candidates * count))
        else:
            take = max(1, int(count))
        top = ranked.head(take)
        positive = top[top > 0]
        base = positive if not positive.empty else top
        denom = base.abs().sum()
        if denom == 0:
            weight = 1.0 / len(base)
            return {symbol: weight for symbol in base.index}
        weights = base / denom
        return weights.to_dict()

    def _timing_multiplier(self, date: pd.Timestamp) -> Optional[float]:
        if not self.timing_engine or self.timing_source is None:
            return None
        series = self.timing_source.loc[:date]
        if series.empty:
            return None
        signal_series = self.timing_engine.compute_signal(series)
        if signal_series.empty:
            return None
        return float(signal_series.iloc[-1])

    def _prepare_timing_source(self) -> None:
        if not self.config.timing or not self.config.timing.data_source:
            self.timing_source = None
            return
        descriptor = self.config.timing.data_source
        if descriptor.startswith("pricing:") and self.data_bundle:
            _, field, symbol = descriptor.split(":", 2)
            field_key = self._alias_to_field(field)
            if field_key and field_key in self.data_bundle.pricing:
                frame = self.data_bundle.pricing[field_key]
                if symbol in frame.columns:
                    self.timing_source = frame[symbol].dropna()
        elif descriptor.startswith("macro:") and self.data_bundle and self.data_bundle.macro is not None:
            _, indicator = descriptor.split(":", 1)
            macro = self.data_bundle.macro
            subset = macro[macro["indicator"] == indicator]
            if not subset.empty:
                series = subset.set_index(pd.to_datetime(subset["release_time"]))["value"]
                self.timing_source = series.sort_index()
        else:
            self.timing_source = None

    def _alias_to_field(self, name: str) -> Optional[str]:
        lower = name.lower()
        for field, aliases in FIELD_ALIASES.items():
            if lower in aliases:
                return field
        return None

    def _parse_rule(self, rule: str) -> Tuple[str, str, float]:
        field, expr = rule.split(":", 1)
        for op in ["<=", ">=", "==", "!=", "<", ">"]:
            if op in expr:
                threshold = float(expr.split(op)[1])
                return field, op, threshold
        raise ValueError(f"Invalid filter rule: {rule}")

    def _apply_operator(self, series: pd.Series, op: str, threshold: float) -> pd.Series:
        if op == "<=":
            return series <= threshold
        if op == ">=":
            return series >= threshold
        if op == "==":
            return series == threshold
        if op == "!=":
            return series != threshold
        if op == "<":
            return series < threshold
        if op == ">":
            return series > threshold
        raise ValueError(f"Unsupported operator {op}")

    def _slice_financial(self, financial: Optional[pd.DataFrame], date: pd.Timestamp) -> Optional[pd.DataFrame]:
        if financial is None:
            return None
        if "report_date" in financial.columns:
            df = financial[pd.to_datetime(financial["report_date"]) <= date]
            return df
        return financial

    def _slice_macro(self, macro: Optional[pd.DataFrame], date: pd.Timestamp) -> Optional[pd.DataFrame]:
        if macro is None:
            return None
        if "release_time" in macro.columns:
            df = macro[pd.to_datetime(macro["release_time"]) <= date]
            return df
        return macro

    def equity_curve(self) -> pd.Series:
        """Return the cumulative equity curve from the last run."""

        if not getattr(self, '_strategies', None):
            raise RuntimeError('Run the backtest before requesting the equity curve')
        strategy = self._strategies[0]
        returns = strategy.analyzers.returns.get_analysis()
        if not returns:
            return pd.Series(dtype=float)
        series = pd.Series(returns)
        series.index = pd.to_datetime(series.index)
        equity = (1 + series).cumprod()
        equity.name = 'equity'
        return equity

    def drawdown_series(self) -> pd.Series:
        """Return drawdown series derived from the equity curve."""

        equity = self.equity_curve()
        if equity.empty:
            return equity
        dd = equity / equity.cummax() - 1
        dd.name = 'drawdown'
        return dd

    def last_cerebro(self) -> Optional[bt.Cerebro]:
        return getattr(self, '_cerebro', None)

    def last_strategies(self) -> list[bt.Strategy]:
        return list(getattr(self, '_strategies', []))

    def _asset_frames(self) -> Dict[str, pd.DataFrame]:
        if not self.data_bundle:
            raise RuntimeError("Data bundle missing")
        close_frame = self.data_bundle.pricing["close"]
        frames: Dict[str, pd.DataFrame] = {}
        symbols = getattr(self, "_selected_symbols", list(close_frame.columns))
        for symbol in symbols:
            data = {}
            for field in ["open", "high", "low", "close", "volume"]:
                frame = self.data_bundle.pricing.get(field)
                if frame is not None and symbol in frame.columns:
                    data[field] = frame[symbol]
            asset = pd.DataFrame(data).dropna(how="all")
            if asset.empty:
                continue
            asset.index.name = "datetime"
            frames[symbol] = asset
        return frames

    def _start(self) -> Optional[pd.Timestamp]:
        return pd.Timestamp(self.config.start_date) if self.config.start_date else None

    def _end(self) -> Optional[pd.Timestamp]:
        return pd.Timestamp(self.config.end_date) if self.config.end_date else None
