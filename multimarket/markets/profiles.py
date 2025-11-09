"""Market-specific trading rule definitions."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


TradingSession = Tuple[time, time]
CommissionRule = Dict[str, float]


@dataclass(frozen=True)
class MarketProfile:
    """Encapsulates market-specific conventions used during backtests."""

    code: str
    name: str
    timezone: str
    currency: str
    lot_size: int
    sessions: Sequence[TradingSession]
    tick_size: float
    stamp_duty: float = 0.0
    short_fee: float = 0.0
    min_commission: float = 0.0
    commission_multipliers: CommissionRule = field(default_factory=dict)
    holiday_calendar: Optional[str] = None
    settlement_days: int = 0

    def session_strings(self) -> List[str]:
        """Return readable session windows for logging."""

        return [f"{window[0].strftime('%H:%M')} - {window[1].strftime('%H:%M')}" for window in self.sessions]


def _time(hour: int, minute: int) -> time:
    return time(hour=hour, minute=minute)


MARKET_PROFILES: Dict[str, MarketProfile] = {
    "cn": MarketProfile(
        code="cn",
        name="A-Shares",
        timezone="Asia/Shanghai",
        currency="CNY",
        lot_size=100,
        sessions=[(_time(9, 30), _time(11, 30)), (_time(13, 0), _time(15, 0))],
        tick_size=0.01,
        stamp_duty=0.001,
        min_commission=5.0,
        commission_multipliers={"stock": 0.0003, "etf": 0.0002},
        holiday_calendar="XSHG",
        settlement_days=1,
    ),
    "us": MarketProfile(
        code="us",
        name="US Equities",
        timezone="America/New_York",
        currency="USD",
        lot_size=1,
        sessions=[(_time(9, 30), _time(16, 0))],
        tick_size=0.01,
        stamp_duty=0.0,
        short_fee=0.0005,
        commission_multipliers={"stock": 0.0005, "option": 0.015},
        holiday_calendar="XNYS",
        settlement_days=2,
    ),
    "hk": MarketProfile(
        code="hk",
        name="Hong Kong Equities",
        timezone="Asia/Hong_Kong",
        currency="HKD",
        lot_size=100,
        sessions=[(_time(9, 30), _time(12, 0)), (_time(13, 0), _time(16, 0))],
        tick_size=0.01,
        stamp_duty=0.001,
        min_commission=10.0,
        commission_multipliers={"stock": 0.00027},
        holiday_calendar="XHKG",
        settlement_days=2,
    ),
    "crypto": MarketProfile(
        code="crypto",
        name="Crypto Spot",
        timezone="UTC",
        currency="USD",
        lot_size=1,
        sessions=[(_time(0, 0), _time(23, 59))],
        tick_size=0.01,
        stamp_duty=0.0,
        short_fee=0.0,
        commission_multipliers={"spot": 0.0005},
        holiday_calendar=None,
        settlement_days=0,
    ),
}
