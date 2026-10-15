"""Array backend + vectorized quant routines.

Uses CuPy (NVIDIA GPU, e.g. the gaming PC) when installed and TRADER_USE_GPU != 0,
otherwise falls back to NumPy. All routines are written against `xp` so they run on either.
"""
from __future__ import annotations

import os

import numpy as np

try:  # pragma: no cover - depends on hardware
    if os.getenv("TRADER_USE_GPU", "1") == "0":
        raise ImportError
    import cupy as xp  # type: ignore

    xp.cuda.runtime.getDeviceCount()
    BACKEND = "cupy-gpu"
except Exception:
    xp = np
    BACKEND = "numpy-cpu"


def to_host(a):
    return a.get() if hasattr(a, "get") else np.asarray(a)


def rolling_mean(x, window: int):
    """Trailing mean; first window-1 entries are NaN. x is 1-D."""
    c = xp.cumsum(xp.concatenate([xp.zeros(1), x]))
    out = xp.full(x.shape[0], xp.nan)
    out[window - 1:] = (c[window:] - c[:-window]) / window
    return out


def sweep_ma_crossover(close, fast_grid, slow_grid, cost_bps: float = 1.0):
    """Evaluate every (fast, slow) SMA crossover in one pass.

    Returns list of dicts sorted by Sharpe-like score. Long/flat, signal lagged one bar.
    """
    close = xp.asarray(close, dtype=float)
    ret = xp.diff(close) / close[:-1]
    ret = xp.concatenate([xp.zeros(1), ret])
    means = {w: rolling_mean(close, w) for w in set(fast_grid) | set(slow_grid)}
    results = []
    for f in fast_grid:
        for s in slow_grid:
            if f >= s or s >= close.shape[0]:
                continue
            raw = xp.where(xp.isnan(means[s]), 0.0, (means[f] > means[s]).astype(float))
            pos = xp.concatenate([xp.zeros(1), raw[:-1]])
            turnover = xp.abs(xp.diff(pos, prepend=0.0))
            strat = pos * ret - turnover * cost_bps / 1e4
            sd = float(strat.std())
            results.append({
                "fast": int(f), "slow": int(s),
                "total_return": float(xp.prod(1 + strat) - 1),
                "score": float(strat.mean() / sd * np.sqrt(252 * 390)) if sd > 0 else 0.0,
                "trades": int(turnover.sum()),
            })
    return sorted(results, key=lambda r: r["score"], reverse=True)


def ridge_fit(X, y, alpha: float = 1.0):
    """Closed-form ridge regression with intercept; returns coefficient vector (intercept first)."""
    X = xp.asarray(X, dtype=float)
    y = xp.asarray(y, dtype=float)
    A = xp.concatenate([xp.ones((X.shape[0], 1)), X], axis=1)
    reg = alpha * xp.eye(A.shape[1])
    reg[0, 0] = 0.0
    return to_host(xp.linalg.solve(A.T @ A + reg, A.T @ y))


def ridge_predict(coef, X):
    X = np.asarray(X, dtype=float)
    return coef[0] + X @ coef[1:]
