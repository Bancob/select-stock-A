"""Dataset loading utilities."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional, Sequence

import backtrader as bt
import pandas as pd

from ..config import DataSourceConfig


LoaderFunc = Callable[[DataSourceConfig, Optional[datetime], Optional[datetime]], pd.DataFrame]


class DataLoaderRegistry:
    """Registry for dataset loader callables."""

    def __init__(self) -> None:
        self._loaders: Dict[str, LoaderFunc] = {}

    def register(self, name: str, func: LoaderFunc) -> None:
        self._loaders[name] = func

    def get(self, name: str) -> LoaderFunc:
        if name not in self._loaders:
            raise KeyError(f"Loader '{name}' is not registered")
        return self._loaders[name]

    def load(
        self,
        config: DataSourceConfig,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        alias = config.loader
        if alias == "auto":
            alias = _infer_loader(config.as_path())
        loader = self.get(alias)
        return loader(config, start, end)


REGISTRY = DataLoaderRegistry()


def _infer_loader(path: Path) -> str:
    if path.is_dir():
        return "csv"
    suffix = path.suffix.lower()
    if suffix in {".parquet", ".pq"}:
        return "parquet"
    if suffix == ".csv":
        return "csv"
    raise RuntimeError(f"Cannot infer loader for path {path}")


def _apply_bounds(frame: pd.DataFrame, start: Optional[datetime], end: Optional[datetime]) -> pd.DataFrame:
    if frame.empty:
        return frame
    if start is not None:
        frame = frame.loc[frame.index >= pd.Timestamp(start)]
    if end is not None:
        frame = frame.loc[frame.index <= pd.Timestamp(end)]
    return frame


def csv_loader(config: DataSourceConfig, start: Optional[datetime], end: Optional[datetime]) -> pd.DataFrame:
    path = config.as_path()
    if path.is_dir():
        pattern = config.metadata.get("pattern", "*.csv")
        frames = []
        for file in sorted(path.glob(pattern)):
            frame = pd.read_csv(file, parse_dates=config.metadata.get("parse_dates"))
            frames.append(frame)
        if not frames:
            return pd.DataFrame()
        data = pd.concat(frames, ignore_index=True)
    else:
        data = pd.read_csv(path, parse_dates=config.metadata.get("parse_dates"))
    index_field = config.metadata.get("index")
    if index_field:
        data[index_field] = pd.to_datetime(data[index_field])
        data = data.set_index(index_field)
    return _apply_bounds(data, start, end)


def parquet_loader(config: DataSourceConfig, start: Optional[datetime], end: Optional[datetime]) -> pd.DataFrame:
    path = config.as_path()
    if path.is_dir():
        frames = []
        for file in sorted(path.glob(config.metadata.get("pattern", "*.parquet"))):
            frame = pd.read_parquet(file)
            frames.append(frame)
        if not frames:
            return pd.DataFrame()
        data = pd.concat(frames, ignore_index=True)
    else:
        data = pd.read_parquet(path)
    index_field = config.metadata.get("index")
    if index_field:
        data[index_field] = pd.to_datetime(data[index_field])
        data = data.set_index(index_field)
    return _apply_bounds(data, start, end)


def quantcsv_loader(config: DataSourceConfig, start: Optional[datetime], end: Optional[datetime]) -> pd.DataFrame:
    """Loader for Quantclass-style per-symbol CSV folders."""

    path = config.as_path()
    encoding = config.metadata.get("encoding", "gbk")
    skiprows = int(config.metadata.get("skiprows", 1))
    pattern = config.metadata.get("pattern", "*.csv")
    prefixes: Sequence[str] = tuple(map(str.lower, config.metadata.get("prefixes", [])))  # type: ignore[arg-type]
    symbols: Optional[set[str]] = None
    if config.metadata.get("symbols"):
        symbols = {str(sym).lower() for sym in config.metadata["symbols"]}

    files = [path] if path.is_file() else sorted(path.glob(pattern))
    frames = []
    for file in files:
        stem = file.stem.lower()
        if prefixes and not stem.startswith(tuple(prefixes)):
            continue
        if symbols and stem not in symbols and stem.upper() not in symbols:
            continue
        try:
            df = pd.read_csv(file, skiprows=skiprows, encoding=encoding)
        except UnicodeDecodeError:
            df = pd.read_csv(file, skiprows=skiprows, encoding="gbk")
        if df.empty:
            continue
        if "index_code" in df.columns:
            df = df.rename(columns={"index_code": "ts_code", "candle_end_time": "trade_date"})
        elif len(df.columns) >= 12:
            df = df.iloc[:, :12]
            df.columns = [
                "ts_code",
                "name",
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "preclose",
                "volume",
                "amount",
                "float_mv",
                "total_mv",
            ]
        else:
            column_map = config.metadata.get("columns")
            if column_map:
                df = df.rename(columns=column_map)
        if "trade_date" not in df.columns:
            continue
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        df = df[df["trade_date"].notnull()]
        if "ts_code" not in df.columns:
            df["ts_code"] = stem
        df["ts_code"] = df["ts_code"].astype(str).str.upper()
        numeric_cols = [
            "open",
            "high",
            "low",
            "close",
            "preclose",
            "volume",
            "amount",
            "float_mv",
            "total_mv",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    data = pd.concat(frames, ignore_index=True)
    data = data.sort_values(["trade_date", "ts_code"]).reset_index(drop=True)
    data["trade_date"] = data["trade_date"].dt.tz_localize(None)
    data = data.drop(columns=["name"], errors="ignore")
    if start:
        data = data[data["trade_date"] >= pd.Timestamp(start)]
    if end:
        data = data[data["trade_date"] <= pd.Timestamp(end)]
    return data


REGISTRY.register("csv", csv_loader)
REGISTRY.register("parquet", parquet_loader)
REGISTRY.register("quantcsv", quantcsv_loader)


class GenericPandasData(bt.feeds.PandasData):
    """Backtrader data feed that expects standard OHLCV columns."""

    params = (
        ("datetime", None),
        ("open", "open"),
        ("high", "high"),
        ("low", "low"),
        ("close", "close"),
        ("volume", "volume"),
        ("openinterest", None),
    )


def to_backtrader_data(
    frame: pd.DataFrame,
    timeframe: bt.TimeFrame = bt.TimeFrame.Days,
    compression: int = 1,
) -> bt.feeds.PandasData:
    """Convert a pandas frame into a backtrader data feed."""

    data = frame.copy()
    if "datetime" not in data.columns:
        data = data.rename(columns={"trade_date": "datetime"})
    data["datetime"] = pd.to_datetime(data["datetime"])
    data = data.set_index("datetime")
    feed = GenericPandasData(dataname=data)
    feed.timeframe = timeframe
    feed.compression = compression
    return feed
