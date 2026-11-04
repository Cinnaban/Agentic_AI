"""Quant metric suite used before any paper trade (day, options and long-hold agents).

Pure numpy and causal: every feature at bar i uses data up to bar i only. Models are always evaluated with
PURGED WALK-FORWARD splits (never random splits): each fold trains on the past, leaves a purge gap of
`horizon + embargo` bars so no training label overlaps the test window, then tests on the next block.

Per symbol:
  indicators   RSI (Wilder), MACD, Z-score, RVOL, realized volatility (RV), GARCH(1,1) volatility forecast
  model (OOS)  RMSE (vs naive), directional accuracy / hit rate, Information Coefficient (rank IC),
               Log Loss and AUC-ROC of the up/down probability
  evaluation   Sharpe, Sortino, Max Drawdown and Profit Factor of the out-of-sample signal strategy

A weak edge is expected and fine: ~53% hit rate or a small positive IC is useful when sizing and risk management
are right, so the verdict never demands a high hit rate. It scales confidence and position size instead.
"""
from __future__ import annotations

import math

import numpy as np

from .compute import ridge_fit, ridge_predict

PPY = {"5minute": 252 * 78, "10minute": 252 * 39, "30minute": 252 * 13, "hour": 252 * 7, "day": 252}
COST_BPS = 2.0  # per unit of position change, charged in the OOS strategy returns
MIN_BARS = 120
MIN_OOS = 60


# ---------------------------------------------------------------- indicators
def ema(x, n):
    x = np.asarray(x, dtype=float)
    out = np.empty_like(x)
    a = 2 / (n + 1)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def rsi_series(c, n=14):
    """Wilder RSI per bar (NaN until n bars exist)."""
    c = np.asarray(c, dtype=float)
    out = np.full(len(c), np.nan)
    if len(c) <= n:
        return out
    d = np.diff(c)
    up, dn = np.clip(d, 0, None), np.clip(-d, 0, None)
    au, ad = up[:n].mean(), dn[:n].mean()
    for i in range(n, len(d) + 1):
        if i > n:
            au = (au * (n - 1) + up[i - 1]) / n
            ad = (ad * (n - 1) + dn[i - 1]) / n
        out[i] = 100.0 if ad == 0 else 100 - 100 / (1 + au / ad)
    return out


def macd_series(c, fast=12, slow=26, signal=9):
    line = ema(c, fast) - ema(c, slow)
    sig = ema(line, signal)
    return line, sig, line - sig


def zscore_series(c, n=20):
    c = np.asarray(c, dtype=float)
    out = np.zeros(len(c))
    for i in range(n - 1, len(c)):
        w = c[i - n + 1:i + 1]
        sd = w.std(ddof=1)
        out[i] = (c[i] - w.mean()) / sd if sd else 0.0
    return out


def rvol_series(v, n=20):
    """Relative volume: this bar's volume over the mean of the previous n bars."""
    v = np.asarray(v, dtype=float)
    out = np.ones(len(v))
    for i in range(n, len(v)):
        base = v[i - n:i].mean()
        out[i] = v[i] / base if base > 0 else 1.0
    return out


def realized_vol(r, ppy, n=None):
    r = np.asarray(r, dtype=float)[-n:] if n else np.asarray(r, dtype=float)
    return float(r.std(ddof=1) * math.sqrt(ppy)) if len(r) > 2 else None


def garch11(r, ppy):
    """GARCH(1,1) with variance targeting, fitted by Gaussian likelihood over a parameter grid (vectorised, robust).

    Returns the one-step-ahead volatility forecast, its annualised value, persistence and the vol ratio against the
    long-run level (>1 means volatility is expanding)."""
    r = np.asarray(r, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 60:
        return None
    r = r - r.mean()
    var = float(r.var())
    if var <= 0:
        return None
    aa, bb = np.meshgrid(np.arange(0.02, 0.32, 0.02), np.arange(0.50, 0.99, 0.02))
    keep = (aa + bb) < 0.999
    aa, bb = aa[keep], bb[keep]
    omega = var * (1 - aa - bb)
    s2 = np.full(aa.shape, var)
    ll = np.zeros(aa.shape)
    for x in r:
        ll -= 0.5 * (np.log(s2) + x * x / s2)
        s2 = omega + aa * x * x + bb * s2
    k = int(np.argmax(ll))
    nxt = float(math.sqrt(s2[k]))
    return {"alpha": float(aa[k]), "beta": float(bb[k]), "persistence": float(aa[k] + bb[k]),
            "sigma_next": nxt, "vol_ann": nxt * math.sqrt(ppy), "long_run_ann": math.sqrt(var * ppy),
            "vol_ratio": nxt / math.sqrt(var)}


# ---------------------------------------------------------------- features and splits
def build_features(c, v, h=1):
    """(X, y, X_live, first_index). Row i uses bars <= i; y[i] is the log return from bar i to bar i+h."""
    c, v = np.asarray(c, dtype=float), np.asarray(v, dtype=float)
    n = len(c)
    r = np.r_[0.0, np.diff(np.log(c))]
    rsi = rsi_series(c)
    _, _, hist = macd_series(c)
    z = zscore_series(c)
    rv = rvol_series(v)
    start = 30
    rows = []
    for i in range(start, n):
        w = r[i - 19:i + 1]
        sd = w.std(ddof=1) or 1e-9
        rows.append([r[i] / sd, r[i - 5:i + 1].sum() / sd, w.sum() / sd, sd,
                     z[i], (rsi[i] - 50) / 50, hist[i] / (c[i] * sd), math.log(max(rv[i], 1e-3))])
    X = np.array(rows)
    y = np.array([math.log(c[i + h] / c[i]) for i in range(start, n - h)])
    return X[:len(y)], y, X[-1], start


def purged_walk_forward(n, folds=5, horizon=1, embargo=1, min_train=80):
    """Expanding-window splits with a purge gap. Yields (train_idx, test_idx); train labels never reach the test block."""
    first = max(min_train + horizon + embargo, n // 2)
    edges = np.linspace(first, n, folds + 1, dtype=int)
    for a, b in zip(edges[:-1], edges[1:]):
        train_end = a - horizon - embargo
        if train_end >= min_train and b > a:
            yield np.arange(0, train_end), np.arange(a, b)


def _standardise(train, *others):
    mu, sd = train.mean(0), train.std(0) + 1e-12
    return [(m - mu) / sd for m in (train,) + others]


# ---------------------------------------------------------------- model metrics
def _rank(x):
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x))
    ranks[order] = np.arange(len(x), dtype=float)
    xs = np.asarray(x)[order]
    i = 0
    while i < len(xs):  # average ranks over ties
        j = i
        while j + 1 < len(xs) and xs[j + 1] == xs[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j) / 2
        i = j + 1
    return ranks


def spearman_ic(p, a):
    if len(p) < 3 or np.std(p) == 0 or np.std(a) == 0:
        return 0.0
    return float(np.corrcoef(_rank(p), _rank(a))[0, 1])


def auc_roc(prob, up):
    """Area under the ROC curve via the rank (Mann-Whitney) statistic."""
    pos = int(up.sum())
    neg = len(up) - pos
    if pos == 0 or neg == 0:
        return None
    ranks = _rank(prob) + 1
    return float((ranks[up == 1].sum() - pos * (pos + 1) / 2) / (pos * neg))


def log_loss(prob, up):
    p = np.clip(prob, 1e-6, 1 - 1e-6)
    return float(-(up * np.log(p) + (1 - up) * np.log(1 - p)).mean())


def logit_fit(X, y, l2=2.0, iters=30):
    A = np.c_[np.ones(len(X)), X]
    w = np.zeros(A.shape[1])
    pen = np.diag(np.r_[0.0, np.ones(A.shape[1] - 1)]) * l2
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(A @ w, -30, 30)))
        g = A.T @ (p - y) + pen @ w
        H = (A.T * (p * (1 - p) + 1e-6)) @ A + pen
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-7:
            break
    return w


def logit_prob(w, X):
    return 1 / (1 + np.exp(-np.clip(w[0] + X @ w[1:], -30, 30)))


def perf(returns, ppy):
    """Sharpe, Sortino, Max Drawdown (fraction, <=0) and Profit Factor of a per-bar return series."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 5:
        return None
    sd = r.std(ddof=1)
    down = math.sqrt(float((np.minimum(r, 0) ** 2).mean()))
    curve = np.cumprod(1 + r)
    peak = np.maximum.accumulate(np.r_[1.0, curve])[1:]
    gains, losses = r[r > 0].sum(), -r[r < 0].sum()
    return {"sharpe": float(r.mean() / sd * math.sqrt(ppy)) if sd else 0.0,
            "sortino": float(r.mean() / down * math.sqrt(ppy)) if down else None,
            "max_dd": float((curve / peak - 1).min()),
            "profit_factor": float(gains / losses) if losses else None,
            "total_return": float(curve[-1] - 1), "n": int(len(r))}


def walk_forward(c, v, h=1, folds=5, alpha=10.0):
    """Purged walk-forward OOS evaluation. Returns metrics plus the live prediction from a model fitted on all
    purged history, or {'error': ...} when there is too little data."""
    X, y, x_live, _ = build_features(c, v, h)
    n = len(y)
    if n < MIN_BARS:
        return {"error": f"need >= {MIN_BARS} usable bars", "n": n}
    P, A, PU = [], [], []
    for tr, te in purged_walk_forward(n, folds, horizon=h):
        Xtr, Xte = _standardise(X[tr], X[te])
        w = ridge_fit(Xtr, y[tr], alpha)
        pred = np.asarray(ridge_predict(w, Xte), dtype=float)
        up_tr = (y[tr] > 0).astype(float)
        pu = logit_prob(logit_fit(Xtr, up_tr), Xte) if 0 < up_tr.mean() < 1 else np.full(len(te), 0.5)
        P.append(pred)
        A.append(y[te])
        PU.append(pu)
    if not P:
        return {"error": "no purged folds", "n": n}
    p, a, pu = np.concatenate(P), np.concatenate(A), np.concatenate(PU)
    if len(a) < MIN_OOS:
        return {"error": "too few out-of-sample bars", "n": int(len(a))}
    up = (a > 0).astype(float)
    rmse, naive = float(np.sqrt(((p - a) ** 2).mean())), float(np.sqrt((a ** 2).mean()))
    base = float(np.clip(up.mean(), 1e-6, 1 - 1e-6))
    pos = (p > 0).astype(float)
    net = pos * a - COST_BPS / 1e4 * np.abs(np.diff(np.r_[0.0, pos]))
    # live prediction: train on everything except the last h labels' overlap, i.e. the same purge rule
    keep = max(n - h - 1, 40)
    Xs, xl = _standardise(X[:keep], x_live[None, :])
    w = ridge_fit(Xs, y[:keep], alpha)
    up_all = (y[:keep] > 0).astype(float)
    p_up = float(logit_prob(logit_fit(Xs, up_all), xl)[0]) if 0 < up_all.mean() < 1 else 0.5
    return {"n_oos": int(len(a)), "folds": len(P), "rmse": rmse, "rmse_naive": naive,
            "rmse_vs_naive": rmse / naive if naive else None,
            "hit_rate": float((np.sign(p) == np.sign(a)).mean()), "ic": spearman_ic(p, a),
            "auc": auc_roc(pu, up), "log_loss": log_loss(pu, up),
            "log_loss_base": float(-(base * math.log(base) + (1 - base) * math.log(1 - base))),
            "_net": net, "pred_ret": float(ridge_predict(w, xl)[0]), "p_up": p_up}


# ---------------------------------------------------------------- per-symbol analysis and verdict
def analyze(bars, interval="5minute", h=1, mode="day"):
    """Full suite for one symbol from OHLCV bars. `mode` is day, options or long and only shapes the verdict."""
    ppy = PPY.get(interval, 252)
    c = np.array([b["close"] for b in bars if b.get("close") is not None], dtype=float)
    v = np.array([b.get("volume") or 0 for b in bars if b.get("close") is not None], dtype=float)
    if len(c) < MIN_BARS:
        return {"error": f"only {len(c)} bars", "n": int(len(c)), "mode": mode, "interval": interval}
    r = np.diff(np.log(c))
    rsi = rsi_series(c)
    line, sig, hist = macd_series(c)
    out = {"mode": mode, "interval": interval, "n": int(len(c)), "price": float(c[-1]),
           "rsi": float(rsi[-1]), "macd": float(line[-1]), "macd_signal": float(sig[-1]), "macd_hist": float(hist[-1]),
           "zscore": float(zscore_series(c)[-1]), "rvol": float(rvol_series(v)[-1]),
           "rv_ann": realized_vol(r, ppy), "rv_recent_ann": realized_vol(r, ppy, 20),
           "garch": garch11(r, ppy)}
    wf = walk_forward(c, v, h)
    net = wf.pop("_net", None)
    if "error" not in wf:
        wf["perf"] = perf(net, ppy)
    out["wf"] = wf
    out.update(verdict(out, c, r))
    return out


def verdict(m, c, r):
    """score in [-1, 1], edge flag, size multiplier, veto and reasons. Descriptive input to the agents; never an order."""
    wf, g = m.get("wf") or {}, m.get("garch") or {}
    sd = float(np.std(r[-20:], ddof=1)) if len(r) > 21 else 0.0
    sd = sd or 1e-9
    macd_term = math.tanh(m["macd_hist"] / (m["price"] * sd) * 1.5)
    rsi = m["rsi"]
    rsi_term = -0.5 * math.tanh((rsi - 50) / 20) if abs(rsi - 50) > 20 else 0.0
    ok = "error" not in wf
    edge = bool(ok and wf["ic"] > 0 and (wf["auc"] or 0.5) > 0.5 and wf["hit_rate"] > 0.5)
    quality = 0.0
    model_term = 0.0
    if ok:
        quality = 0.5 * min(max(((wf["auc"] or 0.5) - 0.5) / 0.05, 0), 1) + 0.5 * min(max(wf["ic"] / 0.05, 0), 1)
        model_term = float(np.clip((wf["p_up"] - 0.5) / 0.1, -1, 1)) * (0.25 + 0.75 * quality)
    mode = m["mode"]
    w = {"day": (0.40, 0.40, 0.20), "options": (0.30, 0.30, 0.40), "long": (0.35, 0.45, 0.20)}.get(mode, (0.4, 0.4, 0.2))
    z_term = -math.tanh(m["zscore"] / 2.5)  # stretched vs its 20-bar mean leans toward reverting
    score = w[0] * model_term + w[1] * macd_term + w[2] * (0.5 * rsi_term + 0.5 * z_term)
    reasons = []
    ratio = g.get("vol_ratio")
    if ratio and ratio > 1.5:
        score -= 0.15
        reasons.append(f"GARCH vol expanding x{ratio:.1f}")
    if ok and not edge:
        reasons.append("no out-of-sample edge (IC/AUC/hit rate)")
    if ok and edge:
        reasons.append(f"OOS edge: IC {wf['ic']:+.3f}, AUC {wf['auc']:.3f}, hit {wf['hit_rate']:.1%}")
    if m["rvol"] >= 1.5:
        reasons.append(f"RVOL {m['rvol']:.1f}x")
    score = float(np.clip(score, -1, 1))
    size = float(np.clip(1 + 0.6 * score * (0.4 + 0.6 * quality), 0.5, 1.3))
    if ratio and ratio > 1.8:
        size = min(size, 0.7)
    floor = {"options": -0.5}.get(mode, -0.4)
    return {"score": score, "edge": edge, "size_mult": size, "veto": score <= floor,
            "model_quality": float(quality), "reasons": reasons}


# ---------------------------------------------------------------- account-level evaluation
def account_performance(equity_log, trades, ppy=252):
    """Sharpe, Sortino, Max DD and Profit Factor of the paper account: daily equity returns, closed-trade P&L."""
    by_day = {}
    for ts, eq in equity_log:
        by_day[str(ts)[:10]] = float(eq)
    eq = np.array([by_day[d] for d in sorted(by_day)], dtype=float)
    out = {"days": int(len(eq))}
    if len(eq) >= 3:
        out.update(perf(np.diff(eq) / eq[:-1], ppy) or {})
    realized = np.array([t["realized"] for t in trades if t.get("realized") is not None and t.get("side") == "sell"],
                        dtype=float)
    if len(realized):
        wins, loss = realized[realized > 0].sum(), -realized[realized < 0].sum()
        out["trade_profit_factor"] = float(wins / loss) if loss else None
        out["trade_win_rate"] = float((realized > 0).mean())
        out["closed_trades"] = int(len(realized))
    return out
