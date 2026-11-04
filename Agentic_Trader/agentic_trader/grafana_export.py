"""Read-only export of the paper trader state into SQLite for the local Grafana dashboard.

Usage: python -m agentic_trader.grafana_export [--loop SECONDS]
The paper trader state is only read; the database is rebuilt atomically on every run.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from datetime import datetime

from .config import STATE_DIR
from .desk import AGENTS, Orchestrator, agent_of
from .paper_options import MULT, _coll, max_loss
from .quant_suite import account_performance

SOURCE = STATE_DIR / "paper_live.json"
QUANT = STATE_DIR / "quant_suite.json"
RANKING = STATE_DIR / "signal_ranking.json"
TARGET = STATE_DIR / "trader_history.db"

SCHEMA = """
CREATE TABLE equity (ts INTEGER, day TEXT, equity REAL, return_pct REAL);
CREATE TABLE trades (ts INTEGER, day TEXT, side TEXT, symbol TEXT, sleeve TEXT, qty REAL, price REAL,
                     value REAL, fee REAL, realized REAL, reason TEXT, agent TEXT, strat TEXT);
CREATE TABLE positions (symbol TEXT, sleeve TEXT, qty REAL, avg REAL, cost REAL);
CREATE TABLE daily (day TEXT, ts INTEGER, open_equity REAL, close_equity REAL, return_pct REAL,
                    realized REAL, fees REAL, trades INTEGER);
CREATE TABLE holdings (symbol TEXT, sleeve TEXT, qty REAL, avg REAL, price REAL, value REAL, cost REAL,
                       pnl REAL, pnl_pct REAL, weight_pct REAL);
CREATE TABLE quant (mode TEXT, symbol TEXT, score REAL, edge INTEGER, veto INTEGER, size_mult REAL, rsi REAL,
                    macd_hist REAL, zscore REAL, rvol REAL, rv_ann REAL, garch_ann REAL, vol_ratio REAL,
                    rmse_vs_naive REAL, hit_rate REAL, ic REAL, auc REAL, log_loss REAL, sharpe REAL, sortino REAL,
                    max_dd REAL, profit_factor REAL, compute TEXT, ts INTEGER, reasons TEXT);
CREATE TABLE quality (metric TEXT, value REAL);
CREATE TABLE options (symbol TEXT, strat TEXT, kind TEXT, short_strike REAL, long_strike REAL, expiry TEXT, qty INTEGER,
                      credit REAL, mark REAL, open_pnl REAL, max_loss REAL, collateral REAL);
CREATE TABLE allocation (ts INTEGER, agent TEXT, mult REAL, budget_pct REAL, score_pct REAL, current INTEGER);
CREATE TABLE ranking (rank INTEGER, name TEXT, parts INTEGER, tier TEXT, train_n INTEGER, train_excess_bp REAL,
                      train_t REAL, hold_n INTEGER, hold_excess_bp REAL, hold_t REAL, hold_hit REAL, hold_pf REAL,
                      weight REAL);
CREATE TABLE benchmark (day TEXT, account_pct REAL, spy_pct REAL, excess_pct REAL);
CREATE TABLE account (ts INTEGER, start_cash REAL, cash REAL, equity REAL, realized_total REAL,
                      fees_total REAL, total_return_pct REAL, regime TEXT);
"""


def _epoch(value):
    return int(datetime.fromisoformat(str(value)).timestamp())


def _day(value):
    return str(value)[:10]


def export(source=SOURCE, target=TARGET):
    state = json.loads(source.read_text())
    start = float(state.get("start_cash") or 5000)
    equity_log = state.get("equity_log") or []
    trades = state.get("trades") or []

    tmp = target.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    db = sqlite3.connect(tmp)
    db.executescript(SCHEMA)

    db.executemany(
        "INSERT INTO equity VALUES (?,?,?,?)",
        [(_epoch(ts), _day(ts), float(eq), (float(eq) / start - 1) * 100) for ts, eq in equity_log],
    )
    db.executemany(
        "INSERT INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (
                _epoch(t["ts"]), _day(t["ts"]), t.get("side"), t.get("sym"), t.get("sleeve"),
                t.get("qty"), t.get("px"),
                t.get("value") if t.get("value") is not None else (t.get("px") or 0) * 100 * (t.get("qty") or 0), t.get("fee") or 0,
                t.get("realized") if t.get("realized") is not None else 0, (f"{t['desc']} [{t.get('reason')}]" if t.get("desc") else t.get("reason")),
                agent_of(t) or "other",
                t.get("strat") or (t.get("sleeve") if agent_of(t) == "growth" else "unassigned"),
            )
            for t in trades
        ],
    )
    db.executemany(
        "INSERT INTO positions VALUES (?,?,?,?,?)",
        [
            (sym, p.get("sleeve"), p.get("qty"), p.get("avg"), (p.get("qty") or 0) * (p.get("avg") or 0))
            for sym, p in (state.get("positions") or {}).items()
        ],
    )

    marks = state.get("marks") or {}
    total = float(equity_log[-1][1]) if equity_log else start
    rows = []
    for sym, p in (state.get("positions") or {}).items():
        px = float(marks.get(sym) or p.get("avg") or 0)
        qty, cost = p.get("qty") or 0, (p.get("qty") or 0) * (p.get("avg") or 0)
        rows.append((sym, p.get("sleeve"), qty, p.get("avg"), px, qty * px, cost, qty * px - cost,
                     (px / p["avg"] - 1) * 100 if p.get("avg") else 0.0, qty * px / total * 100 if total else 0.0))
    cash = float(state.get("cash") or 0)
    rows.append(("Cash", "cash", cash, 1.0, 1.0, cash, cash, 0.0, 0.0, cash / total * 100 if total else 0.0))
    db.executemany("INSERT INTO holdings VALUES (?,?,?,?,?,?,?,?,?,?)", rows)

    suite = json.loads(QUANT.read_text()) if QUANT.exists() else {}
    for key, r in (suite.get("symbols") or {}).items():
        if "error" in r:
            continue
        mode, sym = key.split(":", 1)
        wf, pf, g = r.get("wf") or {}, (r.get("wf") or {}).get("perf") or {}, r.get("garch") or {}
        db.execute("INSERT INTO quant VALUES (" + ",".join("?" * 25) + ")", (
            mode, sym, r.get("score"), int(bool(r.get("edge"))), int(bool(r.get("veto"))), r.get("size_mult"),
            r.get("rsi"), r.get("macd_hist"), r.get("zscore"), r.get("rvol"), r.get("rv_ann"), g.get("vol_ann"),
            g.get("vol_ratio"), wf.get("rmse_vs_naive"), wf.get("hit_rate"), wf.get("ic"), wf.get("auc"),
            wf.get("log_loss"), pf.get("sharpe"), pf.get("sortino"), pf.get("max_dd"), pf.get("profit_factor"),
            r.get("where"), _epoch(r["ts"]) if r.get("ts") else None, "; ".join(r.get("reasons") or [])))

    for o in state.get("options") or []:
        short_mark = o.get("mark") if o.get("mark") is not None else o["credit"]
        db.execute("INSERT INTO options VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
            o["sym"], o.get("strat") or "unassigned", o.get("kind"), o["strike"], o.get("long_strike"), o["exp"],
            o["qty"], o["credit"], short_mark, (o["credit"] - short_mark) * MULT * o["qty"], max_loss(o), _coll(o)))

    alloc = state.get("alloc") or {}
    cur = alloc.get("mult") or {}
    bases = alloc.get("base") or {"growth": 0.6, "options": 0.35, "day": 0.3}  # the orchestrator saves its bases
    for row in (alloc.get("history") or []):
        for a in AGENTS:
            db.execute("INSERT INTO allocation VALUES (?,?,?,?,?,0)", (
                _epoch(row["ts"]), a, row["mult"].get(a, 1.0),
                min(Orchestrator.HARD_CAP[a], bases[a] * row["mult"].get(a, 1.0)) * 100,
                (row.get("score") or {}).get(a, 0.0) * 100))
    if cur:
        now_ts = _epoch(alloc["ts"]) if alloc.get("ts") else int(time.time())
        for a in AGENTS:
            db.execute("INSERT INTO allocation VALUES (?,?,?,?,?,1)", (
                now_ts, a, cur.get(a, 1.0), min(Orchestrator.HARD_CAP[a], bases[a] * cur.get(a, 1.0)) * 100,
                (alloc.get("score") or {}).get(a, 0.0) * 100))

    if RANKING.exists():
        rk = json.loads(RANKING.read_text())
        for r in (rk.get("singles") or []) + (rk.get("ranking") or []):
            a, b = r["train"], r["holdout"]
            db.execute("INSERT INTO ranking VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                r["rank"], r["name"], r["parts"], r.get("tier", "none"), a["n"], a["excess_bp"], a["t"], b["n"],
                b["excess_bp"], b["t"], b["hit"], b["pf"], r.get("weight", 0.0)))

    bench = state.get("bench_daily") or {}
    if bench:
        days = sorted(bench)
        last_eq = {}
        for ts, eq in equity_log:
            last_eq[_day(ts)] = float(eq)
        first = next((d for d in days if d in last_eq), None)
        if first:
            b0, e0 = bench[first], last_eq[first]
            for d in days:
                if d in last_eq and d >= first:
                    acc, spy = (last_eq[d] / e0 - 1) * 100, (bench[d] / b0 - 1) * 100
                    db.execute("INSERT INTO benchmark VALUES (?,?,?,?)", (d, acc, spy, acc - spy))

    quality = account_performance(equity_log, trades)
    db.executemany("INSERT INTO quality VALUES (?,?)", [
        (k, v) for k, v in (("Sharpe", quality.get("sharpe")), ("Sortino", quality.get("sortino")),
                            ("Max drawdown %", None if quality.get("max_dd") is None else quality["max_dd"] * 100),
                            ("Profit factor", quality.get("trade_profit_factor")),
                            ("Trade win rate %", None if quality.get("trade_win_rate") is None else quality["trade_win_rate"] * 100))
        if v is not None])

    by_day = {}
    for ts, eq in equity_log:
        by_day.setdefault(_day(ts), []).append((_epoch(ts), float(eq)))
    previous_close = start
    for day in sorted(by_day):
        points = by_day[day]
        close = points[-1][1]
        day_trades = [t for t in trades if _day(t["ts"]) == day]
        db.execute(
            "INSERT INTO daily VALUES (?,?,?,?,?,?,?,?)",
            (
                day, points[-1][0], previous_close, close, (close / previous_close - 1) * 100,
                sum(t.get("realized") or 0 for t in day_trades),
                sum(t.get("fee") or 0 for t in day_trades), len(day_trades),
            ),
        )
        previous_close = close

    latest_ts, latest_eq = (equity_log[-1] if equity_log else (state.get("created"), start))
    regime = (state.get("regime") or {}).get("name") or ""
    db.execute(
        "INSERT INTO account VALUES (?,?,?,?,?,?,?,?)",
        (
            _epoch(latest_ts), start, state.get("cash"), float(latest_eq),
            state.get("realized_total") or 0, state.get("fees_total") or 0,
            (float(latest_eq) / start - 1) * 100, regime,
        ),
    )
    db.commit()
    db.close()
    os.replace(tmp, target)
    return {"options": len(state.get("options") or []), "equity": len(equity_log), "trades": len(trades), "days": len(by_day), "holdings": len(rows),
            "quant": len(suite.get("symbols") or {})}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", type=int, default=0)
    args = parser.parse_args()
    while True:
        try:
            print(export(), flush=True)
        except Exception as exc:
            print("export failed:", repr(exc), flush=True)
        if not args.loop:
            break
        time.sleep(args.loop)


if __name__ == "__main__":
    main()
