"""Calendar helpers."""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, List

import pandas as pd

from ..markets.profiles import MarketProfile


def trading_sessions(
    profile: MarketProfile,
    start: datetime,
    end: datetime,
) -> pd.DatetimeIndex:
    """Return valid trading sessions between ``start`` and ``end``."""

    try:
        import pandas_market_calendars as mcal

        cal = mcal.get_calendar(profile.holiday_calendar) if profile.holiday_calendar else None
        if cal:
            schedule = cal.schedule(start_date=start, end_date=end)
            return pd.DatetimeIndex(schedule.index.tz_localize(None))
    except ImportError:
        pass
    return pd.date_range(start=start, end=end, freq="B")


def rebalance_schedule(
    sessions: Iterable[pd.Timestamp],
    hold_period: str,
    offset_days: int = 0,
) -> List[pd.Timestamp]:
    """Create a list of rebalance dates aligned to trading sessions."""

    normalized = hold_period.upper()
    if normalized.endswith('M') and not normalized.endswith('ME'):
        normalized = normalized[:-1] + 'ME'
    freq = pd.tseries.frequencies.to_offset(normalized)
    session_list = sorted(pd.Timestamp(ts) for ts in sessions)
    if not session_list:
        return []
    schedule: List[pd.Timestamp] = []
    cursor = session_list[0]
    idx = 0
    while idx < len(session_list):
        target_date = (cursor + freq).normalize()
        while idx < len(session_list) and session_list[idx] < target_date:
            idx += 1
        if idx >= len(session_list):
            break
        assign_idx = max(0, idx - 1 + offset_days)
        assign_idx = min(assign_idx, len(session_list) - 1)
        schedule.append(session_list[assign_idx].normalize())
        cursor = session_list[idx]
    return schedule
