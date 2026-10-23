"""Paper-only options income sleeve: cash-secured puts and covered calls (a "wheel"). Never naked.

Safety invariants (enforced in code and tested):
- a put is only sold when free cash covers strike x 100 x contracts (cash-secured; the paper account never shorts stock);
- a call is only sold against income-sleeve shares that are not already covering another call;
- calls are sold at or above the share cost basis.
Real option quotes come from Robinhood's read-only market-data tools; nothing is ever ordered.
"""
from __future__ import annotations

import math
from datetime import date, datetime

MULT = 100
# Only strategies with a finite, known worst case may ever be opened. Anything else is refused.
ALLOWED_KINDS = {"put": "cash_secured_put", "call": "covered_call"}


class UnlimitedRiskRefused(RuntimeError):
    pass


def max_loss(o):
    """Worst-case loss in dollars for a short option position, or None if it is not provably finite."""
    if o["type"] == "put":  # stock to zero, collateral held in cash
        return max(0.0, (o["strike"] - o["credit"]) * MULT * o["qty"])
    if o["type"] == "call":  # shares already owned: loss is the shares falling to zero (finite)
        return None if o.get("kind") != "covered_call" else MULT * o["qty"] * o["strike"]
    return None


def _label(o):
    return f"{o['sym']} {o['exp']} {o['strike']:g}{'C' if o['type'] == 'call' else 'P'}"


class Income:
    def __init__(self, trader):
        self.tr = trader

    # ---- state helpers
    @property
    def opts(self):
        return self.tr.s.setdefault("options", [])

    def collateral(self):
        return sum(o["strike"] * MULT * o["qty"] for o in self.opts if o["type"] == "put")

    def liability(self):
        return sum((o.get("mark") or o["credit"]) * MULT * o["qty"] for o in self.opts)

    def covered_shares(self, sym):
        return sum(MULT * o["qty"] for o in self.opts if o["type"] == "call" and o["sym"] == sym)

    def uncovered_shares(self, sym):
        p = self.tr.s["positions"].get(sym)
        return (p["qty"] if p and p["sleeve"] == "income" else 0.0) - self.covered_shares(sym)

    def naked_violations(self):
        """Empty when every short option is fully covered or cash-secured and has a finite worst case."""
        bad = [f"{o['sym']} {o['type']} has no finite worst case" for o in self.opts if max_loss(o) is None]
        for sym in {o["sym"] for o in self.opts if o["type"] == "call"}:
            p = self.tr.s["positions"].get(sym)
            if not p or p["qty"] + 1e-6 < self.covered_shares(sym):
                bad.append(f"{sym} calls not covered by shares")
        if self.tr.s["cash"] + 1e-6 < self.collateral():
            bad.append("puts not cash-secured")
        return bad

    def _log(self, t, desc, o, fee, **extra):
        self.tr.s["trades"].append({"ts": t.isoformat(), "side": "option", "sym": o["sym"], "qty": o["qty"],
                                    "px": extra.pop("px", o["credit"]), "fee": fee, "sleeve": "income",
                                    "reason": extra.pop("reason", ""), "value": 0.0, "desc": desc, **extra})

    # ---- order simulation
    def sell_to_open(self, kind, sym, contract, quote, qty, t):
        if kind not in ALLOWED_KINDS or not isinstance(qty, int) or qty < 1:
            raise UnlimitedRiskRefused(f"refused {kind!r} x{qty}: only cash-secured puts and covered calls are allowed")
        s, c = self.tr.s, self.tr.cfg
        credit, fee = quote["bid"], c.opt_fee * qty
        if kind == "put" and self.tr.free_cash() < contract["strike"] * MULT * qty:
            return False
        if kind == "call" and self.uncovered_shares(sym) + 1e-6 < MULT * qty:
            return False
        if not credit or credit < 0.05:
            return False
        probe = {"type": kind, "strike": contract["strike"], "credit": credit, "qty": qty, "kind": ALLOWED_KINDS[kind]}
        if max_loss(probe) is None:
            raise UnlimitedRiskRefused("worst case is not provably finite")
        s["cash"] += credit * MULT * qty - fee
        s["fees_total"] += fee
        o = {"id": contract["id"], "sym": sym, "type": kind, "strike": contract["strike"], "exp": contract["exp"],
             "qty": qty, "credit": credit, "mark": quote.get("mark") or credit, "opened": t.isoformat(), "fee_open": fee,
             "kind": ALLOWED_KINDS[kind]}
        self.opts.append(o)
        self._log(t, f"SELL TO OPEN {_label(o)} x{qty} @ ${credit:.2f} (+${credit * MULT * qty:,.2f} premium, "
                  f"{'cash-secured' if kind == 'put' else 'covered'})", o, fee, reason=f"premium {credit / contract['strike']:.1%} of strike")
        return True

    def _finish(self, o, debit_per_share, fee, t, desc, reason):
        s = self.tr.s
        realized = (o["credit"] - debit_per_share) * MULT * o["qty"] - o["fee_open"] - fee
        s["cash"] -= debit_per_share * MULT * o["qty"] + fee
        s["fees_total"] += fee
        s["realized_total"] += realized
        self.opts.remove(o)
        self._log(t, desc, o, fee, px=debit_per_share, realized=realized, reason=reason)
        return realized

    def buy_to_close(self, o, ask, reason, t):
        fee = self.tr.cfg.opt_fee * o["qty"]
        r = self._finish(o, ask, fee, t, f"BUY TO CLOSE {_label(o)} x{o['qty']} @ ${ask:.2f}", reason)
        return r

    def settle(self, o, under_px, t):
        s = self.tr.s
        itm = under_px > o["strike"] + 0.005 if o["type"] == "call" else under_px < o["strike"] - 0.005
        shares = MULT * o["qty"]
        if not itm:
            self._finish(o, 0.0, 0.0, t, f"EXPIRED WORTHLESS {_label(o)} x{o['qty']} (kept ${o['credit'] * shares:,.2f})",
                         "out of the money at expiry")
            return
        if o["type"] == "put":
            self._finish(o, 0.0, 0.0, t, f"ASSIGNED {_label(o)}: bought {shares} sh @ ${o['strike']:.2f}", "put assigned")
            s["cash"] -= o["strike"] * shares
            s["positions"][o["sym"]] = {"qty": float(shares), "avg": o["strike"], "sleeve": "income", "opened": t.isoformat()}
        else:
            pos = s["positions"].get(o["sym"])
            self._finish(o, 0.0, 0.0, t, f"CALLED AWAY {_label(o)}: sold {shares} sh @ ${o['strike']:.2f}", "call assigned")
            if pos:
                from .paper_live import sell_fees
                gross = o["strike"] * shares
                fee = sell_fees(shares, gross)
                net = gross - fee - pos["avg"] * shares
                s["cash"] += gross - fee
                s["fees_total"] += fee
                s["realized_total"] += net
                pos["qty"] = round(pos["qty"] - shares, 6)
                if pos["qty"] <= 1e-6:
                    s["positions"].pop(o["sym"])
                s["trades"].append({"ts": t.isoformat(), "side": "sell", "sym": o["sym"], "qty": shares, "px": o["strike"],
                                    "fee": fee, "sleeve": "income", "reason": "shares called away", "value": gross,
                                    "realized": net, "closed": o["sym"] not in s["positions"], "avg": pos["avg"],
                                    "opened": pos["opened"]})

    # ---- cycle hooks
    def settle_expired(self, quotes, t):
        for o in list(self.opts):
            exp = date.fromisoformat(o["exp"])
            due = t.date() > exp or (t.date() == exp and (t.hour, t.minute) >= (16, 0))
            px = (quotes.get(o["sym"]) or {}).get("price")
            if due and px:
                self.settle(o, px, t)

    def manage(self, t):
        if not self.opts:
            return
        d, c = self.tr.data, self.tr.cfg
        try:
            qs = d.option_quotes([o["id"] for o in self.opts])
        except Exception as exc:
            print("[paper] option quotes failed:", repr(exc))
            return
        for o in list(self.opts):
            q = qs.get(o["id"])
            if not q or not q.get("mark"):
                continue
            o["mark"] = q["mark"]
            ask = q.get("ask") or q["mark"]
            if ask and ask <= o["credit"] * (1 - c.opt_take_profit):
                self.buy_to_close(o, ask, f"took {c.opt_take_profit:.0%} of max profit", t)
            elif o["type"] == "put" and ask >= o["credit"] * c.opt_stop_mult:
                self.buy_to_close(o, ask, f"stop: option worth {c.opt_stop_mult:g}x credit", t)

    def _liquid(self, q, c):
        if not q or not q.get("bid") or not q.get("ask") or q["bid"] < 0.05:
            return False
        mid = (q["bid"] + q["ask"]) / 2
        return (q["ask"] - q["bid"]) <= max(0.10, 0.15 * mid) and q["oi"] >= c.opt_min_oi

    def _pick(self, sym, kind, px, floor_strike, t):
        d, c = self.tr.data, self.tr.cfg
        exps = [e for e in d.option_expirations(sym)
                if c.opt_min_dte <= (date.fromisoformat(e) - t.date()).days <= c.opt_max_dte]
        if not exps:
            return None
        exp = exps[0]
        dte = (date.fromisoformat(exp) - t.date()).days
        contracts = d.option_contracts(sym, exp, kind)
        if kind == "put":
            cands = sorted((x for x in contracts if x["strike"] <= px * (1 - c.opt_otm)), key=lambda x: -x["strike"])[:5]
        else:
            lo = max(px * (1 + c.opt_otm), floor_strike)
            cands = sorted((x for x in contracts if x["strike"] >= lo), key=lambda x: x["strike"])[:5]
        if not cands:
            return None
        qs = d.option_quotes([x["id"] for x in cands])
        ok = [(x, qs[x["id"]]) for x in cands if self._liquid(qs.get(x["id"]), c)]
        if not ok:
            return None
        # best premium per day per dollar of strike
        return max(ok, key=lambda xq: xq[1]["bid"] / xq[0]["strike"] / max(dte, 1)) + (dte,)

    def scan(self, quotes, t, equity):
        c, tr = self.tr.cfg, self.tr
        last = tr.s.get("opt_scan")
        if last and (t - datetime.fromisoformat(last)).total_seconds() < c.opt_scan_min * 60:
            return
        if not ((10, 0) <= (t.hour, t.minute) < (15, 30)):
            return
        tr.s["opt_scan"] = t.isoformat()
        try:
            earn = {e.get("symbol") for e in tr.data.earnings(c.opt_max_dte)}
        except Exception:
            earn = set()
        taken = set(c.etfs) | set(c.day_symbols) | {c.hedge}
        for sym in c.opt_symbols:
            q = quotes.get(sym) or {}
            px = q.get("price")
            if sym in taken or not px or sym in earn:
                continue
            pos = tr.s["positions"].get(sym)
            held_calls = any(o["sym"] == sym for o in self.opts if o["type"] == "call")
            held_puts = any(o["sym"] == sym for o in self.opts if o["type"] == "put")
            used = self.collateral() + sum(p["qty"] * (quotes.get(s, {}).get("price") or p["avg"])
                                           for s, p in tr.s["positions"].items() if p["sleeve"] == "income")
            try:
                if pos and pos["sleeve"] == "income":
                    if held_calls or self.uncovered_shares(sym) < MULT:
                        continue
                    pick = self._pick(sym, "call", px, pos["avg"], t)
                    if pick:
                        self.sell_to_open("call", sym, pick[0], pick[1], int(self.uncovered_shares(sym) // MULT), t)
                elif not pos and not held_puts:
                    if (q.get("change_pct") or 0) < -0.03:
                        continue
                    pick = self._pick(sym, "put", px, 0, t)
                    if pick and used + pick[0]["strike"] * MULT <= c.opt_pct * equity:
                        self.sell_to_open("put", sym, pick[0], pick[1], 1, t)
            except Exception as exc:
                print(f"[paper] option scan {sym} failed:", repr(exc))

    def enforce(self, quotes, t):
        """Safety net every cycle: if any short option is somehow not covered/secured, close it at the ask."""
        if not self.naked_violations():
            return
        print("[paper] RISK GUARD: uncovered option detected, closing:", self.naked_violations())
        qs = {}
        try:
            qs = self.tr.data.option_quotes([o["id"] for o in self.opts])
        except Exception:
            pass
        for o in list(self.opts):
            if o["type"] == "call" and self.covered_shares(o["sym"]) > ((self.tr.s["positions"].get(o["sym"]) or {}).get("qty", 0)) + 1e-6 \
                    or max_loss(o) is None or (o["type"] == "put" and self.tr.s["cash"] + 1e-6 < self.collateral()):
                q = qs.get(o["id"]) or {}
                self.buy_to_close(o, q.get("ask") or q.get("mark") or o.get("mark") or o["credit"], "risk guard: not fully covered", t)

    def lines(self, quotes):
        out = []
        for o in sorted(self.opts, key=lambda o: (o["exp"], o["sym"])):
            kind = "covered call" if o["type"] == "call" else "cash-secured put"
            under = (quotes.get(o["sym"]) or {}).get("price")
            out.append(f"- {_label(o)} x{o['qty']} ({kind}, max loss ${max_loss(o):,.0f}): credit ${o['credit']:.2f}, mark ${(o.get('mark') or o['credit']):.2f}"
                       + (f", stock ${under:,.2f}" if under else ""))
        return out
