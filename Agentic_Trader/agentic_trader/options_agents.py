"""Options team (paper only): a sub-manager that reports to the orchestrator and runs one agent per options strategy.

Only cash-secured puts and covered calls exist here, so no agent can ever open an unlimited-loss position; every
open goes through `Income.sell_to_open`, which refuses anything else. The `OptionsManager` owns what must be common
(the risk guard, marks and exits, the capital split, the report). Each agent owns one strategy:

- yield puts      higher-delta cash-secured puts ranked by delta-adjusted annualised yield
- defensive puts  low-delta, further-out-of-the-money cash-secured puts on the same universe
- covered calls   calls against shares assigned from puts, never below cost basis
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime

from .paper_options import MULT

MIN_OTM = 0.02


def _earnings(tr, days, today):
    try:
        rows = tr.data.earnings(days)
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


class _Agent:
    name, label, share = "", "", 0.0

    def __init__(self, trader):
        self.tr = trader

    def open_puts(self):
        return [o for o in self.tr.income.opts if o["type"] == "put" and o.get("strat") == self.name]

    def collateral(self):
        return sum(o["strike"] * MULT * o["qty"] for o in self.open_puts())

    def throttled(self, t):
        key = f"opt_scan_{self.name}"
        last = self.tr.s.get(key)
        if last and (t - datetime.fromisoformat(last)).total_seconds() < self.tr.cfg.opt_scan_min * 60:
            return True
        if not ((10, 0) <= (t.hour, t.minute) < (15, 30)):
            return True
        self.tr.s[key] = t.isoformat()
        return False


class PutAgent(_Agent):
    DELTA_RANGE = (0.04, 0.35)
    OTM_FLOOR = MIN_OTM
    MAX_DROP = -0.03
    MIN_VRP = 0.0  # required implied/realized vol ratio; 0 means the ratio only tilts the ranking

    def _vrp(self, sym, iv):
        """Implied vol over a blend of 20-day and 1-year realized vol: above 1 the market pays for the risk it sells."""
        r = self.tr.quant.get(sym, "options")
        if not iv or not r or "error" in r:
            return None
        rv = [x for x in (r.get("rv_recent_ann"), r.get("rv_ann")) if x]
        return iv / (sum(rv) / len(rv)) if rv else None

    def _best(self, sym, px, t, earn_date, room):
        d, c = self.tr.data, self.tr.cfg
        best = None
        otm = max(c.opt_otm, self.OTM_FLOOR)
        exps = [e for e in d.option_expirations(sym)
                if c.opt_min_dte <= (date.fromisoformat(e) - t.date()).days <= c.opt_max_dte][:2]
        for exp in exps:
            if earn_date and earn_date <= exp:
                continue
            dte = (date.fromisoformat(exp) - t.date()).days
            strikes = [x for x in d.option_contracts(sym, exp, "put")
                       if x["strike"] <= px * (1 - otm) and x["strike"] * MULT <= room]
            strikes = sorted(strikes, key=lambda x: -x["strike"])[:6]
            if not strikes:
                continue
            quotes = d.option_quotes([x["id"] for x in strikes])
            for x in strikes:
                oq = quotes.get(x["id"])
                if not self.tr.income._liquid(oq, c) or oq["bid"] < c.opt_min_credit:
                    continue
                delta = abs(oq.get("delta") or 0)
                if delta and not self.DELTA_RANGE[0] <= delta <= self.DELTA_RANGE[1]:
                    continue
                score = oq["bid"] / x["strike"] / dte * 365 * (1 - delta)
                if best is None or score > best[3]:
                    best = (x, oq, dte, score, oq.get("iv"))
        return best

    def run(self, quotes, t, equity, budget, room_total):
        """`budget` is this agent's slice in dollars; `room_total` is what the whole team can still commit."""
        tr, c, s, inc = self.tr, self.tr.cfg, self.tr.s, self.tr.income
        if self.throttled(t):
            return {"note": "waiting for next scan window", "opened": 0}
        stats = Counter()
        earn = _earnings(tr, c.opt_max_dte, t.date())
        taken = set(c.etfs) | set(c.day_symbols) | {c.hedge}
        room = min(budget - self.collateral(), room_total, tr.free_cash())
        held = {o["sym"] for o in inc.opts} | set(s["positions"])
        total_puts = sum(1 for o in inc.opts if o["type"] == "put")
        candidates = []
        stopouts = s.get("opt_stopouts", {})
        scan = [x for x in c.opt_symbols if x not in taken and x not in held]
        tr.quant.ensure(scan, "options")
        tr.signals.refresh(scan, "options")
        for sym in c.opt_symbols:
            q = quotes.get(sym) or {}
            px = q.get("price")
            if sym in taken or sym in held:
                stats["already held"] += 1
            elif sym in stopouts and (t.date() - date.fromisoformat(stopouts[sym])).days < c.opt_stop_cooldown_days:
                stats["cooling down after stop-out"] += 1
            elif not px:
                stats["no quote"] += 1
            elif px * MULT * (1 - max(c.opt_otm, self.OTM_FLOOR)) > room:
                stats["too large for budget"] += 1
            elif (q.get("change_pct") or 0) < self.MAX_DROP:
                stats[f"falling >{abs(self.MAX_DROP):.0%}"] += 1
            elif tr.quant.verdict(sym, "options")[0]:
                stats["quant veto"] += 1
            elif tr.signals.bearish(sym):
                stats["bearish news"] += 1
            else:
                try:
                    best = self._best(sym, px, t, earn.get(sym), room)
                except Exception as exc:
                    print(f"[paper] {self.name} scan {sym} failed:", repr(exc))
                    stats["data error"] += 1
                    continue
                vrp = self._vrp(sym, best[4]) if best else None
                if best and self.MIN_VRP and (vrp is None or vrp < self.MIN_VRP):
                    stats["no vol premium"] += 1
                elif best:
                    tilt = min(1.5, max(0.7, vrp)) if vrp else 1.0
                    candidates.append((best[3] * (1 + 0.5 * tr.quant.verdict(sym, "options")[1]) * tilt, sym, best))
                else:
                    stats["earnings or no liquid strike" if sym in earn else "no liquid strike"] += 1
        opened = 0
        for _, sym, (contract, oq, dte, _s, _iv) in sorted(candidates, key=lambda x: -x[0]):
            if total_puts + opened >= c.opt_max_positions or contract["strike"] * MULT > room:
                continue
            if inc.sell_to_open("put", sym, contract, oq, 1, t, strat=self.name):
                opened += 1
                room -= contract["strike"] * MULT
        parts = [f"{n} {why}" for why, n in stats.most_common()]
        return {"opened": opened, "note": f"scanned {len(c.opt_symbols)} names: opened {opened} put(s)"
                + (f"; skipped {', '.join(parts[:4])}" if parts else "")}


class YieldPuts(PutAgent):
    name, label, share = "yield_puts", "Yield puts", 0.6
    DELTA_RANGE = (0.15, 0.35)


class DefensivePuts(PutAgent):
    name, label, share = "defensive_puts", "Defensive puts", 0.4
    DELTA_RANGE = (0.04, 0.15)
    OTM_FLOOR = 0.06
    MAX_DROP = -0.02


class VRPPuts(PutAgent):
    """Sinclair-style volatility risk premium: only sell puts where implied vol is at least 15% above realized,
    at 10-25 delta (roughly one standard deviation out), so the premium compensates for the tail."""
    name, label, share = "vrp_puts", "Vol-premium puts", 0.5
    DELTA_RANGE = (0.10, 0.25)
    OTM_FLOOR = 0.04
    MIN_VRP = 1.15


class CoveredCalls(_Agent):
    name, label, share = "covered_calls", "Covered calls", 0.0

    def run(self, quotes, t, equity, budget, room_total):
        s, inc = self.tr.s, self.tr.income
        if self.throttled(t):
            return {"note": "waiting for next scan window", "opened": 0}
        opened = 0
        for sym, pos in list(s["positions"].items()):
            if pos["sleeve"] != "income":
                continue
            px = (quotes.get(sym) or {}).get("price")
            if not px or inc.uncovered_shares(sym) < MULT or any(o["sym"] == sym for o in inc.opts):
                continue
            try:
                pick = inc._pick(sym, "call", px, pos["avg"], t)
                if pick and inc.sell_to_open("call", sym, pick[0], pick[1], int(inc.uncovered_shares(sym) // MULT), t,
                                             strat=self.name):
                    opened += 1
            except Exception as exc:
                print(f"[paper] covered call {sym} failed:", repr(exc))
        held = sum(1 for sym, p in s["positions"].items() if p["sleeve"] == "income")
        return {"opened": opened, "note": f"{held} assigned position(s) checked: opened {opened} call(s)"}


class OptionsManager:
    """Sub-manager: takes the orchestrator's options mandate, splits it across its agents, and reports back."""

    def __init__(self, trader):
        self.tr = trader
        self.agents = [VRPPuts(trader), YieldPuts(trader), DefensivePuts(trader), CoveredCalls(trader)]  # selective agent first

    def report_lines(self, t):
        rep = self.tr.s.get("desk", {}).get("options_agents") or {}
        return [f"  - {r['label']}: {r['open']} open, premium today ${r['premium_today']:,.0f}, realized today "
                f"{r['pl_today']:+,.2f}; {r['note']}" for r in rep.values()]

    def _stats(self, name, today):
        trades = [x for x in self.tr.s["trades"] if x.get("strat") == name and x["ts"][:10] == today]
        prem = sum(float(x["px"]) * MULT * x["qty"] for x in trades if x["side"] == "option" and x["desc"].startswith("SELL TO OPEN"))
        pl = sum(x.get("realized", 0.0) for x in trades if "realized" in x)
        return prem, pl

    def run(self, quotes, t, equity, mandate):
        tr, s, inc = self.tr, self.tr.s, self.tr.income
        inc.enforce(quotes, t)  # the risk guard belongs to the manager, not to any one strategy
        inc.manage(t)
        desk = s.setdefault("desk", {})
        today = t.date().isoformat()
        report = {}
        for a in self.agents:
            prem, pl = self._stats(a.name, today)
            n_open = sum(1 for o in inc.opts if o.get("strat") == a.name)
            report[a.name] = {"label": a.label, "open": n_open, "premium_today": prem, "pl_today": pl, "note": ""}
        desk["options_agents"] = report
        if not mandate.allow_new:
            text = f"no new options: {mandate.note or 'orchestrator hold'}"
            for r in report.values():
                r["note"] = "held by manager"
            desk["options_note"] = text
            return
        budget = equity * mandate.budget_pct * mandate.scale
        used = inc.collateral() + sum(p["qty"] * ((quotes.get(sym) or {}).get("price") or p["avg"])
                                      for sym, p in s["positions"].items() if p["sleeve"] == "income")
        notes = []
        for a in self.agents:
            room_total = min(budget - used, tr.free_cash())
            try:
                out = a.run(quotes, t, equity, budget * a.share, room_total)
            except Exception as exc:
                print(f"[paper] options agent {a.name} failed:", repr(exc))
                out = {"note": "error; see log", "opened": 0}
            report[a.name]["note"] = out["note"]
            report[a.name]["open"] = sum(1 for o in inc.opts if o.get("strat") == a.name)
            if out["opened"] or out["note"] != "waiting for next scan window":
                notes.append(f"{a.label}: {out['note']}")
            used = inc.collateral() + sum(p["qty"] * ((quotes.get(sym) or {}).get("price") or p["avg"])
                                          for sym, p in s["positions"].items() if p["sleeve"] == "income")
        if notes:
            desk["options_note"] = " | ".join(notes)
