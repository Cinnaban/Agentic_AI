"""Alpaca market data (free IEX feed with an API key). Keys: ALPACA_API_KEY / ALPACA_API_SECRET."""
from __future__ import annotations

import pandas as pd
import requests

from .base import COLUMNS, DataProvider

URL = "https://data.alpaca.markets/v2/stocks/{sym}/bars"


class AlpacaProvider(DataProvider):
    name = "alpaca"

    def __init__(self, key: str, secret: str, feed: str = "iex"):
        if not key or not secret:
            raise RuntimeError("ALPACA_API_KEY / ALPACA_API_SECRET are not set")
        self.headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        self.feed = feed

    def get_bars(self, symbol: str, interval: str = "1m", limit: int = 500) -> pd.DataFrame:
        tf = "1Min" if interval == "1m" else "1Day"
        start = pd.Timestamp.utcnow() - pd.Timedelta(days=5 if interval == "1m" else 500)
        r = requests.get(URL.format(sym=symbol), headers=self.headers, timeout=15, params={
            "timeframe": tf, "limit": 10000, "feed": self.feed, "adjustment": "all",
            "start": start.strftime("%Y-%m-%dT%H:%M:%SZ")})
        r.raise_for_status()
        rows = r.json().get("bars") or []
        if not rows:
            raise RuntimeError(f"Alpaca returned no bars for {symbol}")
        df = pd.DataFrame(rows).rename(columns={"t": "ts", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
        df.index = pd.to_datetime(df.pop("ts")).dt.tz_convert("America/New_York")
        return df[COLUMNS].tail(limit)
