"""Message formatting for the half-hour (day trader) and end-of-day (updates) Discord posts."""
from __future__ import annotations

import pandas as pd

from .brokers.paper import Fill


def _arrow(x: float) -> str:
    return "🟢" if x > 0 else "🔴" if x < 0 else "⚪"


def half_hour_summary(ts: pd.Timestamp, moves: dict[str, float], fills: list[Fill], equity: float,
                      day_pnl: float, day_positions: dict[str, dict], prices: dict[str, float],
                      halted: bool) -> str:
    lines = [f"**⏱ Day Trader – {ts:%H:%M} ET** (paper)"]
    lines.append("Moves (30m): " + ", ".join(f"{_arrow(v)} {k} {v:+.2%}" for k, v in moves.items()))
    if fills:
        lines.append("Trades:")
        lines += [f"• {f.side.upper()} {f.qty:.2f} {f.symbol} @ {f.price:.2f} — {f.reason}" for f in fills]
    else:
        lines.append("Trades: none")
    if day_positions:
        lines.append("Open: " + ", ".join(f"{s} {p['qty']:.1f} ({prices.get(s, p['avg']) / p['avg'] - 1:+.2%})"
                                         for s, p in day_positions.items()))
    lines.append(f"Equity ${equity:,.0f} | Day P&L {_arrow(day_pnl)} ${day_pnl:+,.2f}" + (" | ⛔ HALTED (loss limit)" if halted else ""))
    return "\n".join(lines)


def daily_summary(day: str, equity: float, day_pnl: float, start_equity: float, fills: list[Fill],
                  realized: dict[str, float], etf_weights: dict[str, float], model_note: str,
                  analyst_lines: list[str] | None = None, blackout: list[str] | None = None) -> str:
    day_fills = [f for f in fills if f.sleeve == "day"]
    sells = [f for f in day_fills if f.side == "sell"]
    lines = [f"**📈 Daily Summary – {day}** (paper)",
             f"Equity ${equity:,.0f} ({day_pnl / start_equity:+.2%} on day, ${day_pnl:+,.2f})",
             f"Day trader: {len(day_fills)} fills, realized ${realized.get('day', 0):+,.2f}",
             f"ETF sleeve: realized ${realized.get('etf', 0):+,.2f}"]
    if etf_weights:
        lines.append("ETF weights: " + ", ".join(f"{k} {v:.0%}" for k, v in sorted(etf_weights.items(), key=lambda kv: -kv[1])))
    if sells:
        lines.append("Last exits: " + "; ".join(f"{f.symbol} ({f.reason})" for f in sells[-5:]))
    if blackout:
        lines.append("Earnings-day no-entry list: " + ", ".join(blackout))
    if analyst_lines:
        lines.append("Analyst consensus: " + "; ".join(analyst_lines))
    lines.append(f"Model: {model_note}")
    return "\n".join(lines)
