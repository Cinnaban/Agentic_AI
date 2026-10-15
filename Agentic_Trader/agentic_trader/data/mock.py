"""Deterministic synthetic market (geometric random walk with regimes and jumps).

Lets the whole system, including Discord reporting, run offline. `advance()` reveals one
more 1-minute bar so the runner can replay a full session in seconds.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import DataProvider

TZ = "America/New_York"
SESSION_MIN = 390
BASE_PRICES = {"SPY": 520, "QQQ": 450, "VTI": 270, "VXUS": 62, "BND": 73, "VNQ": 90,
               "AAPL": 230, "NVDA": 130, "SH": 12}


def _sessions(n_warm: int, end_day: pd.Timestamp) -> list[pd.Timestamp]:
    days = pd.bdate_range(end=end_day, periods=n_warm + 1)
    return [pd.Timestamp(d.date(), tz=TZ) + pd.Timedelta(hours=9, minutes=30) for d in days]


class MockProvider(DataProvider):
    name = "mock"

    def __init__(self, symbols: list[str], seed: int = 7, warmup_sessions: int = 4, sim_day: str | None = None):
        self.seed = seed
        self.warm = warmup_sessions
        day = pd.Timestamp(sim_day) if sim_day else pd.Timestamp("2026-10-14")
        starts = _sessions(warmup_sessions, day)
        self.idx = pd.DatetimeIndex([s + pd.Timedelta(minutes=m) for s in starts for m in range(SESSION_MIN)])
        self.cursor = warmup_sessions * SESSION_MIN + 1  # ready with the first bar of the sim day
        self._intraday: dict[str, pd.DataFrame] = {}
        self._daily: dict[str, pd.DataFrame] = {}
        market = np.random.default_rng(seed).normal(0, 0.0004, len(self.idx))
        for sym in dict.fromkeys(symbols + ["SPY", "SH"]):
            self._build(sym, market)

    def _build(self, sym: str, market: np.ndarray) -> None:
        rng = np.random.default_rng(self.seed + sum(map(ord, sym)))
        n = len(self.idx)
        beta = -1.0 if sym == "SH" else 1.0 if sym in ("SPY", "VTI", "BND", "VNQ", "VXUS") else 1.3
        idio = rng.normal(0, 0.0003, n)
        trend = np.sin(np.arange(n) / 180.0) * 0.00015  # slow regime swings so crossovers happen
        jumps = (rng.random(n) < 0.002) * rng.normal(0, 0.004, n)
        r = beta * market + idio + trend + jumps
        close = BASE_PRICES.get(sym, 100.0) * np.exp(np.cumsum(r))
        open_ = np.concatenate([[close[0]], close[:-1]])
        spread = np.abs(rng.normal(0, 0.0004, n)) * close
        df = pd.DataFrame({
            "open": open_, "high": np.maximum(open_, close) + spread,
            "low": np.minimum(open_, close) - spread,
            "close": close, "volume": rng.integers(5_000, 60_000, n).astype(float),
        }, index=self.idx)
        self._intraday[sym] = df
        daily = df.groupby(df.index.date).agg(open=("open", "first"), high=("high", "max"),
                                              low=("low", "min"), close=("close", "last"), volume=("volume", "sum"))
        # Extend with a synthetic multi-year daily history so 200-day averages are meaningful.
        hist_n = 400
        hr = rng.normal(0.0003, 0.01 * (0.5 if sym == "BND" else 1.0), hist_n)
        hc = daily["close"].iloc[0] * np.exp(-np.cumsum(hr[::-1])[::-1] + hr[-1])
        hist = pd.DataFrame({"open": hc, "high": hc * 1.004, "low": hc * 0.996, "close": hc,
                             "volume": 1e7}, index=pd.bdate_range(end=self.idx[0].normalize().tz_localize(None) - pd.Timedelta(days=1), periods=hist_n))
        daily.index = pd.to_datetime(daily.index)
        self._daily[sym] = pd.concat([hist, daily])

    def get_bars(self, symbol: str, interval: str = "1m", limit: int = 500) -> pd.DataFrame:
        if symbol not in self._intraday:
            self._build(symbol, np.random.default_rng(self.seed).normal(0, 0.0004, len(self.idx)))
        if interval == "1d":
            return self._daily[symbol].tail(limit).copy()
        return self._intraday[symbol].iloc[:self.cursor].tail(limit).copy()

    def advance(self) -> bool:
        if self.cursor >= len(self.idx):
            return False
        self.cursor += 1
        return True

    def now(self) -> pd.Timestamp:
        return self.idx[self.cursor - 1]

    def inject_shock(self, symbol: str, pct: float) -> None:
        """Scale all future bars of a symbol by (1+pct): used to test Discord movement alerts."""
        df = self._intraday[symbol]
        cols = ["open", "high", "low", "close"]
        df.iloc[self.cursor - 1:, [df.columns.get_loc(c) for c in cols]] *= 1 + pct
