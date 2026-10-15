"""/review: per-holding analysis across every readable account (stocks, ETFs, IRA), or for given symbols.

Read-only. Fundamentals, ratings, quotes and daily bars come from the Robinhood MCP market-data path; account holdings
come from account.py. ETF constituents are not exposed by the MCP, so they are fetched from yfinance when available.
Predictions are simple statistical projections, not advice.
"""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

from . import account
from .data import shared

BENCH = "SPY"
HISTORY_DAYS = 420


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _money(x):
    return "n/a" if x is None else f"${x:,.2f}"


def _big(x):
    if not x:
        return "n/a"
    for div, unit in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if x >= div:
            return f"${x / div:.2f}{unit}"
    return f"${x:,.0f}"


def holdings() -> dict[str, dict]:
    """symbol -> {qty, cost_total, where: {account label: qty}} merged across all analysis accounts."""
    out: dict[str, dict] = defaultdict(lambda: {"qty": 0.0, "cost": 0.0, "where": {}})
    for acct in account.analysis_accounts():
        for p in account.positions(acct["account_number"]):
            q = _f(p.get("quantity")) or 0.0
            if q <= 0:
                continue
            h = out[p["symbol"]]
            h["qty"] += q
            h["cost"] += q * (_f(p.get("average_buy_price")) or 0.0)
            h["where"][account.label(acct)] = h["where"].get(account.label(acct), 0.0) + q
    return dict(out)


def _fundamentals(syms):
    data = shared()._call("get_equity_fundamentals", {"symbols": syms}, 3600)
    return {r["symbol"]: r for r in data.get("results", []) if r.get("symbol")}


def _closes(bars):
    return np.array([b["close"] for b in bars if b.get("close")], dtype=float)


def _beta(c, bench):
    n = min(len(c), len(bench))
    if n < 60:
        return None
    r, m = np.diff(np.log(c[-n:])), np.diff(np.log(bench[-n:]))
    var = np.var(m, ddof=1)
    return float(np.cov(r, m)[0, 1] / var) if var > 0 else None


def _projection(c):
    """5-trading-day outlook from a 60-day log-linear trend, momentum and realized vol."""
    if len(c) < 40:
        return None
    y = np.log(c[-60:])
    x = np.arange(len(y))
    slope, icpt = np.polyfit(x, y, 1)
    fit = slope * x + icpt
    ss_res, ss_tot = np.sum((y - fit) ** 2), np.sum((y - y.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    vol_d = float(np.std(np.diff(np.log(c[-60:]))))
    drift5 = float(slope * 5 * max(r2, 0.0))  # shrink the trend by how well it fits
    return {"trend_ann": float(slope * 252), "r2": float(r2), "exp5": drift5, "band5": vol_d * math.sqrt(5),
            "vol_ann": vol_d * math.sqrt(252)}


def _sentiment(rating, upside, trend_ann, rsi):
    """-1..+1 composite of analyst mix, target upside, trend and RSI position."""
    parts = []
    if rating:
        b, h, s = (rating.get(k) or 0 for k in ("num_buy_ratings", "num_hold_ratings", "num_sell_ratings"))
        if b + h + s:
            parts.append((b - s) / (b + h + s))
    if upside is not None:
        parts.append(max(-1, min(1, upside / 0.25)))
    if trend_ann is not None:
        parts.append(max(-1, min(1, trend_ann / 0.5)))
    if rsi is not None:
        parts.append(max(-1, min(1, (50 - rsi) / 30)) * 0.5)  # contrarian, half weight
    if not parts:
        return None
    return float(np.mean(parts))


def _label(s):
    if s is None:
        return "n/a"
    return "bullish" if s > 0.25 else "bearish" if s < -0.25 else "neutral"


def _rsi(c, n=14):
    if len(c) <= n:
        return None
    d = np.diff(c[-(n * 3):])
    up, dn = np.clip(d, 0, None), np.clip(-d, 0, None)
    au, ad = up[-n:].mean(), dn[-n:].mean()
    return 100.0 if ad == 0 else float(100 - 100 / (1 + au / ad))


def _etf_holdings(sym, top=8):
    try:
        import yfinance as yf
        df = yf.Ticker(sym).funds_data.top_holdings
        return [(str(i), float(r.iloc[-1])) for i, r in df.head(top).iterrows()]
    except Exception:
        return None


def _is_etf(f):
    return "investment trusts" in (f.get("industry") or "").lower() or (f.get("sector") or "") == "Miscellaneous"


def review_symbol(sym, f, q, c, bench, rating, held, port_value):
    """Metrics for one symbol as a dict (rendered into tables by review())."""
    price = q.get("price")
    ma = {n: (float(c[-n:].mean()) if len(c) >= n else None) for n in (20, 50, 200)}
    rsi = _rsi(c)
    proj = _projection(c)
    beta = _beta(c, bench) if len(bench) else None
    target = _f((rating or {}).get("mean_price_target"))
    upside = (target / price - 1) if target and price else None
    sent = _sentiment(rating, upside, proj and proj["trend_ann"], rsi)
    etf = _is_etf(f)
    d = {"sym": sym, "kind": "ETF" if etf else (f.get("sector") or "Stock"), "etf": etf, "price": price,
         "day": q.get("change_pct"), "mcap": _f(f.get("market_cap")), "ma": ma, "rsi": rsi, "beta": beta,
         "sent": sent, "upside": upside, "target": target, "proj": proj, "pe": _f(f.get("pe_ratio")),
         "yield": _f(f.get("dividend_yield")), "div_ps": _f(f.get("dividend_per_share")),
         "freq": f.get("distribution_frequency") or "", "rating": rating,
         "hi": _f(f.get("high_52_weeks")), "lo": _f(f.get("low_52_weeks")), "held": None, "top": None}
    if held:
        val = price * held["qty"] if price else 0.0
        d["held"] = {"qty": held["qty"], "val": val, "w": (val / port_value) if port_value else None,
                     "gl": (val - held["cost"]) if held["cost"] else None,
                     "glp": (val / held["cost"] - 1) if held["cost"] else None,
                     "where": ", ".join(held["where"])}
    if etf:
        d["top"] = _etf_holdings(sym)
    return d


def _p(x, spec="+.1%"):
    return "n/a" if x is None else format(x, spec)


def _vs(m, price):
    return "n/a" if not (m and price) else f"{price / m - 1:+.1%}"


def _signal_word(d):
    ma20, ma50 = d["ma"][20], d["ma"][50]
    if not (ma20 and ma50):
        return "n/a"
    return "bull" if ma20 > ma50 else "bear"


def _tables(items):
    from ..tables import table
    out = []
    pos = [d for d in items if d["held"]]
    if pos:
        out.append(table(
            ["Symbol", "Price", "Day", "Value", "Wt", "Gain/Loss", "G/L %"],
            [[d["sym"], f"${d['price']:,.2f}" if d["price"] else "n/a", _p(d["day"], "+.1%"),
              _money(d["held"]["val"]), _p(d["held"]["w"], ".0%"),
              "n/a" if d["held"]["gl"] is None else f"{d['held']['gl']:+,.0f}", _p(d["held"]["glp"])] for d in pos],
            title="Position and gain/loss"))
    out.append(table(
        ["Symbol", "Type", "Price", "Mkt cap", "P/E", "Div yld", "Beta"],
        [[d["sym"], d["kind"][:10], f"${d['price']:,.2f}" if d["price"] else "n/a", _big(d["mcap"]).replace("$", ""),
          _p(d["pe"], ".1f"), f"{d['yield']:.2f}%" if d["div_ps"] and d["yield"] is not None else "-",
          _p(d["beta"], ".2f")] for d in items], title="Valuation and risk"))
    out.append(table(
        ["Symbol", "vs MA20", "vs MA50", "vs MA200", "RSI", "Trend"],
        [[d["sym"], _vs(d["ma"][20], d["price"]), _vs(d["ma"][50], d["price"]), _vs(d["ma"][200], d["price"]),
          "n/a" if d["rsi"] is None else f"{d['rsi']:.0f}", _signal_word(d)] for d in items],
        title="Moving averages and momentum (price vs average)"))
    out.append(table(
        ["Symbol", "Sentiment", "Analysts B/H/S", "Tgt up", "5d exp", "5d +/-"],
        [[d["sym"], _label(d["sent"]) + ("" if d["sent"] is None else f" {d['sent']:+.2f}"),
          "-" if not d["rating"] else "/".join(str(d["rating"].get(k, 0)) for k in
                                               ("num_buy_ratings", "num_hold_ratings", "num_sell_ratings")),
          _p(d["upside"]), _p(d["proj"] and d["proj"]["exp5"], "+.2%"),
          _p(d["proj"] and d["proj"]["band5"], ".1%")] for d in items],
        title="Sentiment and outlook (5 trading days, 1 sd band)"))
    divs = [d for d in items if d["div_ps"]]
    if divs:
        out.append(table(
            ["Symbol", "Per share", "Frequency", "Est/yr on your shares"],
            [[d["sym"], f"${d['div_ps']:.2f}", d["freq"] or "-",
              f"${d['div_ps'] * 4 * d['held']['qty']:.2f}" if d["held"] and d["freq"].lower().startswith("q") else "-"]
             for d in divs], aligns="lrlr", title="Dividends"))
    for d in items:
        if d["etf"]:
            top = d["top"]
            out.append(table(["Holding", "Weight"], [[n, f"{w:.1%}" if w < 1 else f"{w:.1f}%"] for n, w in top],
                             title=f"{d['sym']} top holdings") if top else f"{d['sym']} top holdings: unavailable")
    return out


def review(symbols: list[str] | None = None) -> str:
    held = holdings()
    wanted = [s.upper() for s in symbols] if symbols else sorted(held)
    if not wanted:
        return "No holdings found in the readable accounts."
    d = shared()
    quotes = d.quotes(sorted(set(wanted) | set(held)))
    total = sum((quotes.get(s, {}).get("price") or 0) * h["qty"] for s, h in held.items())
    funds = _fundamentals(wanted)
    bars = d.bars(wanted + [BENCH], "day", HISTORY_DAYS)
    bench = _closes(bars.get(BENCH, []))
    ratings = d.ratings(wanted)
    items, errors = [], []
    for s in wanted:
        try:
            items.append(review_symbol(s, funds.get(s, {}), quotes.get(s, {}), _closes(bars.get(s, [])), bench,
                                       ratings.get(s), held.get(s), total))
        except Exception as exc:
            errors.append(f"{s}: review failed ({str(exc)[:80]})")
    head = f"Review of {len(wanted)} symbol(s)" + (f", equity value {_money(total)}" if not symbols else "")
    parts = [head] + (_tables(items) if items else []) + errors
    parts.append("Sentiment blends analyst mix, target upside, trend and RSI. Outlook is a statistical estimate, not advice.")
    return "\n\n".join(parts)
