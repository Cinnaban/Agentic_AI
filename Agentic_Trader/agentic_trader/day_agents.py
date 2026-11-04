"""Day-trading team (paper only): one independent agent per intraday strategy, supervised by the orchestrator.

Every agent runs its own entry strategy against the same goals, the same day budget (split evenly into slices) and
the same ruleset: ATR stop on every entry, risk-based sizing, break-even/trailing exits, flat by 15:50, long only,
no leverage. The `DayDesk` owns what must be common (market data, exits, hard limits); each `DayStrategyAgent` owns
only its entry decision, its entry count, its own loss limit and its slice of the budget.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

from . import day_strategy as ds
from .single_trade import evaluate as daily_eval
from .factor_tilt import tilt as factor_tilt


def _strat_trades(s, name, today, side=None):
    return [x for x in s["trades"] if x.get("strat") == name and x["ts"][:10] == today and (side is None or x["side"] == side)]


class DayStrategyAgent:
    def __init__(self, name):
        self.name = name
        self.label, self.fn = ds.STRATEGIES[name]

    def positions(self, tr):
        return [s for s, p in tr.s["positions"].items() if p.get("strat") == self.name and p["sleeve"] == "day"]

    def entries_today(self, tr, t):
        return len(_strat_trades(tr.s, self.name, t.date().isoformat(), "buy"))

    def pl_today(self, tr, t):
        return sum(x.get("realized", 0.0) for x in _strat_trades(tr.s, self.name, t.date().isoformat()) if "realized" in x)

    def deployed(self, tr, quotes):
        return sum(tr.s["positions"][s]["qty"] * ((quotes.get(s) or {}).get("price") or tr.s["positions"][s]["avg"])
                   for s in self.positions(tr))

    def scan(self, ctx):
        """Ranked [(score, sym, kind, why, snapshot)] and {sym: reason} for names without a setup."""
        tr, c, quotes, snap, t = ctx["tr"], ctx["cfg"], ctx["quotes"], ctx["snap"], ctx["t"]
        found, skipped = [], {}
        tr.quant.ensure([s for s in c.day_symbols if snap.get(s)], "day")
        for sym in c.day_symbols:
            m, q = snap.get(sym), quotes.get(sym)
            if not m or not q or sym in tr.s["positions"]:
                continue
            if sym in ctx.get("earnings", ()):
                skipped[sym] = "reports earnings today"
                continue
            cd = tr.s["cooldown"].get(sym)
            if cd and (t - datetime.fromisoformat(cd)).total_seconds() < c.reentry_min * 60:
                skipped[sym] = "cooling down after last exit"
                continue
            got, why = self.fn(m, c)
            if got:
                kind, strength = got
                veto, qscore, size, note = tr.quant.verdict(sym, "day")
                if veto:
                    skipped[sym] = f"{kind} setup vetoed by the quant suite ({qscore:+.2f})"
                    continue
                if tr.signals.bearish(sym):
                    skipped[sym] = f"{kind} setup skipped: bearish news"
                    continue
                ft = ctx.get("tilt", {}).get(sym) or {}
                if ft and not ft["liquid"]:
                    skipped[sym] = f"{kind} setup skipped: below the dollar-volume floor"
                    continue
                quality = (ctx["daily"].get(sym) or {}).get("score", 0.0)
                m = dict(m, quant_size=size, quant_note=note)
                found.append((strength + 0.3 * ds.daily_bias(m) + 0.2 * quality + 0.3 * qscore + c.day_tilt_weight * ft.get("tilt", 0.0) + c.rank_weight * ctx.get("rank", {}).get(sym, 0.0), sym, kind, why, m))
            else:
                skipped[sym] = why
        return sorted(found, key=lambda x: -x[0]), skipped

    def probation(self, tr, c, t):
        """Reason to stand down: enough recent closed trades and a profit factor below the floor, else None."""
        if not c.autopause:
            return None
        since = (t - timedelta(days=10)).isoformat()
        rows = [x["realized"] for x in tr.s["trades"] if x.get("strat") == self.name and x["side"] == "sell"
                and "realized" in x and x["ts"] >= since]
        if len(rows) < c.autopause_min:
            return None
        gain, loss = sum(r for r in rows if r > 0), -sum(r for r in rows if r < 0)
        pf = gain / loss if loss else float("inf")
        return f"on probation: profit factor {pf:.2f} over {len(rows)} trades in 10 days" if pf < c.autopause_pf else None

    def run(self, ctx):
        tr, c, t, quotes = ctx["tr"], ctx["cfg"], ctx["t"], ctx["quotes"]
        rep = {"label": self.label, "entries": self.entries_today(tr, t), "pl": self.pl_today(tr, t),
               "open": self.positions(tr), "note": ""}
        ctx["report"][self.name] = rep
        if rep["entries"] >= ctx["agent_max_entries"]:
            rep["note"] = f"entry cap reached ({ctx['agent_max_entries']})"
            return
        if rep["pl"] <= -c.day_agent_loss_limit * ctx["equity"]:
            rep["note"] = f"loss limit hit ({rep['pl']:+.2f}); standing down"
            return
        pause = self.probation(tr, c, t)
        if pause:
            rep["note"] = pause
            return
        if len(rep["open"]) >= c.day_agent_max_open:
            rep["note"] = f"holding {', '.join(rep['open'])}"
            return
        found, skipped = self.scan(ctx)
        if not found:
            rep["note"] = "; ".join(f"{s}: {r}" for s, r in list(skipped.items())[:3]) or "no data"
            return
        slice_room = ctx["slice"] - self.deployed(tr, quotes)
        for score, sym, kind, why, m in found:
            if ctx["team_room"] <= 0 or slice_room <= 0:
                break
            plan = ds.plan_trade(m, c, ctx["equity"], tr.free_cash(), ctx["scale"])
            notional = min(plan["notional"] * m.get("quant_size", 1.0), slice_room, ctx["team_room"])
            if notional < max(c.min_trade, 25):
                rep["note"] = f"{sym} {kind} setup but slice room only ${max(notional, 0):.0f}"
                continue
            q = quotes[sym]
            target = plan["target"]
            if kind == "REVERSION":
                target = max(q["price"] * (1 + 1.2 * plan["stop_pct"]), min(m["vwap"], target))
            extra = {"stop_px": round(plan["stop"], 4), "stop_pct": round(plan["stop_pct"], 4),
                     "target_px": round(target, 4), "r_per_share": plan["risk_per_share"], "high": q["price"],
                     "opened_hm": ctx["hm"][0] * 60 + ctx["hm"][1], "setup": kind, "strat": self.name,
                     "trend_exit": kind not in ("REVERSION", "SWEEP")}
            if tr.buy(sym, notional, "day", f"{self.label}: {why}; stop {plan['stop']:.2f} (-{plan['stop_pct']:.1%}), "
                      f"target {target:.2f}" + (f"; {m['quant_note']}" if m.get("quant_note") else ""), q, t, extra=extra):
                ctx["team_room"] -= notional
                rep["entries"] += 1
                rep["open"].append(sym)
                rep["note"] = f"entered {sym} on {kind}"
                return


class DayDesk:
    """Supervises the strategy agents for the orchestrator: shared data, exits, hard limits and reporting."""

    def __init__(self, trader, names=None):
        self.tr = trader
        self.agents = [DayStrategyAgent(n) for n in (names or trader.cfg.day_strategies)]

    def agent(self, name):
        return next((a for a in self.agents if a.name == name), None)

    def _snapshots(self, quotes, t):
        tr, c = self.tr, self.tr.cfg
        held = [s for s, p in tr.s["positions"].items() if p["sleeve"] == "day"]
        watch = sorted(set(c.day_symbols) | set(held) | {"SPY"})
        daily = tr.data.bars(watch, "day", 120, ttl=1800)
        bars5 = tr.data.bars(watch, "5minute", 6, ttl=60)
        try:
            self.tilt = factor_tilt({s: daily.get(s, []) for s in c.day_symbols}, c.day_min_dollar_volume)
        except Exception as exc:
            print("[paper] factor tilt failed:", repr(exc))
            self.tilt = {}
        snap = {}
        for sym in watch:
            try:
                snap[sym] = ds.analyze(bars5.get(sym, []), daily.get(sym, []), (quotes.get(sym) or {}).get("price"), t.date())
            except Exception as exc:
                print(f"[paper] day analyze {sym} failed:", repr(exc))
                snap[sym] = None
        return snap

    def _manage(self, quotes, t, snap, hm, flatten):
        tr, c = self.tr, self.tr.cfg
        for sym in [s for s, p in tr.s["positions"].items() if p["sleeve"] == "day"]:
            p, q = tr.s["positions"][sym], quotes.get(sym, {})
            px = q.get("price")
            if not px:
                continue
            if flatten:
                tr.sell(sym, p["qty"], "end-of-day flat (day trades are never held overnight)", q, t)
                continue
            reason, new_stop = ds.manage(p, snap.get(sym), px, hm, c)
            if new_stop and new_stop > (p.get("stop_px") or 0):
                p["stop_px"] = round(new_stop, 4)
            if reason:
                tr.sell(sym, p["qty"], reason, q, t)

    def _team_note(self, equity, t, mandate, hm):
        """Reason the whole team stands aside, or None. Exits keep running regardless."""
        tr, c = self.tr, self.tr.cfg
        if hm < c.day_entry_start or hm >= c.day_entry_end:
            return "outside the day-entry window"
        if mandate and not mandate.allow_new:
            return mandate.note or "orchestrator hold"
        if tr.pdt_limited() and tr.day_trades_5d(t) >= c.pdt_max:
            return "day-trade limit reached"
        pl = tr.day_agent_pl_today(t)
        if pl <= -c.day_loss_limit * equity:
            return f"team loss limit hit ({pl:+.2f}); no more day entries"
        open_now = sum(1 for p in tr.s["positions"].values() if p["sleeve"] == "day")
        if open_now >= c.day_max_open:
            return f"{open_now} day positions open (team max {c.day_max_open})"
        if tr.day_entries_today(t) >= c.day_max_trades:
            return f"team cap of {c.day_max_trades} entries reached"
        return None

    def run(self, quotes, t, equity, mandate, reg, hm):
        from .paper_live import FLATTEN_AT
        tr, c = self.tr, self.tr.cfg
        desk = tr.s.setdefault("desk", {})
        snap = self._snapshots(quotes, t)
        self._manage(quotes, t, snap, hm, hm >= FLATTEN_AT)
        report = {a.name: {"label": a.label, "entries": a.entries_today(tr, t), "pl": a.pl_today(tr, t),
                           "open": a.positions(tr), "note": ""} for a in self.agents}
        desk["day_agents"] = report
        stand_aside = self._team_note(equity, t, mandate, hm)
        if hm >= FLATTEN_AT:
            stand_aside = "flattened for the close"
        spy = snap.get("SPY")
        if not stand_aside and spy and spy["price"] < spy["vwap"] and spy["ema9"] < spy["ema21"]:
            stand_aside = "market filter: SPY below VWAP with EMA9<EMA21"
        if stand_aside:
            desk["day_note"] = stand_aside
            for r in report.values():
                r["note"] = r["note"] or stand_aside
            return
        n = max(1, len(self.agents))
        scale = mandate.scale if mandate else 1.0
        budget = equity * (mandate.budget_pct if mandate else c.day_pct) * scale
        deployed = sum(a.deployed(tr, quotes) for a in self.agents)
        ctx = {"tr": tr, "cfg": c, "quotes": quotes, "snap": snap, "t": t, "hm": hm, "equity": equity, "scale": scale,
               "slice": budget / min(n, 4), "team_room": budget - deployed, "report": report,
               "agent_max_entries": max(2, math.ceil(c.day_max_trades / n)),
               "daily": self._daily_scores(quotes, t), "tilt": getattr(self, "tilt", {}),
               "earnings": self._earnings_today(t), "rank": self._rank_scores(snap)}
        tr.signals.refresh(c.day_symbols, "day")
        # agents with the better day so far get first call on shared cash and team budget
        for agent in sorted(self.agents, key=lambda a: -a.pl_today(tr, t)):
            try:
                agent.run(ctx)
            except Exception as exc:
                print(f"[paper] day agent {agent.name} failed:", repr(exc))
                report[agent.name]["note"] = "error; see log"
            if tr.day_entries_today(t) >= c.day_max_trades:
                break
        desk["day_note"] = f"{sum(r['entries'] for r in report.values())}/{c.day_max_trades} entries; " \
                           f"budget ${budget:,.0f}, slice ${budget / min(n, 4):,.0f} per agent"

    def _rank_scores(self, snap):
        """Priority from the historical indicator ranking; computed from the daily bars the snapshots already used."""
        tr = self.tr
        if not tr.rank.w:
            return {}
        daily = tr.data.bars(list(tr.cfg.day_symbols), "day", 400, ttl=3600)
        return {s: tr.rank.score(daily.get(s, []))[0] for s in tr.cfg.day_symbols}

    def _earnings_today(self, t):
        """Symbols reporting today (any timing: the gap risk is on the open or the close); cached for an hour."""
        if not self.tr.cfg.skip_earnings_day:
            return set()
        cached = getattr(self, "_earn", None)
        if cached and (t - cached[0]).total_seconds() < 3600 and cached[1] == t.date():
            return cached[2]
        try:
            rows = self.tr.data.earnings(2)
        except Exception:
            return cached[2] if cached else set()
        today = t.date().isoformat()
        out = {e.get("symbol") for e in rows if (e.get("report") or {}).get("date") == today}
        self._earn = (t, t.date(), out)
        return out

    def _daily_scores(self, quotes, t):
        """Four-pillar daily score per day symbol, refreshed every 15 minutes."""
        cached = getattr(self, "_scores", None)
        if cached and (t - cached[0]).total_seconds() < 900:
            return cached[1]
        try:
            out = daily_eval(list(self.tr.cfg.day_symbols), self.tr.data, quotes)
        except Exception:
            out = {}
        self._scores = (t, out)
        return out
