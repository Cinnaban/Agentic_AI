"""Single-trade-per-day selection for the growth (long) agent and the day agent (paper only).

Each of those two agents gets ONE entry per day, taken early in the open once the foundations agree. Candidates
are ranked on four pillars (weights sum to 1):

  prediction  - walk-forward quant signal / regression IC and the 5-day statistical outlook
  sentiment   - analyst mix and mean-target upside
  financials  - valuation (P/E), profitability, size and dividend, from Robinhood fundamentals
  trend       - price vs MA20/MA50, MA20 vs MA50 and 60-day slope

The options agent is not governed by this module and may trade all day.
"""
from __future__ import annotations

import numpy as np

from .robinhood.review import _closes, _f, _projection, _rsi, _sentiment

WEIGHTS = {"prediction": 0.30, "sentiment": 0.25, "financials": 0.15, "trend": 0.30}
ENTRY_START, ENTRY_END = (9, 35), (10, 30)


def _clip(x, lo=-1.0, hi=1.0):
    return max(lo, min(hi, x))


def trend_score(closes, price):
    c = np.asarray(closes, dtype=float)
    if len(c) < 50 or not price:
        return None
    ma20, ma50 = float(c[-20:].mean()), float(c[-50:].mean())
    parts = [_clip((price / ma20 - 1) / 0.05), _clip((price / ma50 - 1) / 0.08), _clip((ma20 / ma50 - 1) / 0.04)]
    proj = _projection(c)
    if proj:
        parts.append(_clip(proj["trend_ann"] / 0.5))
    return float(np.mean(parts))


def prediction_score(closes, quant=None):
    parts = []
    if quant and "error" not in quant and quant.get("signal_score") is not None:
        s = _clip(quant["signal_score"] / 0.5)
        ic = (quant.get("scorecard") or {}).get("ic")
        parts.append(s * (0.5 + 0.5 * _clip((ic or 0) / 0.2, 0.0, 1.0)))
    proj = _projection(np.asarray(closes, dtype=float)) if len(closes) >= 40 else None
    if proj and proj["band5"]:
        parts.append(_clip(proj["exp5"] / proj["band5"]))
    return float(np.mean(parts)) if parts else None


def sentiment_score(rating, price):
    target = _f((rating or {}).get("mean_price_target"))
    upside = (target / price - 1) if target and price else None
    return _sentiment(rating, upside, None, None)


def financial_score(f):
    """Valuation/quality score for a stock; ETFs are scored on yield only (no single-company fundamentals)."""
    if not f:
        return None
    pe, cap, yld = _f(f.get("pe_ratio")), _f(f.get("market_cap")), _f(f.get("dividend_yield"))
    etf = "investment trusts" in (f.get("industry") or "").lower() or (f.get("sector") or "") == "Miscellaneous"
    parts = []
    if not etf:
        parts.append(-0.3 if pe is None or pe <= 0 else _clip((30 - pe) / 30))
        if cap:
            parts.append(_clip((np.log10(cap) - 9.5) / 2.0))
    if yld is not None:
        parts.append(_clip(yld / 4.0, 0.0, 0.5))
    return float(np.mean(parts)) if parts else None


def composite(pillars):
    """Weighted mean over the pillars that have data; reports how much of the weight had data."""
    have = {k: v for k, v in pillars.items() if v is not None}
    w = sum(WEIGHTS[k] for k in have)
    if not w:
        return None, 0.0
    return sum(WEIGHTS[k] * v for k, v in have.items()) / w, w


def evaluate(symbols, data, quotes, quants=None, bars=None):
    """{sym: {score, coverage, pillars, rsi, vol}} for each symbol that has a live quote and price history."""
    quants = quants or {}
    syms = [s for s in symbols if (quotes.get(s) or {}).get("price")]
    if not syms:
        return {}
    bars = bars if bars is not None else data.bars(syms, "day", 150, ttl=1800)
    try:
        ratings = data.ratings(syms)
    except Exception:
        ratings = {}
    try:
        funds = data.fundamentals(syms)
    except Exception:
        funds = {}
    out = {}
    for s in syms:
        px = quotes[s]["price"]
        closes = _closes(bars.get(s, []))
        if len(closes) < 50:
            continue
        pillars = {"prediction": prediction_score(closes, quants.get(s)),
                   "sentiment": sentiment_score((ratings or {}).get(s), px),
                   "financials": financial_score((funds or {}).get(s)),
                   "trend": trend_score(closes, px)}
        score, cov = composite(pillars)
        if score is None:
            continue
        out[s] = {"score": float(score), "coverage": cov, "pillars": pillars, "rsi": _rsi(closes),
                  "vol": (_projection(closes) or {}).get("vol_ann"), "ma50": float(closes[-50:].mean())}
    return out


def why(e):
    p = e["pillars"]
    names = {"prediction": "pred", "sentiment": "sent", "financials": "fin", "trend": "trend"}
    return f"score {e['score']:+.2f} (" + ", ".join(f"{names[k]} {p[k]:+.2f}" for k in names if p[k] is not None) + ")"


def in_entry_window(hm):
    return ENTRY_START <= hm < ENTRY_END
