"""Growth-team members from the tactical asset-allocation literature, scored per ETF.

  dual momentum  Antonacci, "Dual Momentum Investing": relative strength (12-month return ranked across the ETFs)
                 plus absolute momentum (the 12-month return must beat the cash rate).
  trend (10-mo)  Faber, "A Quantitative Approach to Tactical Asset Allocation": price against its 200-day average.

Both are slower than the 50-day rule they back up. On this universe over the last ~4 years the 200-day rule
whipsawed less than the 50-day rule, which is why a MA50 break now needs confirmation before the growth agent sells.
"""
from __future__ import annotations

import numpy as np

from .factor_tilt import rank01

MIN_BARS = 253


def _clip(x, lo=-1.0, hi=1.0):
    return max(lo, min(hi, x))


def members(closes_by_sym, prices, cash_rate):
    """{sym: {"score": -1..1, "dual": .., "trend": .., "r12": .., "above200": bool, "abs_ok": bool, "bearish": bool}}"""
    r12 = {}
    for s, c in closes_by_sym.items():
        c = np.asarray(c, dtype=float)
        if len(c) >= MIN_BARS:
            r12[s] = float(c[-1] / c[-MIN_BARS] - 1)
    if not r12:
        return {}
    syms = sorted(r12)
    rel = dict(zip(syms, rank01([r12[s] for s in syms])))
    out = {}
    for s in syms:
        c = np.asarray(closes_by_sym[s], dtype=float)
        px = prices.get(s) or float(c[-1])
        ma200 = float(c[-200:].mean())
        abs_ok = r12[s] > cash_rate
        dual = (rel[s] * 2 - 1) if abs_ok else min(rel[s] * 2 - 1, -0.5)
        trend = _clip((px / ma200 - 1) / 0.05)
        out[s] = {"score": float((dual + trend) / 2), "dual": float(dual), "trend": float(trend), "r12": r12[s],
                  "above200": px > ma200, "abs_ok": abs_ok, "bearish": (not abs_ok) and px <= ma200}
    return out
