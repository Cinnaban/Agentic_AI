"""Intraday day-trading strategy (paper only): trend-following long entries sized by volatility, with a hard stop.

Reads 5-minute bars (VWAP, EMA9/EMA21, RSI14, ATR14, opening range, relative volume) against the daily trend
(MA20 / MA50, daily ATR). Two long setups, both requiring an up-trend and price above VWAP:

  ORB       - 5-minute close above the opening-range high (first 30 minutes) on above-average volume
  PULLBACK  - dip to VWAP/EMA21 inside an up-trend, then a 5-minute close back above EMA9 with RSI recovering

Risk is defined at entry: stop = 2.5 x 5-minute ATR (clamped), target = 2R, stop moves to break-even at +1R and then
trails 1R behind the high. Position size is set so a stop-out loses ~`risk_pct` of equity. No shorting, no leverage.
"""
from __future__ import annotations

import numpy as np

OR_BARS = 6  # 30 minutes of 5-minute bars


def ema(x, n):
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return x
    a, out = 2 / (n + 1), np.empty(len(x))
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def rsi(c, n=14):
    c = np.asarray(c, dtype=float)
    if len(c) <= n:
        return None
    d = np.diff(c)
    up, dn = np.clip(d, 0, None), np.clip(-d, 0, None)
    au, ad = up[:n].mean(), dn[:n].mean()
    for i in range(n, len(d)):
        au, ad = (au * (n - 1) + up[i]) / n, (ad * (n - 1) + dn[i]) / n
    return 100.0 if ad == 0 else float(100 - 100 / (1 + au / ad))


def atr(h, l, c, n=14):
    h, l, c = (np.asarray(v, dtype=float) for v in (h, l, c))
    if len(c) < 2:
        return None
    tr = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
    return float(tr[-n:].mean()) if len(tr) else None


def split_today(bars, day):
    """(history, today) lists of bars; `day` is a date in the bars' timezone (ET)."""
    from .paper_live import ET
    hist, today = [], []
    for b in bars:
        if not b.get("close") or not b.get("ts"):
            continue
        (today if b["ts"].astimezone(ET).date() == day else hist).append(b)
    return hist, today


def analyze(bars5, daily, price, day):
    """Indicator snapshot for one symbol, or None when there is not enough data."""
    hist, today = split_today(bars5, day)
    if len(today) < 8 or len(hist) + len(today) < 40 or len(daily) < 50 or not price:
        return None
    allb = hist[-60:] + today
    close = np.array([b["close"] for b in allb])
    high = np.array([b["high"] or b["close"] for b in allb])
    low = np.array([b["low"] or b["close"] for b in allb])
    tc = np.array([b["close"] for b in today])
    th = np.array([b["high"] or b["close"] for b in today])
    tl = np.array([b["low"] or b["close"] for b in today])
    tv = np.array([float(b["volume"] or 0) for b in today])
    typical = (th + tl + tc) / 3
    vwap = float((typical * tv).sum() / tv.sum()) if tv.sum() else float(tc.mean())
    e9, e21 = ema(close, 9), ema(close, 21)
    a5 = atr(high, low, close, 14)
    dc = np.array([b["close"] for b in daily if b.get("close")], dtype=float)
    dh = np.array([b.get("high") or b["close"] for b in daily if b.get("close")], dtype=float)
    dl = np.array([b.get("low") or b["close"] for b in daily if b.get("close")], dtype=float)
    d_atr = atr(dh, dl, dc, 14)
    n_or = min(OR_BARS, len(today))
    prior_v = tv[:-1][-20:]
    return {
        "price": price, "vwap": vwap, "ema9": float(e9[-1]), "ema21": float(e21[-1]), "ema9_prev": float(e9[-2]),
        "rsi": rsi(close), "rsi_prev": rsi(close[:-1]), "atr5": a5, "atr5_pct": (a5 / price) if a5 else None,
        "daily_atr_pct": (d_atr / dc[-1]) if d_atr else None,
        "or_high": float(th[:n_or].max()), "or_low": float(tl[:n_or].min()), "or_done": len(today) >= OR_BARS,
        "last_close": float(tc[-1]), "last_low": float(tl[-3:].min()),
        "rvol": float(tv[-1] / prior_v.mean()) if len(prior_v) and prior_v.mean() else None,
        "day_open": float(today[0]["open"] or tc[0]), "day_high": float(th.max()), "day_low": float(tl.min()),
        "daily_ma20": float(dc[-20:].mean()), "daily_ma50": float(dc[-50:].mean()), "prev_close": float(dc[-1]),
        "above_vwap_share": float((tc > ((th + tl + tc) / 3)).mean()),
    }


def daily_bias(m):
    """-1..+1 read of the daily trend: price vs MA20/MA50, MA20 vs MA50 and where it sits against yesterday."""
    p = m["price"]
    return float(np.mean([
        np.clip((p / m["daily_ma20"] - 1) / 0.05, -1, 1), np.clip((p / m["daily_ma50"] - 1) / 0.08, -1, 1),
        np.clip((m["daily_ma20"] / m["daily_ma50"] - 1) / 0.04, -1, 1), np.clip((p / m["prev_close"] - 1) / 0.02, -1, 1)]))


def setup(m, cfg):
    """('ORB'|'PULLBACK', strength 0..1) when an entry is valid right now, else (None, reason)."""
    p, a = m["price"], m["atr5"]
    if not a or not m["atr5_pct"]:
        return None, "no volatility data"
    if not (cfg.min_daily_atr <= (m["daily_atr_pct"] or 0) <= cfg.max_daily_atr):
        return None, f"daily range {(m['daily_atr_pct'] or 0):.1%} outside {cfg.min_daily_atr:.1%}-{cfg.max_daily_atr:.1%}"
    if daily_bias(m) < cfg.min_bias:
        return None, f"daily trend bias {daily_bias(m):+.2f}"
    if not (m["ema9"] > m["ema21"] and p > m["vwap"]):
        return None, "intraday trend not up (EMA9<=EMA21 or below VWAP)"
    if (m["rsi"] or 50) >= cfg.max_rsi:
        return None, f"overbought (RSI {m['rsi']:.0f})"
    if p > m["vwap"] + 2.5 * a * 1.0 and p > m["ema21"] + 3.5 * a:
        return None, "extended above VWAP/EMA21; waiting for a pullback"
    if m["or_done"] and m["last_close"] > m["or_high"] and (m["rvol"] or 0) >= cfg.min_rvol and p - m["or_high"] <= 2.0 * a:
        strength = min(1.0, 0.5 + 0.25 * min(2.0, (m["rvol"] or 1) - 1) + 0.25 * (m["above_vwap_share"] - 0.5))
        return ("ORB", float(max(0.1, strength))), f"close above opening-range high {m['or_high']:.2f}, rvol {(m['rvol'] or 0):.1f}"
    dipped = m["last_low"] <= max(m["vwap"], m["ema21"]) + 0.3 * a
    turning = m["last_close"] > m["ema9"] and (m["rsi"] or 50) > (m["rsi_prev"] or 50) and 38 <= (m["rsi"] or 50) <= 65
    if dipped and turning:
        return ("PULLBACK", float(min(1.0, 0.45 + 0.3 * max(0.0, daily_bias(m))))), \
            f"pullback to VWAP/EMA21 holding, RSI {m['rsi']:.0f} turning up"
    return None, "no trigger"


def plan_trade(m, cfg, equity, free_cash, scale=1.0):
    """Entry, stop, target and size for a valid setup. Size risks cfg.risk_pct of equity at the stop."""
    p = m["price"]
    stop_pct = float(np.clip(cfg.atr_stop_mult * m["atr5_pct"], cfg.stop_min, cfg.stop_max))
    stop = p * (1 - stop_pct)
    structure = m["last_low"] - 0.25 * m["atr5"]
    if p * (1 - cfg.stop_max) <= structure < p * (1 - cfg.stop_min):  # tuck the stop under real structure when it is sensible
        stop, stop_pct = structure, 1 - structure / p
    risk_usd = equity * cfg.risk_pct * scale
    notional = min(risk_usd / stop_pct, equity * cfg.max_position_pct, free_cash)
    return {"stop": stop, "stop_pct": stop_pct, "target": p * (1 + cfg.target_r * stop_pct),
            "risk_per_share": p - stop, "notional": notional, "risk_usd": notional * stop_pct}


def manage(pos, m, price, hm, cfg):
    """Exit decision for an open day position: (reason|None, new_stop|None). Never lowers the stop."""
    entry, risk = pos["avg"], pos.get("r_per_share") or pos["avg"] * (pos.get("stop_pct") or 0.01)
    stop = pos.get("stop_px") or entry - risk
    pos["high"] = max(pos.get("high") or entry, price)
    r_now = (price - entry) / risk if risk else 0.0
    r_high = (pos["high"] - entry) / risk if risk else 0.0
    new_stop = stop
    if r_high >= cfg.breakeven_r:
        new_stop = max(new_stop, entry + 0.05 * risk)
    if r_high >= cfg.trail_start_r:
        new_stop = max(new_stop, pos["high"] - cfg.trail_r * risk)
    if price <= new_stop:
        kind = "stop loss" if new_stop <= entry - 0.5 * risk else "trailing stop" if new_stop > entry + 0.5 * risk else "break-even stop"
        return f"{kind} ({r_now:+.1f}R)", new_stop
    if price >= pos.get("target_px", float("inf")):
        return f"profit target {r_now:+.1f}R", new_stop
    if m and m["ema9"] < m["ema21"] and price < m["vwap"] and r_now > -0.5:
        return f"trend failed (EMA9<EMA21, below VWAP) {r_now:+.1f}R", new_stop
    if pos.get("opened_hm") is not None and hm is not None:
        held = (hm[0] * 60 + hm[1]) - pos["opened_hm"]
        if held >= cfg.stall_min and r_now < 0.3:
            return f"stalled {held} min without progress ({r_now:+.1f}R)", new_stop
    return None, new_stop
