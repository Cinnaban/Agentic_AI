"""Paper-only long options: bought calls/puts and debit spreads. The loss is capped at the premium paid.

Safety invariants (enforced in code and tested):
- every position is opened for a net debit (cash out); a net credit is refused, so nothing here can be a short option;
- a debit spread pairs the bought option with a sold one further out of the money on the same expiry and type,
  and its net debit is below the width, so the worst case is the debit and the short leg can never lose more;
- the cash for the whole debit plus fees must be free when opening;
- positions are cash-settled at intrinsic value at expiry (no shares change hands) and are closed before the bell
  on expiry day to avoid pin risk.
Real option quotes come from Robinhood's read-only market-data tools; nothing is ever ordered.
"""
from __future__ import annotations

from datetime import date

from .paper_options import MULT, UnlimitedRiskRefused

LONG = {"call": "long_call", "put": "long_put"}
DEBIT_SPREAD = {"call": "call_debit_spread", "put": "put_debit_spread"}
KINDS = set(LONG.values()) | set(DEBIT_SPREAD.values())


def max_loss(o):
    """Worst case in dollars: the debit and the fees paid to open. None if the position is not a provable debit."""
    if o.get("kind") not in KINDS or not o.get("debit") or o["debit"] <= 0 or o["qty"] < 1:
        return None
    if o["kind"] in DEBIT_SPREAD.values():
        width = abs(o["short_strike"] - o["strike"])
        if not o.get("short_id") or o["debit"] >= width:
            return None
    return o["debit"] * MULT * o["qty"] + o.get("fee_open", 0.0)


def _label(o):
    cp = "C" if o["type"] == "call" else "P"
    if o.get("short_id"):
        return f"{o['sym']} {o['exp']} {o['strike']:g}/{o['short_strike']:g}{cp} debit spread"
    return f"{o['sym']} {o['exp']} {o['strike']:g}{cp}"


class LongOptions:
    def __init__(self, trader):
        self.tr = trader

    @property
    def opts(self):
        return self.tr.s.setdefault("long_opts", [])

    def value(self):
        """Mark-to-market value of open long positions (what closing them would roughly return)."""
        return sum((o.get("mark") if o.get("mark") is not None else o["debit"]) * MULT * o["qty"] for o in self.opts)

    def at_risk(self):
        return sum(o["debit"] * MULT * o["qty"] for o in self.opts)

    def violations(self):
        return [f"{o['sym']} {o.get('kind')} has no finite worst case" for o in self.opts if max_loss(o) is None]

    def _log(self, t, desc, o, fee, **extra):
        self.tr.s["trades"].append({"ts": t.isoformat(), "side": "option", "sym": o["sym"], "qty": o["qty"],
                                    "px": extra.pop("px", o["debit"]), "fee": fee, "sleeve": "income",
                                    "reason": extra.pop("reason", ""), "value": 0.0, "desc": desc,
                                    **({"strat": o["strat"]} if o.get("strat") else {}), **extra})

    def buy_to_open(self, sym, kind, long, long_q, qty, t, strat=None, short=None, short_q=None):
        """Buy a call or put, or a debit spread when `short` is given. Returns False if it cannot be afforded."""
        s, c = self.tr.s, self.tr.cfg
        if kind not in LONG or not isinstance(qty, int) or qty < 1:
            raise UnlimitedRiskRefused(f"refused {kind!r} x{qty}: only bought calls/puts and debit spreads are allowed")
        if not long_q.get("ask"):
            return False
        debit, legs = long_q["ask"], 1
        o = {"id": long["id"], "sym": sym, "type": kind, "strike": long["strike"], "exp": long["exp"], "qty": qty,
             "kind": LONG[kind], **({"strat": strat} if strat else {})}
        if short is not None:
            wrong_side = short["strike"] <= long["strike"] if kind == "call" else short["strike"] >= long["strike"]
            if wrong_side or short["exp"] != long["exp"]:
                raise UnlimitedRiskRefused("a debit spread needs a farther-out-of-the-money short leg on the same expiry")
            if not short_q or not short_q.get("bid"):
                return False
            debit, legs = round(long_q["ask"] - short_q["bid"], 2), 2
            o.update(kind=DEBIT_SPREAD[kind], short_id=short["id"], short_strike=short["strike"])
        if debit < 0.05:  # a free or credit "long" would really be a short position
            raise UnlimitedRiskRefused("net debit must be positive")
        fee = c.opt_fee * qty * legs
        o.update(debit=debit, mark=debit, opened=t.isoformat(), fee_open=fee)
        if max_loss(o) is None:
            raise UnlimitedRiskRefused("worst case is not provably finite")
        if self.tr.free_cash() < debit * MULT * qty + fee:
            return False
        s["cash"] -= debit * MULT * qty + fee
        s["fees_total"] += fee
        self.opts.append(o)
        self._log(t, f"BUY TO OPEN {_label(o)} x{qty} @ ${debit:.2f} (-${debit * MULT * qty:,.2f}, max loss "
                  f"${max_loss(o):,.0f})", o, fee, reason="directional setup")
        return True

    def _close_credit(self, o, qs):
        """Per-share proceeds from closing at the market: the bid, or long bid less short ask for a spread."""
        bid = (qs.get(o["id"]) or {}).get("bid") or 0.0
        if not o.get("short_id"):
            return bid
        return max(0.0, bid - ((qs.get(o["short_id"]) or {}).get("ask") or 0.0))

    def _finish(self, o, credit, fee, t, desc, reason):
        s = self.tr.s
        proceeds = credit * MULT * o["qty"] - fee
        realized = proceeds - o["debit"] * MULT * o["qty"] - o["fee_open"]
        s["cash"] += proceeds
        s["fees_total"] += fee
        s["realized_total"] += realized
        self.opts.remove(o)
        self._log(t, desc, o, fee, px=credit, realized=realized, reason=reason)
        return realized

    def sell_to_close(self, o, credit, reason, t):
        fee = self.tr.cfg.opt_fee * o["qty"] * (2 if o.get("short_id") else 1)
        return self._finish(o, credit, fee, t, f"SELL TO CLOSE {_label(o)} x{o['qty']} @ ${credit:.2f}", reason)

    def settle(self, o, under_px, t):
        if o["type"] == "call":
            value = max(0.0, under_px - o["strike"])
        else:
            value = max(0.0, o["strike"] - under_px)
        if o.get("short_id"):
            value = min(value, abs(o["short_strike"] - o["strike"]))
        word = "EXPIRED WORTHLESS" if value <= 0 else "SETTLED"
        self._finish(o, value, 0.0, t, f"{word} {_label(o)} x{o['qty']} at intrinsic ${value:.2f}",
                     "expired out of the money" if value <= 0 else "cash-settled at expiry")

    def settle_expired(self, quotes, t):
        for o in list(self.opts):
            exp = date.fromisoformat(o["exp"])
            due = t.date() > exp or (t.date() == exp and (t.hour, t.minute) >= (16, 0))
            px = (quotes.get(o["sym"]) or {}).get("price")
            if due and px:
                self.settle(o, px, t)

    def manage(self, t):
        """Marks and exits: stop on a premium loss, trail after a big gain, take profit, flat before expiry-day close."""
        if not self.opts:
            return
        c = self.tr.cfg
        ids = [i for o in self.opts for i in (o["id"], o.get("short_id")) if i]
        try:
            qs = self.tr.data.option_quotes(ids)
        except Exception as exc:
            print("[paper] long option quotes failed:", repr(exc))
            return
        for o in list(self.opts):
            q, sq = qs.get(o["id"]), qs.get(o.get("short_id"))
            if not q or not q.get("mark") or (o.get("short_id") and not (sq and sq.get("mark"))):
                continue
            mark = q["mark"] - (sq["mark"] if sq else 0.0)
            o["mark"] = mark
            o["peak"] = max(o.get("peak") or o["debit"], mark)
            bid = self._close_credit(o, qs)
            expiring = o["exp"] <= t.date().isoformat() and (t.hour, t.minute) >= (15, 45)
            if expiring:
                self.sell_to_close(o, bid, "closed before the expiry-day bell", t)
            elif mark >= o["debit"] * (1 + c.lo_take_profit):
                self.sell_to_close(o, bid, f"took profit: +{c.lo_take_profit:.0%} on the premium", t)
            elif o["peak"] >= o["debit"] * (1 + c.lo_trail_after) and mark <= o["peak"] * (1 - c.lo_trail):
                self.sell_to_close(o, bid, f"trailing stop: gave back {c.lo_trail:.0%} from the peak", t)
            elif mark <= o["debit"] * (1 - c.lo_stop):
                self.sell_to_close(o, bid, f"stop: premium down {c.lo_stop:.0%}", t)

    def lines(self, quotes):
        out = []
        for o in sorted(self.opts, key=lambda o: (o["exp"], o["sym"])):
            kind = ("debit spread" if o.get("short_id") else f"long {o['type']}")
            under = (quotes.get(o["sym"]) or {}).get("price")
            out.append(f"- {_label(o)} x{o['qty']} ({kind}, max loss ${max_loss(o):,.0f}): debit ${o['debit']:.2f}, "
                       f"mark ${(o.get('mark') if o.get('mark') is not None else o['debit']):.2f}"
                       + (f", stock ${under:,.2f}" if under else ""))
        return out
