"""Paper-only trading desk: an orchestrator that aligns a growth agent, an options sub-manager (with one agent per
options strategy) and a day-trading team (one agent per intraday strategy) on the daily and weekly goals.

Nothing here places a real order. The orchestrator only sets budgets and risk dials (a `Mandate`) for each
agent; the agents trade through the same paper broker methods as before, so every existing guard still applies
(cash-secured puts / covered calls only, never naked, no leverage, no shorting).

Goals are measured, never chased: falling short of a goal never raises a cap above its configured limit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta


from .day_agents import DayDesk
from .historian import Historian
from .options_agents import OptionsManager

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
    brief: dict = field(default_factory=dict)  # historian briefing for this team (recent results, symbols to avoid/favor)


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

    # weekly capital review: each team's budget moves within [FLOOR, CEIL] x its configured base, and never past
    # a hard ceiling, so a hot week can enlarge a team but not remove the account's overall limits
    FLOOR, CEIL, MAX_CUT, MAX_RAISE = 0.1, 1.5, 0.5, 0.3
    HARD_CAP = {"growth": 0.70, "options": 0.70, "day": 0.40}

    def __init__(self, trader):
        self.tr = trader
        c = trader.cfg
        self.historian = Historian(c)
        self.base = {"growth": min(c.growth_pct, 1 - self.RESERVE - c.opt_pct), "options": c.opt_pct, "day": c.day_pct}
        trader.s.setdefault("alloc", {
            "mult": {a: 1.0 for a in AGENTS},
            "base": dict(self.base),
            "ts": None,
            "history": [],
            "score": {a: 0.0 for a in AGENTS},
            "note": "default allocations; weekly review begins after the first market session",
        })

    def weekly_review(self, quotes, t, equity):
        """Once every 7 days, resize every active team's budget by its trailing-week return on the budget it was
        given (realized plus open): a team that lost its whole budget is cut by MAX_CUT, down to FLOOR of its base,
        and gains raise it by up to MAX_RAISE. Teams with no activity are left alone. Returns a note or None."""
        s = self.tr.s
        al = s.setdefault("alloc", {"mult": {a: 1.0 for a in AGENTS}, "ts": None, "history": []})
        last = al.get("ts")
        if last and (t - datetime.fromisoformat(last)).total_seconds() < 7 * 86400:
            return None
        since = (t - timedelta(days=7)).isoformat()
        pnl = {a: 0.0 for a in AGENTS}
        active = {a: 0 for a in AGENTS}
        for x in s["trades"]:
            a = agent_of(x)
            if a in pnl and "realized" in x and x["ts"] >= since:
                pnl[a] += x["realized"]
                active[a] += 1
        for a, v in self.attribution(quotes, t).items():
            pnl[a] += v["open"]
        score = {a: pnl[a] / equity for a in AGENTS}
        mult = dict(al["mult"])
        moves = []
        for a in AGENTS:
            if not (active[a] >= 2 or pnl[a]):
                continue  # no activity: left alone
            budget = equity * min(self.HARD_CAP[a], self.base[a] * mult[a])
            ret = pnl[a] / budget if budget else 0.0  # return on the capital the team was given
            new = mult[a] * (1 + max(-self.MAX_CUT, min(self.MAX_RAISE, ret)))
            mult[a] = max(self.FLOOR, min(self.CEIL, new))
            moves.append(f"{LABELS[a]} {ret:+.1%} of budget -> {mult[a]:.0%} of base")
        note = ("weekly review: " + "; ".join(moves)) if moves else "weekly review: no team activity; allocations unchanged"
        al.update(mult=mult, base=dict(self.base), ts=t.isoformat(), score={a: round(score[a], 5) for a in AGENTS}, note=note)
        al["history"] = (al["history"] + [{"ts": t.isoformat(), "mult": dict(mult), "score": al["score"]}])[-26:]
        return note

    def budgets(self):
        mult = (self.tr.s.get("alloc") or {}).get("mult") or {}
        out = {a: min(self.HARD_CAP[a], self.base[a] * mult.get(a, 1.0)) for a in AGENTS}
        out["growth"] = min(out["growth"], 1 - self.RESERVE - out["options"])
        return out

    def plan(self, quotes, t, equity, reg):
        tr, c, s = self.tr, self.tr.cfg, self.tr.s
        review = self.weekly_review(quotes, t, equity)
        bud = self.budgets()
        c.opt_pct = bud["options"]  # the options sub-manager reads its collateral cap from the config
        day_ret = equity / s["day"]["open_equity"] - 1
        week_ret = equity / s["week"]["open_equity"] - 1
        brief = {}
        if c.brief_on:
            try:
                brief = self.historian.build(s["trades"], t, agent_of, equity, s.get("bench_daily"))
            except Exception as exc:
                print("[paper] historian failed:", repr(exc))
        # growth + options hold capital overnight, so together they leave the cash reserve untouched
        growth = Mandate("growth", bud["growth"])
        options = Mandate("options", bud["options"])
        day = Mandate("day", bud["day"], scale=reg.get("day_scale", 1.0))
        head = [n for n in [review or (s.get("alloc") or {}).get("note")] if n]
        notes = []

        if reg.get("name") not in (None, "normal"):
            day.scale = min(day.scale, reg.get("day_scale", 0.5))
            notes.append(f"{reg['name']} volatility: day sizing reduced to {day.scale:.0%}")

        if day_ret >= c.daily_max:
            day.allow_new = options.allow_new = False
            day.note = options.note = f"daily goal reached ({day_ret:+.2%}): banking, no new risk"
            notes.append(day.note)
        elif day_ret <= self.DRAWDOWN_DAY:
            day.allow_new = False
            day.note = f"day down {day_ret:+.2%}: day entries paused"
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
        notes = head + notes
        plan = Plan({"growth": growth, "options": options, "day": day}, day_ret, week_ret, stance, notes)
        for name, mandate in plan.mandates.items():
            mandate.brief = (brief.get("teams") or {}).get(name, {})
        s["desk"] = {**s.get("desk", {}), **plan.as_state(t.isoformat())}
        if brief:
            s["desk"]["briefing"] = brief
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
        from . import growth_members, single_trade as st
        tr, c = self.tr, self.tr.cfg
        one = tr.single_state()
        if "growth" in one:
            return
        if hm >= st.ENTRY_END:
            one["growth"] = {"sym": None, "note": "no qualifying action in the entry window; no trade today"}
            return
        etf_budget = equity * max(0.0, mandate.budget_pct - (reg.get("hedge_target") or 0.0)) * mandate.scale
        avoid = (mandate.brief or {}).get("avoid", {})
        weights = self.weights()
        bars = tr.data.bars(list(weights), "day", 380, ttl=1800)
        ev = st.evaluate(list(weights), tr.data, quotes, bars={k: v[-150:] for k, v in bars.items()})
        tr.signals.refresh(list(weights), "growth")
        gm = growth_members.members({k: [b["close"] for b in v if b.get("close")] for k, v in bars.items()},
                                    {k: (quotes.get(k) or {}).get("price") for k in weights}, tr.signals.cash_rate())
        tr.s["desk"]["growth_members"] = {k: {"score": round(v["score"], 3), "bearish": v["bearish"]} for k, v in gm.items()}
        tr.quant.ensure(list(weights), "long")
        cands = []  # (priority, run, label)
        for sym, w in weights.items():
            q, e = quotes.get(sym), ev.get(sym)
            if not q or not q.get("price") or not e:
                continue
            px, held, ma50 = q["price"], tr.s["positions"].get(sym), e["ma50"]
            target = etf_budget * w
            member = gm.get(sym) or {}
            # a MA50 break alone whipsaws; it needs the slower members to agree unless the break is deep
            if held and px < ma50 * 0.985 and (member.get("bearish") or px < ma50 * 0.97 or not member):
                cands.append((3.0, lambda sym=sym, held=held, q=q, ma50=ma50: tr.sell(
                    sym, held["qty"], f"ETF trend break (below MA50 {ma50:.2f})", q, t), f"sell {sym}"))
            elif held:
                cur = held["qty"] * px
                if cur > target * (1 + c.rebalance_band) and cur - target >= c.min_trade:
                    cands.append((0.4, lambda sym=sym, held=held, q=q, cur=cur, target=target, px=px: tr.sell(
                        sym, min(held["qty"], (cur - target) / px),
                        f"rebalance: {cur / equity:.0%} vs {target / equity:.0%} target weight", q, t), f"trim {sym}"))
            veto, qscore, _size, qnote = tr.quant.verdict(sym, "long")
            if veto:
                tr.s["desk"].setdefault("quant_vetoes", {})[sym] = f"{qscore:+.2f}"
            if (px > ma50 * (1 + c.entry_buffer) and mandate.allow_new and e["score"] >= c.growth_min_score
                    and e["coverage"] >= c.single_min_coverage and not veto and not member.get("bearish")
                    and not tr.signals.bearish(sym) and sym not in avoid):
                cur = held["qty"] * px if held else 0.0
                gap = min(target - cur, tr.free_cash())
                if gap >= max(c.min_trade, 25 if held else 0) and (not held or cur < target * (1 - c.rebalance_band)):
                    cands.append((e["score"] + 0.3 * qscore + 0.3 * member.get("score", 0.0), lambda sym=sym, q=q, gap=gap, e=e, qnote=qnote: tr.buy(
                        sym, gap, "core", f"single daily trade: {st.why(e)}, stop -{tr.stop_for('core', e['vol']):.1%}"
                        + (f"; {qnote}" if qnote else ""), q, t,
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
                last = tr.s["trades"][-1] if tr.s["trades"] else {}
                one["growth"] = {"sym": label.split()[-1], "note": f"{label} ({last.get('reason')})" if last.get("reason") else label}
                return


class Desk:
    def __init__(self, trader):
        self.orchestrator = Orchestrator(trader)
        self.growth = GrowthAgent(trader)
        self.options = OptionsManager(trader)  # sub-manager: reports to the orchestrator, runs the options agents
        self.day = DayDesk(trader)  # one independent agent per day-trading strategy
