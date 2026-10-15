"""Intraday trader: EMA crossover + VWAP/RSI filters, ATR stop, optional regression gate, SPY hedge."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .. import indicators as ind
from ..config import STATE_DIR
from ..features import FEATURES, feature_frame
from ..compute import ridge_predict
from .base import Signal

DEFAULT_PARAMS = {
    "fast": 9, "slow": 21, "cross_lookback": 3, "rsi_max": 72.0, "rsi_exit": 85.0,
    "atr_stop": 2.0, "min_score": 0.0, "use_model": True,
    "hedge_trigger": -0.007, "hedge_weight": 0.05,
}
PARAMS_FILE = STATE_DIR / "day_params.json"
MODEL_FILE = STATE_DIR / "day_model.json"


def load_params(path: Path = PARAMS_FILE) -> dict:
    p = dict(DEFAULT_PARAMS)
    if path.exists():
        p.update(json.loads(path.read_text()))
    return p


class DayTradeStrategy:
    name = "day"

    def __init__(self, params: dict | None = None, model_path: Path = MODEL_FILE):
        self.params = params or load_params()
        self.model = json.loads(model_path.read_text()) if model_path.exists() else None

    def _score(self, bars: pd.DataFrame) -> float:
        if not (self.model and self.params["use_model"]):
            return 0.0
        row = feature_frame(bars).iloc[-1][FEATURES]
        if row.isna().any():
            return 0.0
        x = (row.values - np.array(self.model["mean"])) / np.array(self.model["std"])
        return float(ridge_predict(np.array(self.model["coef"]), x[None, :])[0])

    def evaluate(self, symbol: str, bars: pd.DataFrame, entry_price: float | None, weight: float) -> Signal:
        p = self.params
        if len(bars) < max(p["slow"] * 2, 40):
            return Signal(symbol, "hold", "warming up")
        df = ind.add_all(bars)
        c = df["close"]
        fast, slow = ind.ema(c, p["fast"]), ind.ema(c, p["slow"])
        last = df.iloc[-1]
        if entry_price is not None:  # manage open position
            if last["close"] < entry_price - p["atr_stop"] * last["atr14"]:
                return Signal(symbol, "sell", "ATR stop hit")
            if fast.iloc[-1] < slow.iloc[-1]:
                return Signal(symbol, "sell", "EMA cross down")
            if last["rsi14"] > p["rsi_exit"]:
                return Signal(symbol, "sell", f"RSI overbought {last['rsi14']:.0f}")
            return Signal(symbol, "hold", "in trade")
        n = p["cross_lookback"]
        crossed = ((fast.iloc[-n:] > slow.iloc[-n:]).all()
                   and (fast.iloc[-n - 1] <= slow.iloc[-n - 1]) if len(fast) > n else False)
        today = df[df.index.date == df.index[-1].date()]
        above_vwap = last["close"] > ind.vwap(today).iloc[-1]
        if crossed and above_vwap and last["rsi14"] < p["rsi_max"]:
            score = self._score(bars)
            if score >= p["min_score"]:
                return Signal(symbol, "buy", f"EMA{p['fast']}/{p['slow']} cross, >VWAP, RSI {last['rsi14']:.0f}",
                              weight=weight, score=score)
            return Signal(symbol, "hold", f"model veto (score {score:.5f})", score=score)
        return Signal(symbol, "hold", "no setup")

    def hedge(self, spy_bars: pd.DataFrame, hedged: bool, symbol: str) -> Signal:
        """Hold the inverse ETF while SPY is down on the day and below VWAP."""
        today = spy_bars[spy_bars.index.date == spy_bars.index[-1].date()]
        if len(today) < 15:
            return Signal(symbol, "hold", "hedge: too early")
        move = today["close"].iloc[-1] / today["open"].iloc[0] - 1
        below = today["close"].iloc[-1] < ind.vwap(today).iloc[-1]
        if not hedged and move <= self.params["hedge_trigger"] and below:
            return Signal(symbol, "buy", f"hedge: SPY {move:+.2%} & <VWAP", weight=self.params["hedge_weight"])
        if hedged and (move > self.params["hedge_trigger"] / 2 or not below):
            return Signal(symbol, "sell", f"hedge off: SPY {move:+.2%}")
        return Signal(symbol, "hold", "hedge unchanged")
