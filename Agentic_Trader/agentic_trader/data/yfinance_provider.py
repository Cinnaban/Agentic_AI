"""Open-source/free data via yfinance (delayed, rate limited; fine for paper trading)."""
from __future__ import annotations

import pandas as pd

from .base import COLUMNS, DataProvider


class YFinanceProvider(DataProvider):
    name = "yfinance"

    def get_bars(self, symbol: str, interval: str = "1m", limit: int = 500) -> pd.DataFrame:
        import yfinance as yf

        period, iv = ("5d", "1m") if interval == "1m" else ("2y", "1d")
        df = yf.Ticker(symbol).history(period=period, interval=iv, auto_adjust=True)
        if df.empty:
            raise RuntimeError(f"yfinance returned no data for {symbol}")
        df = df.rename(columns=str.lower)[COLUMNS]
        df.index = df.index.tz_convert("America/New_York") if df.index.tz else df.index
        return df.tail(limit)
