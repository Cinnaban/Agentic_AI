"""Independent paper accounts for the parallel day-strategy experiment."""
from copy import copy

from .day_agents import DayDesk
from .desk import Mandate, Orchestrator, agent_of
from .historian import Historian
from .paper_live import PaperTrader, new_state
from .paper_longopts import LongOptions
from .paper_options import Income
from .quant_gate import QuantGate


class CachedSignals:
    """Reuse the production signal cache without refreshing or consuming its API budget."""
    def __init__(self, signals):
        self.signals = signals

    def refresh(self, symbols, group):
        return None

    def bearish(self, symbol):
        return self.signals.bearish(symbol)


class ComparisonTrader(PaperTrader):
    def __init__(self, parent, state, single, quant, signals):
        self.cfg = copy(parent.cfg)
        if single:
            self.cfg.day_strategies = ["PULLBACK"]
            self.cfg.day_max_trades = 1
            self.cfg.day_max_open = 1
        self.s = state
        self.data, self.analyze = parent.data, parent.analyze
        self.quant, self.signals, self.rank = quant, signals, parent.rank
        self.income, self.longopts = Income(self), LongOptions(self)
        self.pdt_blocked = 0
        self.day_desk = DayDesk(self)
        self.historian = Historian(self.cfg)


class DayComparison:
    def __init__(self, parent):
        self.parent = parent
        self.teams = None

    def _initialize(self, t):
        parent = self.parent
        comparison = parent.s.get("day_comparison")
        if comparison is None:
            comparison = {
                "started": t.isoformat(),
                "budget_pct": parent.cfg.day_pct,
                "teams": {
                    "multi": new_state(parent.cfg, t),
                    "single": new_state(parent.cfg, t),
                },
            }
            parent.s["day_comparison"] = comparison
        states = comparison["teams"]
        quant = QuantGate(parent.data, enabled=parent.cfg.quant_gate,
                          path=parent.store.mirror.with_name("day_comparison_quant.json"))
        signals = CachedSignals(parent.signals)
        self.teams = {
            "multi": ComparisonTrader(parent, states["multi"], False, quant, signals),
            "single": ComparisonTrader(parent, states["single"], True, quant, signals),
        }

    def initialize(self, t):
        if self.teams is None:
            self._initialize(t)

    def run(self, quotes, t, reg):
        self.initialize(t)
        comparison = self.parent.s["day_comparison"]
        multi = self.teams["multi"]
        try:
            snapshots = multi.day_desk._snapshots(quotes, t)
            comparison["last_error"] = None
        except Exception as exc:
            comparison["last_error"] = repr(exc)
            print(f"[paper] day comparison snapshots failed: {exc!r}", flush=True)
            snapshots = {}
        tilt = getattr(multi.day_desk, "tilt", {})
        for name, tr in self.teams.items():
            state = tr.s
            try:
                tr.day_desk.tilt = tilt
                equity = tr.equity(quotes)
                if state["day"]["date"] != t.date().isoformat():
                    state["day"] = {"date": t.date().isoformat(), "open_equity": equity,
                                    "spy_open": (quotes.get("SPY") or {}).get("prev_close"), "eod_posted": False}
                week_id = "%d-W%02d" % t.isocalendar()[:2]
                if state["week"]["id"] != week_id:
                    state["week"] = {"id": week_id, "open_equity": equity}
                tr.protect(quotes, t)
                equity = tr.equity(quotes)
                day_ret = equity / state["day"]["open_equity"] - 1
                week_ret = equity / state["week"]["open_equity"] - 1
                scale = reg.get("day_scale", 1.0)
                mandate = Mandate("day", comparison["budget_pct"], scale=scale)
                if comparison["last_error"]:
                    mandate.allow_new = False
                    mandate.note = "comparison market snapshots unavailable"
                if day_ret >= tr.cfg.daily_max or day_ret <= Orchestrator.DRAWDOWN_DAY or week_ret >= tr.cfg.week_max:
                    mandate.allow_new = False
                    mandate.note = "comparison account goal or drawdown limit"
                if week_ret <= Orchestrator.DRAWDOWN_WEEK:
                    mandate.scale = min(mandate.scale, 0.5)
                if tr.cfg.brief_on:
                    mandate.brief = tr.historian.build(state["trades"], t, agent_of, equity)["teams"]["day"]
                tr.day_desk.run(quotes, t, equity, mandate, reg, (t.hour, t.minute), snapshots=snapshots)
                equity = tr.equity(quotes)
                point = [t.isoformat(), equity]
                if state["equity_log"] and state["equity_log"][-1][0][:10] == t.date().isoformat():
                    state["equity_log"][-1] = point
                else:
                    state["equity_log"].append(point)
                state["marks"] = {sym: (quotes.get(sym) or {}).get("price") or pos["avg"]
                                  for sym, pos in state["positions"].items()}
                state["last_error"] = None
            except Exception as exc:
                state["last_error"] = repr(exc)
                print(f"[paper] day comparison {name} failed: {exc!r}", flush=True)
