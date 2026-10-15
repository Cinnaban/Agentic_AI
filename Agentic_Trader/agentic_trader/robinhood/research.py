"""Research snapshots built from Robinhood data: quote + analyst consensus + earnings timing.

Deliberately contains no account, position or portfolio information.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .data import RobinhoodData, shared


def consensus(r: dict | None) -> str | None:
    if not r:
        return None
    b, h, s = (r.get("num_buy_ratings") or 0), (r.get("num_hold_ratings") or 0), (r.get("num_sell_ratings") or 0)
    n = b + h + s
    return f"{b / n:.0%} Buy / {h / n:.0%} Hold / {s / n:.0%} Sell ({n} analysts)" if n else None


def snapshot(symbols: list[str], data: RobinhoodData | None = None, earnings_days: int = 14) -> dict[str, dict]:
    d = data or shared()
    syms = [s.upper() for s in symbols]
    quotes = d.quotes(syms)
    try:
        ratings = d.ratings(syms)
    except Exception:
        ratings = {}
    try:
        cal = {}
        for e in d.earnings(earnings_days):
            if e.get("symbol") in syms:
                cal.setdefault(e["symbol"], e)
    except Exception:
        cal = {}
    out = {}
    for s in syms:
        q, r, e = quotes.get(s), ratings.get(s), cal.get(s)
        out[s] = {"quote": q, "ratings": r, "consensus": consensus(r), "next_earnings": (e or {}).get("report", {}).get("date"),
                  "upside_to_target": ((_f(r.get("mean_price_target")) / q["price"] - 1)
                                       if r and q and q.get("price") and _f(r.get("mean_price_target")) else None)}
    return out


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def describe(sym: str, s: dict) -> str:
    q = s["quote"]
    if not q or not q["price"]:
        return f"{sym}: no live quote"
    parts = [f"{sym} ${q['price']:,.2f}"]
    if q["change_pct"] is not None:
        parts.append(f"{q['change_pct']:+.2%} vs prev close")
    if q["session"] == "extended":
        parts.append("(extended hours)")
    if s["consensus"]:
        parts.append(f"analysts: {s['consensus']}")
    if s["upside_to_target"] is not None:
        parts.append(f"mean target {s['upside_to_target']:+.1%} vs price")
    if s["next_earnings"]:
        parts.append(f"earnings {s['next_earnings']}")
    as_of = q["as_of"].astimezone(timezone.utc).strftime("%H:%M:%SZ") if q.get("as_of") else "n/a"
    return "; ".join(parts) + f" [as of {as_of}]"
