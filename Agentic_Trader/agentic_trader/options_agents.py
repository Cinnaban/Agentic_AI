"""Options team (paper only): a sub-manager that reports to the orchestrator and runs one agent per options strategy.

Only cash-secured puts, covered calls and put credit spreads exist here, so no agent can ever open an unlimited-loss position; every
open goes through `Income.sell_to_open`, which refuses anything else. The `OptionsManager` owns what must be common
(the risk guard, marks and exits, the capital split, the report). Each agent owns one strategy:

- yield puts      higher-delta cash-secured puts ranked by delta-adjusted annualised yield
- defensive puts  low-delta, further-out-of-the-money cash-secured puts on the same universe
- put spreads     put credit spreads: a short put paired with a bought lower-strike put, so loss is capped
- covered calls   calls against shares assigned from puts, never below cost basis
- long options    bought calls/puts and debit spreads on a directional setup; the loss is capped at the premium paid
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime

from . import day_strategy as ds
from .paper_options import MULT, _coll

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
    brief = {}  # set by the options manager from the orchestrator's mandate

    def __init__(self, trader):
        self.tr = trader

    def open_puts(self):
        return [o for o in self.tr.income.opts if o["type"] == "put" and o.get("strat") == self.name]

    def collateral(self):
        return sum(_coll(o) for o in self.open_puts())

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

    def _weak(self, sym):
        b = self.brief or {}
        return b.get("avoid", {}).get(sym) or b.get("avoid_strat", {}).get(f"{self.name}|{sym}")

    def _strong(self, sym):
        b = self.brief or {}
        return bool(b.get("favored", {}).get(sym) or b.get("favored_strat", {}).get(f"{self.name}|{sym}"))

    def _min_cost(self, px):
        """Smallest cash a position in this symbol could need, used to skip names the budget cannot fund."""
        return px * MULT * (1 - max(self.tr.cfg.opt_otm, self.OTM_FLOOR))

    def _cost(self, best):
        return best[0]["strike"] * MULT

    def _open(self, sym, best, t):
        return self.tr.income.sell_to_open("put", sym, best[0], best[1], 1, t, strat=self.name)

    def _rank(self, sym):
        tr = self.tr
        if not tr.rank.w:
            return 0.0
        try:
            return tr.rank.score(tr.data.bars([sym], "day", 400, ttl=3600).get(sym, []))[0]
        except Exception:
            return 0.0

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

    def run(self, quotes, t, equity, budget, room_total, team_budget=0.0):
        """`budget` is this agent's slice in dollars; `room_total` is what the whole team can still commit."""
        tr, c, s, inc = self.tr, self.tr.cfg, self.tr.s, self.tr.income
        if self.throttled(t):
            return {"note": "waiting for next scan window", "opened": 0}
        stats = Counter()
        earn = _earnings(tr, c.opt_max_dte, t.date())
        taken = set(c.etfs) | set(c.day_symbols) | {c.hedge}
        # An agent may use its slice or up to half the team budget, so an idle agent's slice is not stranded.
        cap = max(budget, 0.5 * team_budget) if team_budget else budget
        room = min(cap - self.collateral(), room_total, tr.free_cash())
        market = max(min((quotes.get("SPY") or {}).get("change_pct") or 0, 0), -0.04)
        drop_limit = self.MAX_DROP + market  # only weakness beyond the market's own move counts as a falling knife
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
            elif self._weak(sym):
                stats["weak recent results (briefing)"] += 1
            elif self._min_cost(px) > room:
                stats["too large for budget"] += 1
            elif (q.get("change_pct") or 0) < drop_limit:
                stats[f"falling >{abs(self.MAX_DROP):.0%} beyond the market"] += 1
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
                    candidates.append((best[3] * (1 + 0.5 * tr.quant.verdict(sym, "options")[1]) * tilt
                                       * (1 + c.rank_weight * self._rank(sym)) * (1 + c.brief_weight * self._strong(sym)), sym, best))
                else:
                    stats["earnings or no liquid strike" if sym in earn else "no liquid strike"] += 1
        opened = 0
        for _, sym, best in sorted(candidates, key=lambda x: -x[0]):
            if total_puts + opened >= c.opt_max_positions or self._cost(best) > room:
                continue
            if self._open(sym, best, t):
                opened += 1
                room -= self._cost(best)
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


class PutSpreads(PutAgent):
    """Put credit spreads: sell a put 4-10% below the price and buy one a few strikes lower. The bought put caps the
    loss, so the position needs far less cash than a cash-secured put and can never become a naked short."""
    name, label, share = "put_spreads", "Put credit spreads", 0.5
    DELTA_RANGE = (0.10, 0.30)
    OTM_FLOOR = 0.03
    MAX_DROP = -0.02
    MIN_CREDIT_RATIO = 0.25  # net credit as a share of the spread width: caps risk at 3x the reward

    def _min_cost(self, px):
        return MULT

    def _cost(self, best):
        return (best[0]["strike"] - best[5]["strike"]) * MULT

    def _open(self, sym, best, t):
        return self.tr.income.sell_credit_spread(sym, best[0], best[1], best[5], best[6], 1, t, strat=self.name)

    def _best(self, sym, px, t, earn_date, room):
        d, c = self.tr.data, self.tr.cfg
        best = None
        otm = max(c.opt_otm, self.OTM_FLOOR)
        exps = [e for e in d.option_expirations(sym)
                if c.opt_min_dte <= (date.fromisoformat(e) - t.date()).days <= c.opt_max_dte][:2]
        want = max(1.0, round(px * 0.05))  # target width: about 5% of the price, at least $1
        for exp in exps:
            if earn_date and earn_date <= exp:
                continue
            dte = (date.fromisoformat(exp) - t.date()).days
            puts = sorted((x for x in d.option_contracts(sym, exp, "put") if x["strike"] <= px * (1 - otm)),
                          key=lambda x: -x["strike"])
            shorts = puts[:6]
            if not shorts:
                continue
            pairs = []
            for sh in shorts:
                lows = [x for x in puts if x["strike"] <= sh["strike"] - want + 1e-9 and sh["strike"] - x["strike"] <= want * 2]
                if lows and (sh["strike"] - lows[0]["strike"]) * MULT <= room:
                    pairs.append((sh, lows[0]))
            if not pairs:
                continue
            quotes = d.option_quotes(list({x["id"] for p in pairs for x in p}))
            for sh, lo in pairs:
                sq, lq = quotes.get(sh["id"]), quotes.get(lo["id"])
                if not self.tr.income._liquid(sq, c) or not lq or not lq.get("ask"):
                    continue
                delta = abs(sq.get("delta") or 0)
                if delta and not self.DELTA_RANGE[0] <= delta <= self.DELTA_RANGE[1]:
                    continue
                width, credit = sh["strike"] - lo["strike"], sq["bid"] - lq["ask"]
                if credit < max(c.opt_min_credit, self.MIN_CREDIT_RATIO * width):
                    continue
                score = credit / width / dte * 365 * (1 - delta)
                if best is None or score > best[3]:
                    best = (sh, sq, dte, score, sq.get("iv"), lo, lq)
        return best


class CoveredCalls(_Agent):
    name, label, share = "covered_calls", "Covered calls", 0.0

    def run(self, quotes, t, equity, budget, room_total, team_budget=0.0):
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


class LongOptionAgent(_Agent):
    """Directional short-dated options bought for a debit (long calls/puts, or a debit spread when a single leg costs
    more than the per-trade cap). Worst case is the premium paid, so it is defined-risk like the rest of the team.
    Entry needs the opening range broken with price on the right side of VWAP and the EMAs; calls also face the quant veto."""
    name, label, share = "long_options", "Long calls/puts", 0.0
    TARGET_DELTA = 0.40
    WINDOW = ((9, 45), (14, 30))
    SCAN_MIN = 5

    def _snapshots(self, syms, quotes, t):
        d = self.tr.data
        bars5 = d.bars(syms, "5minute", 6, ttl=60)
        daily = d.bars(syms, "day", 120, ttl=1800)
        snap = {}
        for sym in syms:
            try:
                snap[sym] = ds.analyze(bars5.get(sym, []), daily.get(sym, []), (quotes.get(sym) or {}).get("price"), t.date())
            except Exception as exc:
                print(f"[paper] long option analyze {sym} failed:", repr(exc))
                snap[sym] = None
        return snap

    @staticmethod
    def direction(m):
        """('call'|'put', strength) when price is breaking the opening range with trend and VWAP agreeing, else None."""
        if not m or not m.get("or_done"):
            return None
        a = m.get("atr5") or 0.0
        if not a:
            return None
        if m["price"] > m["vwap"] and m["ema9"] > m["ema21"] and m["price"] > m["or_high"] and (m.get("rsi") or 50) < 78:
            return "call", (m["price"] - m["or_high"]) / a
        if m["price"] < m["vwap"] and m["ema9"] < m["ema21"] and m["price"] < m["or_low"] and (m.get("rsi") or 50) > 22:
            return "put", (m["or_low"] - m["price"]) / a
        return None

    def _pick(self, sym, kind, px, t, per_trade):
        """(long, long_q, short, short_q, cost per contract) or (None, reason)."""
        d, c, inc = self.tr.data, self.tr.cfg, self.tr.income
        exps = [e for e in d.option_expirations(sym)
                if c.lo_min_dte <= (date.fromisoformat(e) - t.date()).days <= c.lo_max_dte]
        if not exps:
            return None, "no expiry in range"
        contracts = d.option_contracts(sym, exps[0], kind)
        near = sorted((x for x in contracts if abs(x["strike"] / px - 1) <= 0.03), key=lambda x: abs(x["strike"] - px))[:8]
        far_dir = 1 if kind == "call" else -1
        far = sorted((x for x in contracts if 0 < far_dir * (x["strike"] - px) <= px * 0.06), key=lambda x: abs(x["strike"] - px))[:10]
        if not near:
            return None, "no strike near the money"
        qs = d.option_quotes(list({x["id"] for x in near + far}))
        liquid = [(x, qs[x["id"]]) for x in near if inc._liquid(qs.get(x["id"]), c)]
        if not liquid:
            return None, "no liquid strike"

        def fit(xq):
            delta = abs(xq[1].get("delta") or 0)
            return abs(delta - self.TARGET_DELTA) if delta else abs(xq[0]["strike"] / px - 1)

        long, lq = min(liquid, key=fit)
        if lq["ask"] * MULT <= per_trade:
            return (long, lq, None, None, lq["ask"] * MULT), ""
        best = None
        for sh in far:
            sq = qs.get(sh["id"])
            if far_dir * (sh["strike"] - long["strike"]) <= 0 or not sq or not sq.get("bid") or sq.get("oi", 0) < c.opt_min_oi:
                continue
            debit, width = round(lq["ask"] - sq["bid"], 2), abs(sh["strike"] - long["strike"])
            if debit < 0.05 or debit >= width or debit * MULT > per_trade:
                continue
            ratio = debit / width
            if best is None or ratio < best[0]:
                best = (ratio, sh, sq, debit)
        if not best:
            return None, "premium above the per-trade cap"
        return (long, lq, best[1], best[2], best[3] * MULT), ""

    def run(self, quotes, t, equity, budget, room_total, team_budget=0.0):
        tr, c, s, lo = self.tr, self.tr.cfg, self.tr.s, self.tr.longopts
        hm = (t.hour, t.minute)
        if not c.lo_on:
            return {"note": "disabled", "opened": 0}
        if not (self.WINDOW[0] <= hm < self.WINDOW[1]):
            return {"note": "waiting for next scan window", "opened": 0}
        last = s.get("opt_scan_long_options")
        if last and (t - datetime.fromisoformat(last)).total_seconds() < self.SCAN_MIN * 60:
            return {"note": "waiting for next scan window", "opened": 0}
        s["opt_scan_long_options"] = t.isoformat()
        today = t.date().isoformat()
        entries = sum(1 for x in s["trades"] if x.get("strat") == self.name and x["ts"][:10] == today
                      and x.get("desc", "").startswith("BUY TO OPEN"))
        room = min(team_budget * c.lo_budget_pct - lo.at_risk(), room_total, tr.free_cash())
        per_trade = min(team_budget * c.lo_trade_pct, room)
        if len(lo.opts) >= c.lo_max_open or entries >= c.lo_max_entries or per_trade < 5:
            return {"note": f"at limits ({len(lo.opts)} open, {entries} entries today, ${max(room, 0):,.0f} premium room)",
                    "opened": 0}
        stats = Counter()
        syms = [x for x in c.lo_symbols if x in quotes]
        snap = self._snapshots(syms, quotes, t)
        earn = _earnings(tr, c.lo_max_dte, t.date())
        held = {o["sym"] for o in lo.opts}
        found = []
        tr.quant.ensure([x for x in syms if snap.get(x)], "options")
        for sym in syms:
            m = snap.get(sym)
            dirn = self.direction(m)
            weak = (self.brief or {}).get("avoid", {}).get(sym)
            if sym in held:
                stats["already held"] += 1
            elif not dirn:
                stats["no breakout setup"] += 1
            elif sym in earn:
                stats["earnings in the window"] += 1
            elif weak:
                stats["weak recent results (briefing)"] += 1
            elif dirn[0] == "call" and (tr.quant.verdict(sym, "options")[0] or tr.signals.bearish(sym)):
                stats["call vetoed (quant or news)"] += 1
            else:
                strong = (self.brief or {}).get("favored", {}).get(sym)
                found.append((dirn[1] * (1 + (c.brief_weight if strong else 0)), sym, dirn[0]))
        opened = 0
        for _, sym, kind in sorted(found, reverse=True):
            if len(lo.opts) >= c.lo_max_open or entries + opened >= c.lo_max_entries or per_trade < 5:
                break
            try:
                pick, why = self._pick(sym, kind, quotes[sym]["price"], t, per_trade)
            except Exception as exc:
                print(f"[paper] long option scan {sym} failed:", repr(exc))
                stats["data error"] += 1
                continue
            if not pick:
                stats[why] += 1
                continue
            long, lq, short, sq, cost = pick
            qty = max(1, min(10, int(per_trade // cost))) if cost <= per_trade else 0
            if qty and lo.buy_to_open(sym, kind, long, lq, qty, t, strat=self.name, short=short, short_q=sq):
                opened += 1
                room -= cost * qty
                per_trade = min(per_trade, room)
            else:
                stats["not enough free cash"] += 1
        parts = [f"{n} {why}" for why, n in stats.most_common()]
        return {"opened": opened, "note": f"scanned {len(syms)} names: opened {opened} long option(s)"
                + (f"; skipped {', '.join(parts[:4])}" if parts else "")}


class OptionsManager:
    """Sub-manager: takes the orchestrator's options mandate, splits it across its agents, and reports back."""

    def __init__(self, trader):
        self.tr = trader
        self.agents = [VRPPuts(trader), PutSpreads(trader), YieldPuts(trader), DefensivePuts(trader), CoveredCalls(trader),
                       LongOptionAgent(trader)]  # selective agent first

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
        tr.longopts.manage(t)
        desk = s.setdefault("desk", {})
        today = t.date().isoformat()
        report = {}
        for a in self.agents:
            prem, pl = self._stats(a.name, today)
            n_open = sum(1 for o in inc.opts + tr.longopts.opts if o.get("strat") == a.name)
            report[a.name] = {"label": a.label, "open": n_open, "premium_today": prem, "pl_today": pl, "note": ""}
        desk["options_agents"] = report
        if not mandate.allow_new:
            text = f"no new options: {mandate.note or 'orchestrator hold'}"
            for r in report.values():
                r["note"] = "held by manager"
            desk["options_note"] = text
            return
        budget = equity * mandate.budget_pct * mandate.scale
        used = inc.collateral() + tr.longopts.at_risk() + sum(p["qty"] * ((quotes.get(sym) or {}).get("price") or p["avg"])
                                      for sym, p in s["positions"].items() if p["sleeve"] == "income")
        notes = []
        for a in self.agents:
            a.brief = mandate.brief or {}
            room_total = min(budget - used, tr.free_cash())
            try:
                out = a.run(quotes, t, equity, budget * a.share, room_total, budget)
            except Exception as exc:
                print(f"[paper] options agent {a.name} failed:", repr(exc))
                out = {"note": "error; see log", "opened": 0}
            report[a.name]["note"] = out["note"]
            report[a.name]["open"] = sum(1 for o in inc.opts + tr.longopts.opts if o.get("strat") == a.name)
            if out["opened"] or out["note"] != "waiting for next scan window":
                notes.append(f"{a.label}: {out['note']}")
            used = inc.collateral() + tr.longopts.at_risk() + sum(p["qty"] * ((quotes.get(sym) or {}).get("price") or p["avg"])
                                          for sym, p in s["positions"].items() if p["sleeve"] == "income")
        if notes:
            desk["options_note"] = " | ".join(notes)
