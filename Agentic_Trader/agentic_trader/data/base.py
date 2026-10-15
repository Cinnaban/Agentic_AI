from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

COLUMNS = ["open", "high", "low", "close", "volume"]


class DataProvider(ABC):
    """Market data source. Frames are indexed by tz-aware timestamps with COLUMNS."""

    name = "base"

    @abstractmethod
    def get_bars(self, symbol: str, interval: str = "1m", limit: int = 500) -> pd.DataFrame:
        """interval: '1m' (intraday) or '1d' (daily)."""

    def last_price(self, symbol: str) -> float:
        return float(self.get_bars(symbol, "1m", 1)["close"].iloc[-1])

    def advance(self) -> bool:
        """Simulated feeds step forward one bar; live feeds just return True."""
        return True

    def now(self) -> pd.Timestamp:
        return pd.Timestamp.now(tz="America/New_York")
