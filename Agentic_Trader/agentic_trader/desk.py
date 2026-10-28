"""Paper-only trading desk: an orchestrator that aligns a growth agent, an options-income agent and the
day-trading agent on the daily and weekly goals.

Nothing here places a real order. The orchestrator only sets budgets and risk dials (a `Mandate`) for each
agent; the agents trade through the same paper broker methods as before, so every existing guard still applies
(cash-secured puts / covered calls only, never naked, no leverage, no shorting).

Goals are measured, never chased: falling short of a goal never raises a cap above its configured limit.
"""
from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import numpy as np

from .paper_options import MULT

AGENTS = ("growth", "options", "day")
LABELS = {"growth": "Growth agent", "options": "Options agent", "day": "Day agent"}
# trade-log sleeve -> owning agent
SLEEVE_AGENT = {"core": "growth", "hedge": "growth", "income": "options", "option": "options", "day": "day"}


@dataclass
class Mandate:
    name: str
    budget_pct: float
    scale: float = 1.0
    allow_new: bool = True
    note: str = ""


@dataclass
class Plan:
    mandates: dict = field(default_factory=dict)
    day_ret: float = 0.0
    week_ret: float = 0.0
    stance: str = ""
    notes: list = field(default_factory=list)

    def as_state(self, ts):
        return {
            "ts": ts, "stance": self.stance, "day_ret": self.day_ret, "week_ret": self.week_ret, "notes": self.notes,
            "mandates": {k: {"budget_pct": m.budget_pct, "scale": m.scale, "allow_new": m.allow_new, "note": m.note}
                         for k, m in self.mandates.items()},
        }


def agent_of(trade):
    if trade.get("side") == "option":
        return "options"
    return SLEEVE_AGENT.get(trade.get("sleeve"))


class Orchestrator:
    """Reads progress against the daily/weekly goals plus regime and cash, then issues one mandate per agent."""

    RESERVE = 0.05
    DRAWDOWN_DAY = -0.02
    DRAWDOWN_WEEK = -0.04

    def __init__(self, trader):
        self.tr = trader

    def plan(self, quotes, t, equity, reg):
        tr, c, s = self.tr, self.tr.cfg, self.tr.s
        day_ret = equity / s["day"]["open_equity"] - 1
        week_ret = equity / s["week"]["open_equity"] - 1
        # growth + options hold capital overnight, so together they leave the cash reserve untouched
        growth_cap = min(c.growth_pct, 1 - self.RESERVE - c.opt_pct)
        growth = Mandate("growth", growth_cap)
        options = Mandate("options", c.opt_pct)
        day = Mandate("day", c.day_pct, scale=reg.get("day_scale", 1.0))
        notes = []

        if reg.get("name") not in (None, "normal"):
            options.scale = min(options.scale, reg.get("day_scale", 0.5))
            notes.append(f"{reg['name']} volatility: day and options sizing reduced to {options.scale:.0%}")

        if day_ret >= c.daily_max:
            day.allow_new = options.allow_new = False
            day.note = options.note = f"daily goal reached ({day_ret:+.2%}): banking, no new risk"
            notes.append(day.note)
        elif day_ret <= self.DRAWDOWN_DAY:
            day.allow_new = False
            day.note = f"day down {day_ret:+.2%}: day entries paused"
            options.scale = min(options.scale, 0.5)
            notes.append(day.note)

        if week_ret >= c.week_max:
            day.allow_new = options.allow_new = False
            day.note = options.note = f"weekly goal reached ({week_ret:+.2%}): protecting gains"
            notes.append(options.note)
        elif week_ret <= self.DRAWDOWN_WEEK:
            day.scale = min(day.scale, 0.5)
            if reg.get("name") not in (None, "normal"):
                options.allow_new = False
            notes.append(f"week down {week_ret:+.2%}: risk dials cut, caps unchanged")

        # a day/week below target never lifts a cap; the shortfall is simply reported
        if day_ret < c.daily_min and not notes:
            notes.append(f"behind day goal ({day_ret:+.2%} vs {c.daily_min:.0%}): staying inside risk caps, no chasing")
        elif not notes:
            notes.append("on pace: all agents operating at normal mandates")

        # every agent must stay inside what cash can actually fund
        invested_overnight = sum(self._value(p, sym, quotes) for sym, p in s["positions"].items()
                                 if p["sleeve"] in ("core", "hedge", "income")) + tr.income.collateral()
        if invested_overnight > (1 - self.RESERVE) * equity:
            growth.allow_new = options.allow_new = False
            notes.append("cash reserve reached: no new growth or options capital")

        stance = ("risk-off" if not (day.allow_new or options.allow_new)
                  else "reduced" if min(day.scale, options.scale) < 1 else "normal")
        plan = Plan({"growth": growth, "options": options, "day": day}, day_ret, week_ret, stance, notes)
        s["desk"] = {**s.get("desk", {}), **plan.as_state(t.isoformat())}
        return plan

    @staticmethod
    def _value(p, sym, quotes):
        return p["qty"] * ((quotes.get(sym) or {}).get("price") or p["avg"])

    # ---- attribution
    def attribution(self, quotes, t):
        s = self.tr.s
        today = t.date().isoformat()
        monday = (t - timedelta(days=t.weekday())).date().isoformat()
        rows = {a: {"today": 0.0, "week": 0.0, "open": 0.0, "value": 0.0, "fees": 0.0} for a in AGENTS}
        for x in s["trades"]:
            a = agent_of(x)
            if a not in rows or "realized" not in x:
                continue
            if x["ts"][:10] == today:
                rows[a]["today"] += x["realized"]
            if x["ts"][:10] >= monday:
                rows[a]["week"] += x["realized"]
        for sym, p in s["positions"].items():
            a = SLEEVE_AGENT.get(p["sleeve"])
            px = (quotes.get(sym) or {}).get("price") or p["avg"]
            if a in rows:
                rows[a]["open"] += (px - p["avg"]) * p["qty"]
                rows[a]["value"] += px * p["qty"]
        rows["options"]["value"] += self.tr.income.collateral()
        return rows


class GrowthAgent:
    """Long-term proportional growth: target weights across the core ETFs, trend-filtered, rebalanced inside a band,
    with the volatility hedge as its protective leg."""

    def __init__(self, trader):
        self.tr = trader

    def weights(self):
        c = self.tr.cfg
        raw = c.growth_weights or {}
        picked = {s: raw.get(s, 0.0) for s in c.etfs} if raw else {s: 1.0 for s in c.etfs}
        total = sum(picked.values()) or 1.0
        return {s: w / total for s, w in picked.items()}

    def run(self, quotes, t, equity, mandate, reg, hm=(9, 35)):
        """One trade per day, early in the open: the highest-priority of (protective sell, hedge change,
        best-ranked ETF buy, over-weight rebalance). Protective actions outrank buys."""
        from . import single_trade as st
        tr, c = self.tr, self.tr.cfg
        one = tr.single_state()
        if "growth" in one:
            return
        if hm >= st.ENTRY_END:
            one["growth"] = {"sym": None, "note": "no qualifying action in the entry window; no trade today"}
            return
        etf_budget = equity * max(0.0, mandate.budget_pct - (reg.get("hedge_target") or 0.0)) * mandate.scale
        weights = self.weights()
        bars = tr.data.bars(list(weights), "day", 150, ttl=1800)
        ev = st.evaluate(list(weights), tr.data, quotes, bars=bars)
        cands = []  # (priority, run, label)
        for sym, w in weights.items():
            q, e = quotes.get(sym), ev.get(sym)
            if not q or not q.get("price") or not e:
                continue
            px, held, ma50 = q["price"], tr.s["positions"].get(sym), e["ma50"]
            target = etf_budget * w
            if held and px < ma50 * 0.985:
                cands.append((3.0, lambda sym=sym, held=held, q=q, ma50=ma50: tr.sell(
                    sym, held["qty"], f"ETF trend break (below MA50 {ma50:.2f})", q, t), f"sell {sym}"))
            elif held:
                cur = held["qty"] * px
                if cur > target * (1 + c.rebalance_band) and cur - target >= c.min_trade:
                    cands.append((0.4, lambda sym=sym, held=held, q=q, cur=cur, target=target, px=px: tr.sell(
                        sym, min(held["qty"], (cur - target) / px),
                        f"rebalance: {cur / equity:.0%} vs {target / equity:.0%} target weight", q, t), f"trim {sym}"))
            if px > ma50 and mandate.allow_new and e["score"] >= c.growth_min_score and e["coverage"] >= c.single_min_coverage:
                cur = held["qty"] * px if held else 0.0
                gap = min(target - cur, tr.free_cash())
                if gap >= max(c.min_trade, 25 if held else 0) and (not held or cur < target * (1 - c.rebalance_band)):
                    cands.append((e["score"], lambda sym=sym, q=q, gap=gap, e=e: tr.buy(
                        sym, gap, "core", f"single daily trade: {st.why(e)}, stop -{tr.stop_for('core', e['vol']):.1%}", q, t,
                        vol_ann=e["vol"]), f"buy {sym}"))
        plan = tr.hedge_plan(quotes, equity, reg)
        if plan:
            side, sym, amt, why, urgent = plan
            q = quotes[sym]
            fn = (lambda: tr.buy(sym, amt, "hedge", why, q, t)) if side == "buy" else (lambda: tr.sell(sym, amt, why, q, t))
            cands.append((2.0 if urgent else 0.5, fn, f"hedge {side}"))
        tr.s["desk"]["growth_candidates"] = [(lab, round(p, 3)) for p, _, lab in sorted(cands, key=lambda x: -x[0])[:6]]
        for _, fn, label in sorted(cands, key=lambda x: -x[0]):
            if fn():
                one["growth"] = {"sym": label.split()[-1], "note": label}
                return


class DayAgent:
    """The existing day-trading sleeve, run inside the budget and risk dials the orchestrator hands it."""

    def __init__(self, trader):
        self.tr = trader

    def run(self, quotes, t, equity, mandate, reg, hm):
        self.tr.day_sleeve(quotes, t, equity, reg, hm, mandate)


class OptionsAgent:
    """Cash-secured puts and covered calls only. Scans a wide universe, ranks every candidate by
    delta-adjusted annualised yield, and opens the best ones that fit the budget. Records why nothing opened."""

    DELTA_RANGE = (0.04, 0.35)
    MIN_OTM = 0.02

    def __init__(self, trader):
        self.tr = trader

    def run(self, quotes, t, equity, mandate):
        inc = self.tr.income
        inc.enforce(quotes, t)
        inc.manage(t)
        if not mandate.allow_new:
            self._note(f"no new options: {mandate.note or 'orchestrator hold'}")
            return
        self.scan(quotes, t, equity, mandate)

    def _note(self, text):
        self.tr.s.setdefault("desk", {})["options_note"] = text

    def _earnings(self, days, today):
        try:
            rows = self.tr.data.earnings(days)
        except Exception:
            return {}
        out = {}
        for e in rows:
            rep = e.get("report") or {}
            d = rep.get("date")
            if not d or d < today.isoformat() or (d == today.isoformat() and rep.get("timing") == "am"):
                continue
            out[e.get("symbol")] = min(d, out.get(e.get("symbol"), d))
        return out

    def _best_put(self, sym, px, t, earn_date, room):
        d, c = self.tr.data, self.tr.cfg
        best = None
        exps = [e for e in d.option_expirations(sym)
                if c.opt_min_dte <= (date.fromisoformat(e) - t.date()).days <= c.opt_max_dte][:2]
        for exp in exps:
            if earn_date and earn_date <= exp:
                continue
            dte = (date.fromisoformat(exp) - t.date()).days
            strikes = [x for x in d.option_contracts(sym, exp, "put")
                       if x["strike"] <= px * (1 - max(c.opt_otm, self.MIN_OTM)) and x["strike"] * MULT <= room]
            strikes = sorted(strikes, key=lambda x: -x["strike"])[:6]
            if not strikes:
                continue
            quotes = d.option_quotes([x["id"] for x in strikes])
            for x in strikes:
                oq = quotes.get(x["id"])
                if not self.tr.income._liquid(oq, c):
                    continue
                delta = abs(oq.get("delta") or 0)
                if delta and not self.DELTA_RANGE[0] <= delta <= self.DELTA_RANGE[1]:
                    continue
                score = oq["bid"] / x["strike"] / dte * 365 * (1 - delta)
                if best is None or score > best[3]:
                    best = (x, oq, dte, score)
        return best

    def scan(self, quotes, t, equity, mandate):
        tr, c, s, inc = self.tr, self.tr.cfg, self.tr.s, self.tr.income
        last = s.get("opt_scan")
        if last and (t - datetime.fromisoformat(last)).total_seconds() < c.opt_scan_min * 60:
            return
        if not ((10, 0) <= (t.hour, t.minute) < (15, 30)):
            return
        s["opt_scan"] = t.isoformat()
        stats = Counter()
        earn = self._earnings(c.opt_max_dte, t.date())
        taken = set(c.etfs) | set(c.day_symbols) | {c.hedge}
        budget = equity * mandate.budget_pct * mandate.scale
        used = inc.collateral() + sum(p["qty"] * ((quotes.get(sym) or {}).get("price") or p["avg"])
                                      for sym, p in s["positions"].items() if p["sleeve"] == "income")
        room = min(budget - used, tr.free_cash())

        for sym, pos in list(s["positions"].items()):
            if pos["sleeve"] != "income":
                continue
            px = (quotes.get(sym) or {}).get("price")
            if not px or inc.uncovered_shares(sym) < MULT or any(o["sym"] == sym for o in inc.opts):
                continue
            try:
                pick = inc._pick(sym, "call", px, pos["avg"], t)
                if pick and inc.sell_to_open("call", sym, pick[0], pick[1], int(inc.uncovered_shares(sym) // MULT), t):
                    stats["covered_calls"] += 1
            except Exception as exc:
                print(f"[paper] covered call {sym} failed:", repr(exc))

        open_puts = sum(1 for o in inc.opts if o["type"] == "put")
        held = {o["sym"] for o in inc.opts} | set(s["positions"])
        candidates = []
        for sym in c.opt_symbols:
            q = quotes.get(sym) or {}
            px = q.get("price")
            if sym in taken or sym in held:
                stats["already held"] += 1
            elif not px:
                stats["no quote"] += 1
            elif px * MULT * (1 - max(c.opt_otm, self.MIN_OTM)) > room:
                stats["too large for budget"] += 1
            elif (q.get("change_pct") or 0) < -0.03:
                stats["falling >3%"] += 1
            else:
                try:
                    best = self._best_put(sym, px, t, earn.get(sym), room)
                except Exception as exc:
                    print(f"[paper] option scan {sym} failed:", repr(exc))
                    stats["data error"] += 1
                    continue
                if best:
                    candidates.append((best[3], sym, best))
                else:
                    stats["earnings or no liquid strike" if sym in earn else "no liquid strike"] += 1
        opened = 0
        for score, sym, (contract, oq, dte, _) in sorted(candidates, key=lambda x: -x[0]):
            if open_puts >= c.opt_max_positions or contract["strike"] * MULT > room:
                continue
            if inc.sell_to_open("put", sym, contract, oq, 1, t):
                open_puts += 1
                opened += 1
                room -= contract["strike"] * MULT
        parts = [f"{n} {why}" for why, n in stats.most_common() if why != "covered_calls"]
        self._note(f"scanned {len(c.opt_symbols)} names: opened {opened} put(s)"
                   + (f", {stats['covered_calls']} call(s)" if stats["covered_calls"] else "")
                   + (f"; skipped {', '.join(parts)}" if parts else ""))


class Desk:
    def __init__(self, trader):
        self.orchestrator = Orchestrator(trader)
        self.growth = GrowthAgent(trader)
        self.options = OptionsAgent(trader)
        self.day = DayAgent(trader)
