"""Feature engineering shared by the day-trader gate and the regression improvement loop."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import indicators as ind

FEATURES = ["ret1", "ret5", "ret15", "ema_gap", "rsi", "macd_hist", "pct_b", "vol_ratio", "vwap_gap"]


def feature_frame(bars: pd.DataFrame) -> pd.DataFrame:
    df = ind.add_all(bars)
    c = df["close"]
    out = pd.DataFrame(index=df.index)
    out["ret1"], out["ret5"], out["ret15"] = c.pct_change(1), c.pct_change(5), c.pct_change(15)
    out["ema_gap"] = (df["ema9"] - df["ema21"]) / c
    out["rsi"] = df["rsi14"] / 100 - 0.5
    out["macd_hist"] = df["hist"] / c
    band = (df["bb_upper"] - df["bb_lower"]).replace(0, np.nan)
    out["pct_b"] = ((c - df["bb_lower"]) / band - 0.5).fillna(0)
    out["vol_ratio"] = (df["volume"] / df["volume"].rolling(30).mean()).fillna(1) - 1
    out["vwap_gap"] = (c - df["vwap"]) / c
    return out.replace([np.inf, -np.inf], np.nan)


def forward_return(bars: pd.DataFrame, horizon: int = 10) -> pd.Series:
    return bars["close"].shift(-horizon) / bars["close"] - 1
