"""Orchestrates data -> strategies -> risk -> paper broker -> Discord, one 1-minute tick at a time."""
from __future__ import annotations

import json
import time
from datetime import datetime

import pandas as pd

from .config import STATE_DIR, Settings
from .data import build_provider
from .data.base import DataProvider
from .brokers import build_broker
from .brokers.paper import Fill, PaperBroker
from .notify.discord import DiscordNotifier
from .reporting import daily_summary, half_hour_summary
from .strategies.day_trader import DayTradeStrategy
from .strategies.etf_core import ETFCoreStrategy

OPEN, FLATTEN, CLOSE = (9, 30), (15, 55), (16, 0)


def _mins(ts: pd.Timestamp) -> int:
    return ts.hour * 60 + ts.minute


class Engine:
    def __init__(self, s: Settings, provider: DataProvider | None = None, broker: PaperBroker | None = None,
                 notifier: DiscordNotifier | None = None, day: DayTradeStrategy | None = None, research=None):
        self.s = s
        self.symbols = sorted(set(s.day_symbols) | set(s.etf_universe) | {"SPY", s.hedge_symbol})
        self.provider = provider or build_provider(s, self.symbols)
        self.broker = broker or build_broker(s)
        self.notifier = notifier or DiscordNotifier(s)
        self.day = day or DayTradeStrategy()
        self.etf = ETFCoreStrategy(s.etf_universe)
        self.start_equity: float | None = None
        self.day_key: str | None = None
        self.halted = False
        self.last_summary: pd.Timestamp | None = None
        self.window_fills: list[Fill] = []
        self.closed = False
        self.etf_weights: dict[str, float] = {}
        self.research = research if research is not None else self._default_research()
        self.blackout: set[str] = set()
        self.research_lines: list[str] = []

    def _default_research(self):
        if self.provider.name != "robinhood":
            return None
        from .robinhood import research
        return research

    def _load_research(self, today: str) -> None:
        """Earnings-day blackout for new day-trade entries + analyst context for the daily summary."""
        self.blackout, self.research_lines = set(), []
        if not self.research:
            return
        try:
            snaps = self.research.snapshot(self.s.day_symbols, earnings_days=1)
        except Exception as exc:
            print(f"[research] unavailable: {exc}")
            return
        for sym, snap in snaps.items():
            if snap["next_earnings"] == today:
                self.blackout.add(sym)
            if snap["consensus"]:
                self.research_lines.append(f"{sym}: {snap['consensus']}")

    # ---- helpers ----
    def prices(self) -> dict[str, float]:
        return {sym: self.provider.last_price(sym) for sym in self.symbols}

    def equity(self, px: dict[str, float]) -> float:
        return self.broker.equity(px)

    def _trade(self, sleeve, sym, side, qty, px, ts, reason):
        fill = self.broker.submit_order(sleeve, sym, side, qty, px[sym], ts.isoformat(), reason)
        if fill:
            self.window_fills.append(fill)
        return fill

    def _post(self, channel: str, text: str) -> None:
        tag = "🧪 **[MOCK DATA]** " if self.provider.name == "mock" else ""
        self.notifier.post(channel, tag + text)

    def _state(self) -> dict:
        f = STATE_DIR / "engine_state.json"
        return json.loads(f.read_text()) if f.exists() else {}

    def _save_state(self, d: dict) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        (STATE_DIR / "engine_state.json").write_text(json.dumps(d))

    # ---- ETF sleeve ----
    def rebalance_etf(self, ts: pd.Timestamp, px: dict[str, float], force: bool = False) -> None:
        st = self._state()
        month = ts.strftime("%Y-%m")
        if not force and st.get("etf_last_rebalance") == month:
            return
        daily = {sym: self.provider.get_bars(sym, "1d", 260) for sym in self.s.etf_universe}
        eq = self.equity(px)
        sleeve_target_value = eq * self.s.etf_allocation_pct
        targets = self.etf.target_weights(daily)
        held = {k: v["qty"] for k, v in self.broker.positions["etf"].items()}
        for sym, side, qty, reason in self.etf.orders(targets, sleeve_target_value, px, held):
            self._trade("etf", sym, side, qty, px, ts, reason)
        self.etf_weights = targets
        st["etf_last_rebalance"] = month
        self._save_state(st)

    # ---- day trader ----
    def _new_day(self, ts: pd.Timestamp, px: dict[str, float]) -> None:
        self.day_key = ts.strftime("%Y-%m-%d")
        self.start_equity = self.equity(px)
        self.halted, self.closed = False, False
        self.last_summary = ts
        self.window_fills = []
        self._load_research(self.day_key)
        self.rebalance_etf(ts, px)

    def tick(self) -> None:
        ts = self.provider.now()
        px = self.prices()
        if self.day_key != ts.strftime("%Y-%m-%d"):
            self._new_day(ts, px)
        eq = self.equity(px)
        if not self.halted and self.start_equity and (eq - self.start_equity) / self.start_equity <= -self.s.max_daily_loss_pct:
            self.halted = True
            self._flatten_day(ts, px, "daily loss limit")
        m = _mins(ts)
        if not self.halted and m < FLATTEN[0] * 60 + FLATTEN[1]:
            self._run_day_strategy(ts, px, eq)
        elif m >= FLATTEN[0] * 60 + FLATTEN[1] and not self.closed:
            self._flatten_day(ts, px, "end-of-day flatten")
        if self.last_summary is not None and (ts - self.last_summary) >= pd.Timedelta(minutes=self.s.summary_interval_min):
            self._send_half_hour(ts, px)
        if m >= CLOSE[0] * 60 + CLOSE[1] - 1 and not self.closed:
            self.close_day(ts, px)

    def _run_day_strategy(self, ts, px, eq) -> None:
        for sym in self.s.day_symbols:
            bars = self.provider.get_bars(sym, "1m", 300)
            pos = self.broker.positions["day"].get(sym)
            sig = self.day.evaluate(sym, bars, pos["avg"] if pos else None, self.s.max_position_pct)
            if sig.action == "buy" and sym in self.blackout:
                continue  # earnings today: no new entries
            if sig.action == "buy":
                qty = eq * sig.weight / px[sym]
                self._trade("day", sym, "buy", qty, px, ts, sig.reason + (f", model {sig.score:+.4f}" if sig.score else ""))
            elif sig.action == "sell" and pos:
                self._trade("day", sym, "sell", pos["qty"], px, ts, sig.reason)
        hedge = self.s.hedge_symbol
        hedged = hedge in self.broker.positions["day"]
        sig = self.day.hedge(self.provider.get_bars("SPY", "1m", 300), hedged, hedge)
        if sig.action == "buy":
            self._trade("day", hedge, "buy", eq * sig.weight / px[hedge], px, ts, sig.reason)
        elif sig.action == "sell" and hedged:
            self._trade("day", hedge, "sell", self.broker.qty("day", hedge), px, ts, sig.reason)

    def _flatten_day(self, ts, px, reason) -> None:
        for sym, pos in list(self.broker.positions["day"].items()):
            self._trade("day", sym, "sell", pos["qty"], px, ts, reason)

    def _send_half_hour(self, ts, px) -> None:
        moves = {}
        for sym in self.s.day_symbols + ["SPY"]:
            if sym in moves:
                continue
            bars = self.provider.get_bars(sym, "1m", 31)
            moves[sym] = float(bars["close"].iloc[-1] / bars["close"].iloc[0] - 1)
        eq = self.equity(px)
        self._post("realtime", half_hour_summary(
            ts, moves, self.window_fills, eq, eq - (self.start_equity or eq),
            self.broker.positions["day"], px, self.halted))
        self.window_fills, self.last_summary = [], ts

    def close_day(self, ts, px) -> None:
        self._flatten_day(ts, px, "end-of-day flatten")
        px = self.prices()
        eq = self.equity(px)
        model = self.day.model
        note = (f"ridge OOS IC {model['metrics']['ic']:+.3f}, hit {model['metrics']['hit_rate']:.0%}"
                if model else "none (run `improve`)")
        if self.window_fills:
            self._send_half_hour(ts, px)
        self._post("updates", daily_summary(
            self.day_key or ts.strftime("%Y-%m-%d"), eq, eq - (self.start_equity or eq), self.start_equity or eq,
            self.broker.fills, self.broker.realized, self.etf_weights, note,
            self.research_lines, sorted(self.blackout)))
        self.closed = True

    # ---- runners ----
    def run_simulation(self, max_ticks: int | None = None, delay: float = 0.0) -> None:
        n = 0
        while True:
            self.tick()
            n += 1
            if self.closed or (max_ticks and n >= max_ticks) or not self.provider.advance():
                break
            time.sleep(delay)
        if not self.closed and max_ticks is None:
            self.close_day(self.provider.now(), self.prices())

    def run_live(self) -> None:  # pragma: no cover - wall-clock loop
        while True:
            ts = self.provider.now()
            if ts.weekday() < 5 and OPEN[0] * 60 + OPEN[1] <= _mins(ts) < CLOSE[0] * 60 + CLOSE[1]:
                try:
                    self.tick()
                except Exception as exc:
                    print(f"[{datetime.now():%H:%M:%S}] tick error: {exc}")
            time.sleep(60)
