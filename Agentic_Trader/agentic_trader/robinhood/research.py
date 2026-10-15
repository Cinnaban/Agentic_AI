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


def quote_table(sym: str, s: dict, m: dict | None = None) -> str:
    """Live quote as a metric/value table (market data only)."""
    from ..tables import kv_table
    q = s["quote"]
    if not q or not q.get("price"):
        return ""
    as_of = q["as_of"].astimezone(timezone.utc).strftime("%H:%M:%SZ") if q.get("as_of") else "n/a"
    pairs = [("Price", f"${q['price']:,.2f}" + (" (ext. hrs)" if q.get("session") == "extended" else "")),
             ("Change vs prev close", f"{q['change_pct']:+.2%}" if q.get("change_pct") is not None else None),
             ("Analysts", s.get("consensus")),
             ("Target vs price", f"{s['upside_to_target']:+.1%}" if s.get("upside_to_target") is not None else None),
             ("Next earnings", s.get("next_earnings"))]
    if m and "error" not in m:
        sc = m.get("scorecard", {})
        pairs += [("Quant signal", f"{m['signal_score']:+.2f}"), ("RSI14", f"{m.get('rsi14') or 0:.0f}"),
                  ("VWAP deviation", f"{m['vwap_dev_pct']:+.2%}"), ("Realized vol (ann.)", f"{m['realized_vol_ann']:.0%}"),
                  ("Beta vs SPY", f"{m.get('beta_vs_spy') or 0:.2f}"),
                  ("Walk-forward IC / hit rate", f"{sc.get('ic', 0):+.2f} / {sc.get('hit_rate', 0):.0%}")]
    pairs.append(("As of", as_of))
    return kv_table(pairs, title=f"{sym} live quote (Robinhood, real-time)")
