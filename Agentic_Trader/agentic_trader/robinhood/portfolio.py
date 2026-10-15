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
    from ..tables import kv_table, table
    no = acct["account_number"]
    pf, pos = account.portfolio(no), account.positions(no)
    total = _f(pf.get("total_value"))
    cash = _f(pf.get("cash"))
    bp = _f((pf.get("buying_power") or {}).get("unleveraged_buying_power") or (pf.get("buying_power") or {}).get("buying_power"))
    out = [f"{account.label(acct)} ({acct.get('brokerage_account_type')}, {acct.get('type')})"]
    kinds = {k.replace("_value", ""): _f(pf.get(k)) for k in
             ("equity_value", "options_value", "crypto_value", "mutual_funds_value", "fixed_income_value", "futures_value")}
    pairs = [("Total value", _money(total)), ("Cash", _money(cash)), ("Buying power (unlevered)", _money(bp))]
    pairs += [(f"{k.capitalize()} mix", f"{v / total:.1%}") for k, v in kinds.items() if v and total]
    if cash and total:
        pairs.append(("Cash mix", f"{cash / total:.1%}"))
    out.append(kv_table(pairs, title="Account"))
    held = [p for p in pos if _f(p.get("quantity")) > 0]
    if not held:
        return "\n\n".join(out + ["No open equity positions."])
    quotes = shared().quotes([p["symbol"] for p in held])
    rows = []
    for p in held:
        q = quotes.get(p["symbol"]) or {}
        px, qty, cost = q.get("price") or 0.0, _f(p["quantity"]), _f(p.get("average_buy_price"))
        rows.append({"sym": p["symbol"], "val": px * qty, "growth": (px / cost - 1) if cost and px else None,
                     "gl": (px - cost) * qty if cost and px else None, "day": q.get("change_pct")})
    eq = sum(r["val"] for r in rows) or 1.0
    rows.sort(key=lambda r: r["val"], reverse=True)
    quant = {}
    if with_quant:
        try:
            from .. import quant_live
            quant = quant_live.analyze([r["sym"] for r in rows[:8]], data=shared())
        except Exception:
            quant = {}
    sig = lambda s: (f"{quant[s]['signal_score']:+.2f}" if s in quant and "error" not in quant[s] else "-")
    out.append(table(
        ["Symbol", "Weight", "Value", "Gain/Loss", "G/L %", "Day", "Signal"],
        [[r["sym"], f"{r['val'] / eq:.1%}", _money(r["val"]), "n/a" if r["gl"] is None else f"{r['gl']:+,.0f}",
          f"{r['growth']:+.1%}" if r["growth"] is not None else "n/a",
          f"{r['day']:+.1%}" if r["day"] is not None else "n/a", sig(r["sym"])] for r in rows[:25]],
        title="Positions (weight of equity)"))
    hhi = sum((r["val"] / eq) ** 2 for r in rows)
    top = rows[0]
    note = "concentrated" if hhi > 0.25 or top["val"] / eq > 0.4 else "reasonably diversified"
    out.append(kv_table([("Top holding", f"{top['sym']} {top['val'] / eq:.0%}"), ("HHI", f"{hhi:.2f} ({note})"),
                         ("Positions", str(len(rows)))], title="Concentration"))
    return "\n\n".join(out)


def report() -> str:
    return "\n\n----------\n\n".join(analyze_account(a) for a in account.analysis_accounts())
