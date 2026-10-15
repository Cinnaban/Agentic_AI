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
    price = q.get("price")
    ma20 = float(c[-20:].mean()) if len(c) >= 20 else None
    ma50 = float(c[-50:].mean()) if len(c) >= 50 else None
    ma200 = float(c[-200:].mean()) if len(c) >= 200 else None
    rsi = _rsi(c)
    proj = _projection(c)
    beta = _beta(c, bench) if len(bench) else None
    target = _f((rating or {}).get("mean_price_target"))
    upside = (target / price - 1) if target and price else None
    sent = _sentiment(rating, upside, proj and proj["trend_ann"], rsi)
    etf = _is_etf(f)
    kind = "ETF" if etf else (f.get("sector") or "stock")
    L = [f"{sym} ({kind})", ""]

    def kv(label, value):
        L.extend([f"{label}:", value])

    day = q.get("change_pct")
    kv("Current price", f"{_money(price)}" + (f" ({day:+.2%} today)" if day is not None else ""))
    kv("Market cap", _big(_f(f.get("market_cap"))))
    if held:
        val = price * held["qty"] if price else 0.0
        gl = (val - held["cost"]) if held["cost"] else None
        glp = (val / held["cost"] - 1) if held["cost"] else None
        where = ", ".join(f"{k} {v:g}" for k, v in held["where"].items())
        L.append("")
        kv("Position", f"{held['qty']:g} sh in {where}\nValue {_money(val)}"
           + (f" ({val / port_value:.1%} of all holdings)" if port_value else ""))
        if gl is not None:
            kv("Gain/Loss", f"{gl:+,.2f} ({glp:+.1%}) vs average cost")
    pos = lambda m: "n/a" if not (m and price) else f"{_money(m)} ({price / m - 1:+.1%})"
    L.append("")
    kv("MA20", pos(ma20))
    kv("MA50", pos(ma50))
    kv("MA200", pos(ma200))
    if ma20 and ma50:
        kv("Trend", "MA20 above MA50 (bullish)" if ma20 > ma50 else "MA20 below MA50 (bearish)")
    if rsi is not None:
        kv("RSI14", f"{rsi:.0f}" + (" (oversold)" if rsi < 30 else " (overbought)" if rsi > 70 else ""))
    hi, lo = _f(f.get("high_52_weeks")), _f(f.get("low_52_weeks"))
    if hi and lo and price and hi > lo:
        kv("52-week range", f"{_money(lo)} - {_money(hi)} ({(price - lo) / (hi - lo):.0%} of range)")
    L.append("")
    kv("Beta", f"{beta:.2f} (1y daily vs {BENCH})" if beta is not None else "n/a")
    div_ps, dy = _f(f.get("dividend_per_share")), _f(f.get("dividend_yield"))
    freq = (f.get("distribution_frequency") or "")
    if div_ps:
        txt = f"{dy:.2f}% yield\n${div_ps:.2f}/sh {freq}".rstrip()
        if held and freq.lower().startswith("q"):
            txt += f"\n~${div_ps * 4 * held['qty']:.2f}/yr on your shares"
        kv("Dividend", txt)
    else:
        kv("Dividend", "none")
    if f.get("pe_ratio"):
        kv("P/E", f"{_f(f['pe_ratio']):.1f}")
    L.append("")
    if rating:
        kv("Analysts", f"{rating.get('num_buy_ratings', 0)} buy / {rating.get('num_hold_ratings', 0)} hold / "
           f"{rating.get('num_sell_ratings', 0)} sell\nMean target {_money(target)}"
           + (f" ({upside:+.1%})" if upside is not None else ""))
    kv("Market sentiment", f"{_label(sent)}" + (f" ({sent:+.2f})" if sent is not None else ""))
    if proj:
        L.append("")
        kv("Outlook (5 days)", f"Expected {proj['exp5']:+.2%} +/- {proj['band5']:.1%} (1 sd)\n"
           f"60d trend {proj['trend_ann']:+.0%}/yr (fit R2 {proj['r2']:.2f})\nVolatility {proj['vol_ann']:.0%}/yr")
    if etf:
        top = _etf_holdings(sym)
        L.append("")
        kv("Top holdings", "\n".join(f"- {n}: {w:.1%}" if w < 1 else f"- {n}: {w:.1f}%" for n, w in top)
           if top else "unavailable")
    return "\n".join(L)


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
    blocks = []
    for s in wanted:
        try:
            blocks.append(review_symbol(s, funds.get(s, {}), quotes.get(s, {}), _closes(bars.get(s, [])), bench,
                                        ratings.get(s), held.get(s), total))
        except Exception as exc:
            blocks.append(f"{s}: review failed ({str(exc)[:80]})")
    head = f"Review of {len(wanted)} symbol(s)" + (f" across {len(held)} held, equity value {_money(total)}" if not symbols else "")
    return head + "\n\n" + "\n\n----------\n\n".join(blocks) + "\n\nProjections are statistical estimates, not advice."
