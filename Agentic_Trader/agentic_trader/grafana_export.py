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
from .desk import agent_of

SOURCE = STATE_DIR / "paper_live.json"
TARGET = STATE_DIR / "trader_history.db"

SCHEMA = """
CREATE TABLE equity (ts INTEGER, day TEXT, equity REAL, return_pct REAL);
CREATE TABLE trades (ts INTEGER, day TEXT, side TEXT, symbol TEXT, sleeve TEXT, qty REAL, price REAL,
                     value REAL, fee REAL, realized REAL, reason TEXT, agent TEXT);
CREATE TABLE positions (symbol TEXT, sleeve TEXT, qty REAL, avg REAL, cost REAL);
CREATE TABLE daily (day TEXT, ts INTEGER, open_equity REAL, close_equity REAL, return_pct REAL,
                    realized REAL, fees REAL, trades INTEGER);
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
        "INSERT INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (
                _epoch(t["ts"]), _day(t["ts"]), t.get("side"), t.get("sym"), t.get("sleeve"),
                t.get("qty"), t.get("px"),
                t.get("value") if t.get("value") is not None else (t.get("px") or 0) * 100 * (t.get("qty") or 0), t.get("fee") or 0,
                t.get("realized") if t.get("realized") is not None else 0, (f"{t['desc']} [{t.get('reason')}]" if t.get("desc") else t.get("reason")),
                agent_of(t) or "other",
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
    return {"equity": len(equity_log), "trades": len(trades), "days": len(by_day)}


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
