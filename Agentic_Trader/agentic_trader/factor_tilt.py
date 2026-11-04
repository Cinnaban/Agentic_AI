"""Cross-sectional factor tilt for the day team, adapted from the price/liquidity signals in the S43 kit.

S43 equal-weights published predictors, each in its paper's direction, and ranks names against their peers.
Only the price-based ones can be computed from the daily bars we already fetch. They are slow signals, so they
tilt the *ranking* of setups and never create or veto entries on their own.

  mom      return from ~6 months ago to 1 month ago, skipping the latest month  (high is good)
  hi52     price / highest high in the window                                    (high is good)
  rev_1m   last month's return                                                   (low is good)
  maxret   largest daily return in the last 21 days, the "lottery" effect        (low is good)
  vol      daily return volatility                                               (low is good)
  amihud   mean |return| / dollar volume, i.e. illiquidity                       (high is good in S43)
"""
from __future__ import annotations

import numpy as np

SIGNALS = {"mom": 1, "hi52": 1, "rev_1m": -1, "maxret": -1, "vol": -1, "amihud": 1}
MIN_BARS = 60


def raw_signals(daily):
    """Signals for one symbol from daily bars (oldest first), or None if there is too little history."""
    bars = [b for b in daily if b.get("close")]
    if len(bars) < MIN_BARS:
        return None
    c = np.array([float(b["close"]) for b in bars])
    h = np.array([float(b.get("high") or b["close"]) for b in bars])
    v = np.array([float(b.get("volume") or 0) for b in bars])
    r = np.diff(c) / c[:-1]
    n = len(c)
    dolvol = float(np.mean(c[-21:] * v[-21:]))
    out = {
        "mom": float(c[-22] / c[max(0, n - 127)] - 1) if n > 22 else 0.0,
        "hi52": float(c[-1] / h.max()),
        "rev_1m": float(c[-1] / c[-22] - 1),
        "maxret": float(r[-21:].max()),
        "vol": float(r.std(ddof=1)),
        "amihud": float(np.mean(np.abs(r[-21:]) / np.maximum(c[-21:] * v[-21:], 1.0))),
        "dolvol": dolvol,
    }
    return out


def rank01(values):
    """Percentile rank in [0, 1]; ties share the average rank. A single name sits at 0.5."""
    a = np.asarray(values, dtype=float)
    if len(a) < 2:
        return np.full(len(a), 0.5)
    order = a.argsort(kind="mergesort")
    ranks = np.empty(len(a))
    ranks[order] = np.arange(len(a))
    for x in np.unique(a):
        m = a == x
        if m.sum() > 1:
            ranks[m] = ranks[m].mean()
    return ranks / (len(a) - 1)


def tilt(daily_by_symbol, min_dollar_volume=50e6):
    """{sym: {"tilt": -1..+1, "liquid": bool, "parts": {signal: rank}}}; equal weights, nothing fitted."""
    raw = {s: raw_signals(b) for s, b in daily_by_symbol.items()}
    raw = {s: r for s, r in raw.items() if r}
    if len(raw) < 3:
        return {}
    syms = sorted(raw)
    score = np.zeros(len(syms))
    ranks = {}
    for name, sign in SIGNALS.items():
        rk = rank01([raw[s][name] for s in syms])
        ranks[name] = rk
        score += rk if sign > 0 else 1 - rk
    score = score / len(SIGNALS) * 2 - 1
    return {s: {"tilt": float(score[i]), "liquid": raw[s]["dolvol"] >= min_dollar_volume,
                "parts": {k: float(ranks[k][i]) for k in SIGNALS}} for i, s in enumerate(syms)}
