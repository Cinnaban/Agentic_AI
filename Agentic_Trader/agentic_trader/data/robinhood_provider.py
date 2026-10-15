"""Real-time bars/quotes from the Robinhood MCP (read-only market data)."""
from __future__ import annotations

import pandas as pd

from ..robinhood.data import RobinhoodData, shared
from .base import COLUMNS, DataProvider

TZ = "America/New_York"


class RobinhoodProvider(DataProvider):
    name = "robinhood"

    def __init__(self, data: RobinhoodData | None = None):
        self.d = data or shared()

    def get_bars(self, symbol: str, interval: str = "1m", limit: int = 500) -> pd.DataFrame:
        iv, days = ("minute", 6) if interval == "1m" else ("day", 800)
        rows = self.d.bars([symbol], iv, days_back=days).get(symbol.upper())
        if not rows:
            raise RuntimeError(f"Robinhood returned no bars for {symbol}")
        df = pd.DataFrame(rows).set_index("ts")
        df.index = pd.DatetimeIndex(df.index).tz_convert(TZ)
        return df[COLUMNS].astype(float).tail(limit)

    def last_price(self, symbol: str) -> float:
        q = self.d.quotes([symbol]).get(symbol.upper())
        if not q or not q["price"]:
            raise RuntimeError(f"No live quote for {symbol}")
        return q["price"]
