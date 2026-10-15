"""Live-quote quant metrics and a walk-forward prediction scorecard.

Inputs are plain dicts from RobinhoodData (quotes + minute/5-minute bars). No account data.
"""
from __future__ import annotations

import math

import numpy as np

from .compute import ridge_fit, ridge_predict

BARS_PER_YEAR_5M = 252 * 78


def _arr(bars, key="close"):
    return np.array([b[key] for b in bars if b.get(key) is not None], dtype=float)


def _ema(x, n):
    a = 2 / (n + 1)
    out = np.empty_like(x)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def _rsi(c, n=14):
    d = np.diff(c)
    if len(d) < n:
        return None
    up, dn = np.clip(d, 0, None)[-n:].mean(), np.clip(-d, 0, None)[-n:].mean()
    return 100.0 if dn == 0 else 100 - 100 / (1 + up / dn)


def metrics(quote: dict, bars: list[dict], bench_bars: list[dict] | None = None) -> dict:
    """Quant formulas from the live quote anchored on recent bars (5-minute recommended)."""
    c = _arr(bars)
    if len(c) < 30:
        return {"symbol": quote.get("symbol"), "error": "insufficient bars"}
    px = quote.get("price") or c[-1]
    h, l, v = _arr(bars, "high"), _arr(bars, "low"), _arr(bars, "volume")
    r = np.diff(np.log(c))
    vol = float(r.std(ddof=1))
    out = {"symbol": quote.get("symbol"), "price": px, "n_bars": len(c)}
    out["realized_vol_ann"] = vol * math.sqrt(BARS_PER_YEAR_5M)
    sd20 = c[-20:].std(ddof=1)
    out["bb_z"] = float((px - c[-20:].mean()) / sd20) if sd20 else 0.0
    tr = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
    atr = float(tr[-14:].mean())
    out["atr_pct"] = atr / px
    pv = (c * v).sum()
    vwap = float(pv / v.sum()) if v.sum() > 0 else float(c.mean())
    out["vwap_dev_pct"] = px / vwap - 1
    out["vwap_z"] = float((px - vwap) / sd20) if sd20 else 0.0
    out["rsi14"] = _rsi(c)
    e12, e26 = _ema(c, 12), _ema(c, 26)
    macd = e12 - e26
    out["macd_hist"] = float(macd[-1] - _ema(macd, 9)[-1])
    for k in (6, 12, 36):
        if len(c) > k:
            out[f"mom_{k}"] = float(px / c[-k - 1] - 1)
    out["sharpe_like"] = float(r.mean() / vol * math.sqrt(BARS_PER_YEAR_5M)) if vol else 0.0
    bid, ask = quote.get("bid"), quote.get("ask")
    if bid and ask and px:
        out["spread_bps"] = (ask - bid) / px * 1e4
        out["quote_imbalance"] = float((px - (bid + ask) / 2) / (ask - bid)) if ask > bid else 0.0
    # mean-reversion half-life from AR(1) on price deviations
    dev = c - c.mean()
    den = float((dev[:-1] ** 2).sum())
    phi = float((dev[:-1] * dev[1:]).sum() / den) if den else 0.0
    out["half_life_bars"] = float(-math.log(2) / math.log(phi)) if 0 < phi < 1 else None
    # Hurst-lite: variance ratio of 6-bar vs 1-bar returns (>1 trending, <1 mean-reverting)
    if len(c) > 40:
        r6 = np.log(c[6:]) - np.log(c[:-6])
        out["variance_ratio_6"] = float(r6.var(ddof=1) / (6 * r.var(ddof=1))) if r.var() else None
    if bench_bars:
        b = np.diff(np.log(_arr(bench_bars)))
        n = min(len(b), len(r))
        if n > 30 and b[-n:].var() > 0:
            rr, bb = r[-n:], b[-n:]
            out["beta_vs_spy"] = float(np.cov(rr, bb)[0, 1] / bb.var(ddof=1))
            out["corr_vs_spy"] = float(np.corrcoef(rr, bb)[0, 1])
    out["signal_score"] = _score(out)
    return out


def _score(m: dict) -> float:
    """Composite in [-1, 1]: trend/momentum minus stretch (mean-reversion). Descriptive, not a trade order."""
    s = 0.0
    s += 0.35 * np.tanh((m.get("mom_12") or 0) / max(m["atr_pct"], 1e-6) / 3)
    s += 0.25 * np.tanh(m.get("macd_hist", 0) / max(m["price"] * m["atr_pct"], 1e-9) * 3)
    s -= 0.25 * np.tanh(m.get("bb_z", 0) / 2)
    rsi = m.get("rsi14")
    if rsi is not None:
        s -= 0.15 * np.tanh((rsi - 50) / 25) * (1 if abs(rsi - 50) > 20 else 0.3)
    return float(np.clip(s, -1, 1))


def _features(c, v):
    r = np.diff(np.log(c))
    X, y = [], []
    for i in range(30, len(r) - 1):
        w = r[i - 20:i + 1]
        X.append([r[i], w[-6:].sum(), w.sum(), w.std(), (c[i + 1] - c[i - 19:i + 1].mean()) / (c[i - 19:i + 1].std() + 1e-12)])
        y.append(r[i + 1])
    return np.array(X), np.array(y)


def prediction_scorecard(bars: list[dict], folds: int = 4, alpha: float = 10.0) -> dict:
    """Walk-forward ridge on next-bar return. Metrics: IC, hit rate, R2, RMSE, MAE, calibration slope, naive-RMSE edge."""
    c, v = _arr(bars), _arr(bars, "volume")
    if len(c) < 150:
        return {"error": "need >=150 bars", "n": len(c)}
    X, y = _features(c, v)
    n = len(y)
    cut = np.linspace(n // 2, n, folds + 1, dtype=int)
    preds, acts = [], []
    for a, b in zip(cut[:-1], cut[1:]):
        mu, sd = X[:a].mean(0), X[:a].std(0) + 1e-12
        w = ridge_fit((X[:a] - mu) / sd, y[:a], alpha)
        preds.append(np.asarray(ridge_predict(w, (X[a:b] - mu) / sd), dtype=float))
        acts.append(y[a:b])
    p, a = np.concatenate(preds), np.concatenate(acts)
    ic = float(np.corrcoef(p, a)[0, 1]) if p.std() and a.std() else 0.0
    rmse = float(np.sqrt(((p - a) ** 2).mean()))
    naive = float(np.sqrt((a ** 2).mean()))
    slope = float(np.cov(p, a)[0, 1] / p.var(ddof=1)) if p.var() else 0.0
    return {"n_oos": int(len(a)), "ic": ic, "hit_rate": float((np.sign(p) == np.sign(a)).mean()),
            "r2": float(1 - ((p - a) ** 2).sum() / ((a - a.mean()) ** 2).sum()), "rmse": rmse,
            "mae": float(abs(p - a).mean()), "calibration_slope": slope,
            "rmse_vs_naive": rmse / naive if naive else None}


def analyze(symbols: list[str], data=None, bench="SPY", interval="5minute", days_back=5) -> dict:
    """Pull live quotes + bars and compute metrics/scorecards per symbol."""
    from .robinhood.data import shared
    data = data or shared()
    syms = list(dict.fromkeys([s.upper() for s in symbols] + [bench]))
    quotes, bars = data.quotes(syms), data.bars(syms, interval, days_back)
    res = {}
    for s in syms:
        if s == bench and bench not in [x.upper() for x in symbols]:
            continue
        if s not in quotes or s not in bars:
            res[s] = {"error": "no data"}
            continue
        m = metrics(quotes[s], bars[s], bars.get(bench))
        m["scorecard"] = prediction_scorecard(bars[s])
        res[s] = m
    return res
