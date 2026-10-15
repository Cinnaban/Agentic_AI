"""Portfolio analysis text for Telegram: balances, allocation %, per-position growth, concentration, live quant."""
from __future__ import annotations

from . import account
from .data import shared


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _money(x: float) -> str:
    return f"${x:,.2f}"


def analyze_account(acct: dict, with_quant: bool = True) -> str:
    no = acct["account_number"]
    pf, pos = account.portfolio(no), account.positions(no)
    total = _f(pf.get("total_value"))
    cash = _f(pf.get("cash"))
    bp = _f((pf.get("buying_power") or {}).get("unleveraged_buying_power") or (pf.get("buying_power") or {}).get("buying_power"))
    lines = [f"{account.label(acct)} ({acct.get('brokerage_account_type')}, {acct.get('type')})",
             f"Total {_money(total)} | cash {_money(cash)} | buying power (unleveraged) {_money(bp)}"]
    kinds = {k.replace('_value', ''): _f(pf.get(k)) for k in
             ("equity_value", "options_value", "crypto_value", "mutual_funds_value", "fixed_income_value", "futures_value")}
    mix = [f"{k} {v / total:.1%}" for k, v in kinds.items() if v and total]
    if cash and total:
        mix.append(f"cash {cash / total:.1%}")
    if mix:
        lines.append("Mix: " + ", ".join(mix))
    held = [p for p in pos if _f(p.get("quantity")) > 0]
    if not held:
        return "\n".join(lines + ["No open equity positions."])
    syms = [p["symbol"] for p in held]
    quotes = shared().quotes(syms)
    rows = []
    for p in held:
        q = quotes.get(p["symbol"]) or {}
        px, qty, cost = q.get("price") or 0.0, _f(p["quantity"]), _f(p.get("average_buy_price"))
        val = px * qty
        rows.append({"sym": p["symbol"], "val": val, "qty": qty, "growth": (px / cost - 1) if cost and px else None,
                     "day": q.get("change_pct")})
    eq = sum(r["val"] for r in rows) or 1.0
    rows.sort(key=lambda r: r["val"], reverse=True)
    lines.append("Positions (weight of equity | value | growth vs cost | day):")
    for r in rows[:15]:
        g = f"{r['growth']:+.1%}" if r["growth"] is not None else "n/a"
        d = f"{r['day']:+.2%}" if r["day"] is not None else "n/a"
        lines.append(f"- {r['sym']}: {r['val'] / eq:.1%} | {_money(r['val'])} | {g} | {d}")
    hhi = sum((r["val"] / eq) ** 2 for r in rows)
    top = rows[0]
    note = "concentrated" if hhi > 0.25 or top["val"] / eq > 0.4 else "reasonably diversified"
    lines.append(f"Concentration: top holding {top['sym']} {top['val'] / eq:.0%}, HHI {hhi:.2f} ({note}), {len(rows)} positions.")
    if with_quant:
        try:
            from .. import quant_live
            res = quant_live.analyze([r["sym"] for r in rows[:5]], data=shared())
            q = [f"{s}: signal {m['signal_score']:+.2f}, RSI {m.get('rsi14') or 0:.0f}, vol {m['realized_vol_ann']:.0%}"
                 for s, m in res.items() if "error" not in m]
            if q:
                lines.append("Live quant (top holdings): " + " | ".join(q))
        except Exception:
            pass
    return "\n".join(lines)


def report() -> str:
    return "\n\n".join(analyze_account(a) for a in account.analysis_accounts())
