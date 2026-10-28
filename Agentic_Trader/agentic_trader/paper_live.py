"""Internal live paper trading on real Robinhood market data (read-only data path only).

- Starts with PAPER_START_CASH ($5,000). Orders are simulated here; nothing is ever sent to Robinhood.
- State lives in the shared_storage cache (namespace `paper_trader`) with a JSON mirror in state/.
- Sleeves: ETF core (trend-filtered), day trader (live-quote quant signal, inverse-vol sizing, flat by close),
  a cash-secured-put/covered-call income sleeve (paper_options.py), and a volatility hedge (VIX + SPY realized vol -> long-only inverse ETF + smaller day-trade size).
- Posts a summary every 30 minutes to the realtime Discord channel and a daily summary to the updates channel.
- Fees: zero commission; SEC fee + FINRA TAF on sells (min $0.01); buys fill at the ask and sells at the bid.
"""
from __future__ import annotations

import json
import math
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np

from .config import STATE_DIR, Settings, load_env_files
from .desk import AGENTS, LABELS, Desk
from .paper_options import Income

ET = ZoneInfo("America/New_York")
NAMESPACE, STORE_KEY = "paper_trader", "account_v1"
OPEN, CLOSE = (9, 30), (16, 0)
NO_ENTRY_AFTER, FLATTEN_AT = (15, 30), (15, 50)
SEC_FEE_RATE, TAF_PER_SHARE, TAF_MAX = 0.0000206, 0.000166, 8.30


def _csv(name, default):
    return [x.strip().upper() for x in os.getenv(name, default).split(",") if x.strip()]


class Cfg:
    def __init__(self):
        load_env_files()
        self.start_cash = float(os.getenv("PAPER_START_CASH", "5000"))
        self.core_pct = float(os.getenv("PAPER_CORE_PCT", "0.60"))
        # day-trading sleeve is held within 20-40% of equity
        self.day_pct = min(0.40, max(0.20, float(os.getenv("PAPER_DAY_PCT", "0.30"))))
        self.etfs = _csv("PAPER_ETFS", "VOO,QQQ,SCHD,VXUS")
        self.day_symbols = _csv("PAPER_DAY_SYMBOLS", "NVDA,AAPL,AMD,TSLA,MSFT,META")
        self.hedge = os.getenv("PAPER_HEDGE_SYMBOL", "SH").upper()
        self.cycle = int(os.getenv("PAPER_CYCLE_SECONDS", "300"))
        self.entry = float(os.getenv("PAPER_ENTRY_SIGNAL", "0.20"))
        self.stop = float(os.getenv("PAPER_STOP_PCT", "0.015"))
        # volatility-scaled stop losses (fraction of cost), clamped to a sensible range per agent
        self.day_stop_mult = float(os.getenv("PAPER_DAY_STOP_VOL_MULT", "1.5"))
        self.day_stop_min = float(os.getenv("PAPER_DAY_STOP_MIN", "0.015"))
        self.day_stop_max = float(os.getenv("PAPER_DAY_STOP_MAX", "0.035"))
        self.growth_stop_mult = float(os.getenv("PAPER_GROWTH_STOP_VOL_MULT", "3.0"))
        self.growth_stop_min = float(os.getenv("PAPER_GROWTH_STOP_MIN", "0.05"))
        self.growth_stop_max = float(os.getenv("PAPER_GROWTH_STOP_MAX", "0.09"))
        self.target = float(os.getenv("PAPER_TARGET_PCT", "0.02"))
        self.max_day_positions = int(os.getenv("PAPER_MAX_DAY_POSITIONS", "3"))
        self.min_trade = float(os.getenv("PAPER_MIN_TRADE_USD", "5"))
        # 2026 rule: margin accounts with >= $2,000 equity have no day-trade limit; otherwise the
        # legacy limit (max 3 day trades per 5 business days under $25,000) applies.
        self.account_type = os.getenv("PAPER_ACCOUNT_TYPE", "margin").lower()
        self.pdt_free_min = float(os.getenv("PAPER_PDT_FREE_MIN_EQUITY", "2000"))
        self.pdt_max = int(os.getenv("PAPER_PDT_MAX_DAY_TRADES", "3"))
        self.pdt_legacy_equity = float(os.getenv("PAPER_PDT_LEGACY_EQUITY", "25000"))
        # targets are goals to measure against, not instructions to add risk
        self.daily_min = float(os.getenv("PAPER_DAILY_TARGET_MIN", "0.02"))
        self.daily_max = float(os.getenv("PAPER_DAILY_TARGET_MAX", "0.05"))
        self.week_min = float(os.getenv("PAPER_WEEKLY_TARGET_MIN", "0.08"))
        self.week_max = float(os.getenv("PAPER_WEEKLY_TARGET_MAX", "0.12"))
        # options income sleeve: cash-secured puts + covered calls only, never naked
        self.opt_enabled = os.getenv("PAPER_OPTIONS", "1") not in ("0", "false", "off")
        self.opt_symbols = _csv("PAPER_OPTION_SYMBOLS", "F,SOFI,RIVN,SNAP,NIO,AAL,HBAN,NU,VALE,BB,RIG,LCID,T,KVUE,CMCSA,PFE")
        self.opt_pct = float(os.getenv("PAPER_OPTION_PCT", "0.35"))
        self.opt_min_dte = int(os.getenv("PAPER_OPTION_MIN_DTE", "5"))
        self.opt_max_dte = int(os.getenv("PAPER_OPTION_MAX_DTE", "14"))
        self.opt_otm = float(os.getenv("PAPER_OPTION_OTM", "0.04"))
        self.opt_min_oi = int(os.getenv("PAPER_OPTION_MIN_OI", "25"))
        self.opt_take_profit = float(os.getenv("PAPER_OPTION_TAKE_PROFIT", "0.75"))
        self.opt_stop_mult = float(os.getenv("PAPER_OPTION_STOP_MULT", "3"))
        self.opt_fee = float(os.getenv("PAPER_OPTION_FEE_PER_CONTRACT", "0.04"))
        self.opt_scan_min = int(os.getenv("PAPER_OPTION_SCAN_MIN", "30"))
        self.cooldown_min = int(os.getenv("PAPER_COOLDOWN_MIN", "30"))
        self.opt_max_positions = int(os.getenv("PAPER_OPTION_MAX_POSITIONS", "3"))
        self.opt_weekly_premium_goal = float(os.getenv("PAPER_OPTION_WEEKLY_PREMIUM_GOAL", "0.01"))
        # growth agent: share of equity for core ETFs + hedge, optional "VOO:0.35,QQQ:0.25" weights, rebalance band
        self.growth_pct = float(os.getenv("PAPER_GROWTH_PCT", str(self.core_pct)))
        self.growth_weights = {k.strip().upper(): float(v) for k, v in
                               (item.split(":") for item in os.getenv("PAPER_GROWTH_WEIGHTS", "").split(",") if ":" in item)}
        self.rebalance_band = float(os.getenv("PAPER_REBALANCE_BAND", "0.25"))
        # growth + day agents: one trade per day each, taken early in the open (options agent is unrestricted)
        self.single_min_score = float(os.getenv("PAPER_SINGLE_MIN_SCORE", "0.15"))
        self.growth_min_score = float(os.getenv("PAPER_GROWTH_MIN_SCORE", "0.0"))
        self.single_min_coverage = float(os.getenv("PAPER_SINGLE_MIN_COVERAGE", "0.5"))
        self.day_intraday_exits = os.getenv("PAPER_DAY_INTRADAY_EXITS", "0") in ("1", "true", "on")


def now_et() -> datetime:
    return datetime.now(ET)


def _money(x, sign=False):
    return f"{'+' if sign and x >= 0 else ''}{'-' if x < 0 else ''}${abs(x):,.2f}"


def _pct(x):
    return f"{x:+.2%}"


# ---------------------------------------------------------------- storage
class Store:
    """shared_storage cache (primary) + JSON mirror (fallback)."""

    def __init__(self, mirror=None, storage=True):
        self.mirror = mirror or (STATE_DIR / "paper_live.json")
        self.storage = None
        if storage:
            try:
                import sys
                from pathlib import Path
                root = str(Path(__file__).resolve().parents[2])
                if root not in sys.path:
                    sys.path.append(root)
                from shared_storage.storage_manager import StorageManager
                self.storage = StorageManager()
            except Exception:
                self.storage = None

    def load(self):
        if self.storage:
            try:
                v = self.storage.get_cached_data(NAMESPACE, STORE_KEY)
                if v:
                    return v
            except Exception:
                pass
        if self.mirror.exists():
            try:
                return json.loads(self.mirror.read_text())
            except Exception:
                return None
        return None

    def save(self, state):
        self.mirror.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.mirror.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, default=str))
        os.replace(tmp, self.mirror)
        if self.storage:
            try:
                self.storage.set_cached_data(NAMESPACE, STORE_KEY, state, 400 * 86400)
            except Exception as exc:
                print("[paper] shared_storage save failed:", repr(exc))


def new_state(cfg, ts):
    return {"version": 1, "created": ts.isoformat(), "start_cash": cfg.start_cash, "cash": cfg.start_cash,
            "positions": {}, "trades": [], "fees_total": 0.0, "realized_total": 0.0, "equity_log": [],
            "options": [], "week": {"id": None, "open_equity": cfg.start_cash},
            "day": {"date": None, "open_equity": cfg.start_cash, "spy_open": None, "eod_posted": False},
            "last_summary": {"ts": ts.isoformat(), "equity": cfg.start_cash}, "cooldown": {}, "regime": {}}


# ---------------------------------------------------------------- math
def sell_fees(qty, value):
    raw = value * SEC_FEE_RATE + min(TAF_MAX, qty * TAF_PER_SHARE)
    return max(0.01, math.ceil(raw * 100 - 1e-9) / 100)


def realized_vol(closes, n):
    c = np.asarray(closes[-(n + 1):], dtype=float)
    if len(c) < n // 2:
        return None
    return float(np.std(np.diff(np.log(c))) * math.sqrt(252))


def classify_regime(vix, vol20, spy_below_ma50):
    """Volatility level -> hedge target (share of equity in the inverse ETF) and day-trade size scale."""
    level = max(vix or 0.0, (vol20 or 0.0) * 100)
    if level < 16:
        name, hedge, scale = "calm", 0.0, 1.0
    elif level < 22:
        name, hedge, scale = "normal", 0.05, 1.0
    elif level < 30:
        name, hedge, scale = "elevated", 0.10, 0.6
    else:
        name, hedge, scale = "stressed", 0.20, 0.3
    if spy_below_ma50:
        hedge = min(0.25, hedge + 0.05)
    return {"name": name, "level": level, "vix": vix, "spy_vol20": vol20, "hedge_target": hedge, "day_scale": scale,
            "spy_below_ma50": bool(spy_below_ma50)}


# ---------------------------------------------------------------- trader
class PaperTrader:
    def __init__(self, data, notifier, store, cfg=None, clock=now_et, analyze=None):
        self.data, self.n, self.store, self.cfg, self.clock = data, notifier, store, cfg or Cfg(), clock
        self.analyze = analyze or self._analyze
        self.s = store.load()
        if self.s and abs(self.s.get("start_cash", 0) - self.cfg.start_cash) > 1e-9:
            self._archive(self.s)
            self.s = None
        self.s = self.s or new_state(self.cfg, clock())
        self.pdt_blocked = 0
        self.s.setdefault("options", [])
        self.income = Income(self)
        self.desk = Desk(self)
        self.plan = None

    # ---- helpers
    def _archive(self, old):
        path = STATE_DIR / f"paper_live_archive_{self.clock().strftime('%Y%m%d_%H%M%S')}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(old, default=str))
        print("[paper] start cash changed; archived previous account to", path)

    def day_trades_5d(self, t):
        """Day trades (sold on the day opened) in the last 5 business days."""
        days, d = set(), t.date()
        while len(days) < 5:
            if d.weekday() < 5:
                days.add(d.isoformat())
            d -= timedelta(days=1)
        return sum(1 for x in self.s["trades"] if x["side"] == "sell" and x.get("opened")
                   and x["ts"][:10] in days and x["opened"][:10] == x["ts"][:10])

    def pdt_limited(self):
        c = self.cfg
        eq = self.s["equity_log"][-1][1] if self.s["equity_log"] else self.s["cash"]
        if c.account_type == "margin" and eq >= c.pdt_free_min:
            return False
        return eq < c.pdt_legacy_equity

    def day_trade_blocked(self, opened_iso, t):
        return (opened_iso[:10] == t.isoformat()[:10] and self.pdt_limited()
                and self.day_trades_5d(t) >= self.cfg.pdt_max)

    def _analyze(self, symbols):
        from . import quant_live
        return quant_live.analyze(symbols, data=self.data)

    def universe(self):
        c = self.cfg
        return sorted(set(c.etfs) | set(c.day_symbols) | {c.hedge, "SPY"} | set(self.s["positions"])
                      | (set(c.opt_symbols) if c.opt_enabled else set()))

    def equity(self, quotes):
        return (self.s["cash"] + sum(p["qty"] * (quotes.get(sym, {}).get("price") or p["avg"])
                                     for sym, p in self.s["positions"].items()) - self.income.liability())

    def free_cash(self):
        return self.s["cash"] - self.income.collateral()

    @staticmethod
    def fill_px(q, side):
        px = q.get("price") or 0.0
        edge = (q.get("ask") if side == "buy" else q.get("bid")) or 0.0
        return edge if edge and px and abs(edge / px - 1) < 0.02 else px

    def phase(self, t, quotes):
        """open | close | idle. Staleness of SPY's last trade handles holidays and early closes."""
        if t.weekday() >= 5:
            return "idle"
        hm = (t.hour, t.minute)
        spy = quotes.get("SPY", {})
        as_of = spy.get("as_of")
        fresh = bool(as_of) and as_of.astimezone(ET).date() == t.date() and spy.get("session") == "regular" \
            and (t - as_of.astimezone(ET)).total_seconds() < 20 * 60
        if OPEN <= hm < CLOSE and fresh:
            return "open"
        if CLOSE <= hm < (16, 40) and as_of and as_of.astimezone(ET).date() == t.date():
            return "close"
        return "idle"

    # ---- order simulation
    def stop_for(self, sleeve, vol_ann):
        """Stop-loss distance from cost: a multiple of the stock's daily volatility, clamped per agent."""
        c = self.cfg
        daily = (vol_ann or 0.3) / math.sqrt(252)
        mult, lo, hi = ((c.day_stop_mult, c.day_stop_min, c.day_stop_max) if sleeve == "day"
                        else (c.growth_stop_mult, c.growth_stop_min, c.growth_stop_max))
        return min(hi, max(lo, mult * daily))

    def protect(self, quotes, t):
        """Stop losses for the day and growth agents. Protective exits are not entries, so they sit outside the
        one-trade-per-day entry limit. Hedge and options-income shares are not stopped here."""
        for sym, p in list(self.s["positions"].items()):
            q = quotes.get(sym) or {}
            if p["sleeve"] in ("day", "core") and not p.get("stop_pct"):
                p["stop_pct"] = round(self.stop_for(p["sleeve"], None), 4)  # positions opened before stops existed
            stop = p.get("stop_pct")
            if p["sleeve"] not in ("day", "core") or not stop or not q.get("price"):
                continue
            ret = q["price"] / p["avg"] - 1
            if ret <= -stop:
                self.sell(sym, p["qty"], f"stop loss {ret:+.1%} (limit -{stop:.1%})", q, t)

    def buy(self, sym, usd, sleeve, reason, q, t, vol_ann=None):
        px = self.fill_px(q, "buy")
        usd = min(usd, self.free_cash())
        if not px or usd < self.cfg.min_trade:
            return False
        qty = round(usd / px, 6)
        cost = qty * px
        pos = self.s["positions"].setdefault(sym, {"qty": 0.0, "avg": 0.0, "sleeve": sleeve, "opened": t.isoformat()})
        pos["avg"] = (pos["avg"] * pos["qty"] + cost) / (pos["qty"] + qty)
        pos["qty"] = round(pos["qty"] + qty, 6)
        if sleeve in ("day", "core"):
            pos["stop_pct"] = round(self.stop_for(sleeve, vol_ann), 4)
        self.s["cash"] -= cost
        self.s["trades"].append({"ts": t.isoformat(), "side": "buy", "sym": sym, "qty": qty, "px": px, "fee": 0.0,
                                 "sleeve": sleeve, "reason": reason, "value": cost})
        return True

    def sell(self, sym, qty, reason, q, t):
        pos = self.s["positions"].get(sym)
        if not pos:
            return False
        if self.day_trade_blocked(pos["opened"], t):
            self.pdt_blocked += 1
            return False
        qty = min(qty, pos["qty"] - self.income.covered_shares(sym))
        px = self.fill_px(q, "sell")
        if not px or qty <= 0:
            return False
        gross = qty * px
        fee = sell_fees(qty, gross)
        net = gross - fee - pos["avg"] * qty
        self.s["cash"] += gross - fee
        self.s["fees_total"] += fee
        self.s["realized_total"] += net
        pos["qty"] = round(pos["qty"] - qty, 6)
        full = pos["qty"] <= 1e-6
        if full:
            self.s["positions"].pop(sym)
            self.s["cooldown"][sym] = t.isoformat()
        self.s["trades"].append({"ts": t.isoformat(), "side": "sell", "sym": sym, "qty": qty, "px": px, "fee": fee,
                                 "sleeve": pos["sleeve"], "reason": reason, "value": gross, "realized": net,
                                 "closed": full, "avg": pos["avg"], "opened": pos["opened"]})
        return True

    # ---- strategy
    def volatility(self):
        bars = self.data.bars(["SPY"], "day", 120, ttl=1800).get("SPY", [])
        closes = [b["close"] for b in bars if b.get("close")]
        vol20 = realized_vol(closes, 20)
        below = len(closes) >= 50 and closes[-1] < float(np.mean(closes[-50:]))
        reg = classify_regime(self.data.vix(), vol20, below)
        self.s["regime"] = reg
        return reg

    def hedge_plan(self, quotes, equity, reg):
        """The hedge adjustment the regime calls for, or None: (side, sym, usd_or_qty, reason, urgent)."""
        sym = self.cfg.hedge
        q = quotes.get(sym)
        if not q or not q.get("price"):
            return None
        held = self.s["positions"].get(sym)
        cur = (held["qty"] * q["price"]) if held else 0.0
        want = equity * reg["hedge_target"]
        band = max(self.cfg.min_trade, equity * 0.025)
        why = f"{reg['name']} volatility (VIX {reg['vix'] or 0:.1f}, SPY 20d vol {(reg['spy_vol20'] or 0):.0%})"
        if want - cur > band:
            return ("buy", sym, want - cur, f"hedge up: {why}", reg["name"] in ("elevated", "stressed"))
        if cur - want > band and held:
            qty = min(held["qty"], (cur - want) / q["price"]) if want > 0 else held["qty"]
            return ("sell", sym, qty, f"hedge down: {why}", False)
        return None

    def single_state(self):
        return self.s["day"].setdefault("single", {})

    def day_sleeve(self, quotes, t, equity, reg, phase_hm, mandate=None):
        """One entry per day, early in the open, held until the end-of-day flatten (no re-entry)."""
        from . import single_trade as st
        c = self.cfg
        day_pct = mandate.budget_pct if mandate else c.day_pct
        scale = (mandate.scale if mandate else 1.0)
        one = self.single_state()
        flatten = phase_hm >= FLATTEN_AT
        for sym in [s for s, p in self.s["positions"].items() if p["sleeve"] == "day"]:
            p, q = self.s["positions"][sym], quotes.get(sym, {})
            px = q.get("price")
            if not px:
                continue
            ret = px / p["avg"] - 1
            reason = ("end-of-day close of the day's single trade" if flatten else
                      f"target {ret:+.1%}" if c.day_intraday_exits and ret >= c.target else None)
            if reason:
                self.sell(sym, p["qty"], reason, q, t)
        if "day" in one or flatten:
            return
        if phase_hm >= st.ENTRY_END:
            one["day"] = {"sym": None, "note": "no qualifying setup in the entry window; no trade today"}
            return
        if mandate and not mandate.allow_new:
            return
        if self.pdt_limited() and self.day_trades_5d(t) >= c.pdt_max:
            one["day"] = {"sym": None, "note": "day-trade limit reached; no trade today"}
            return
        try:
            quants = self.analyze(c.day_symbols)
        except Exception as exc:
            print("[paper] analyze failed:", repr(exc))
            quants = {}
        ev = st.evaluate(c.day_symbols, self.data, quotes, quants)
        ranked = sorted(((e["score"], s) for s, e in ev.items()
                         if e["coverage"] >= c.single_min_coverage and (e["rsi"] or 50) < 75), reverse=True)
        self.s.setdefault("desk", {})["day_ranking"] = [(s, round(sc, 3)) for sc, s in ranked[:6]]
        if not ranked or ranked[0][0] < c.single_min_score:
            return  # keep looking until the window closes
        score, sym = ranked[0]
        q, e = quotes[sym], ev[sym]
        vol = e["vol"] or 0.3
        size = min(self.free_cash(), equity * day_pct * scale * min(1.0, 0.35 / max(vol, 0.05)))
        if self.buy(sym, size, "day", f"single daily trade: {st.why(e)}, RSI {e['rsi'] or 0:.0f}, vol {vol:.0%}, "
                                           f"stop -{self.stop_for('day', vol):.1%}", q, t, vol_ann=vol):
            one["day"] = {"sym": sym, "note": st.why(e)}

    # ---- main cycle
    def _sentiment(self, symbols):
        """Analyst buy-minus-sell share per symbol in [-1, 1]; missing data is simply omitted."""
        try:
            ratings = self.data.ratings(list(symbols))
        except Exception as exc:
            print("[paper] sentiment unavailable:", repr(exc))
            return {}
        out = {}
        for sym, r in (ratings or {}).items():
            b, h, s = ((r or {}).get(k) or 0 for k in ("num_buy_ratings", "num_hold_ratings", "num_sell_ratings"))
            if b + h + s:
                out[sym] = (b - s) / (b + h + s)
        return out

    @staticmethod
    def day_rank(m, sentiment=None):
        """Momentum/mean-reversion score, tilted by the walk-forward regression's out-of-sample IC
        (trust the model only as far as it has predicted) and by analyst sentiment."""
        score = m.get("signal_score") or -9
        ic = (m.get("scorecard") or {}).get("ic")
        if ic is not None:
            score += 0.10 * max(-1.0, min(1.0, ic / 0.2))
        if sentiment is not None:
            score += 0.10 * sentiment
        return score

    # ---- main cycle
    def step(self):
        t = self.clock()
        quotes = self.data.quotes(self.universe())
        phase = self.phase(t, quotes)
        if phase == "idle":
            return "idle"
        day = self.s["day"]
        if day["date"] != t.date().isoformat():
            last = self.s["equity_log"][-1][1] if self.s["equity_log"] else self.s["start_cash"]
            spy = quotes.get("SPY", {})
            self.s["day"] = day = {"date": t.date().isoformat(), "open_equity": last,
                                   "spy_open": spy.get("prev_close"), "eod_posted": False}
            self.s["last_summary"] = {"ts": t.isoformat(), "equity": last}
        wid = "%d-W%02d" % t.isocalendar()[:2]
        if self.s.get("week", {}).get("id") != wid:
            monday = (t - timedelta(days=t.weekday())).date().isoformat()
            prior = [e for ts, e in self.s["equity_log"] if ts[:10] < monday]
            self.s["week"] = {"id": wid, "open_equity": prior[-1] if prior else self.s["start_cash"]}
        hm = (t.hour, t.minute)
        if self.cfg.opt_enabled or self.s["options"]:
            try:
                self.income.settle_expired(quotes, t)
            except Exception as exc:
                print("[paper] option settle failed:", repr(exc))
        if phase == "open":
            try:
                self.protect(quotes, t)
            except Exception as exc:
                print("[paper] stop-loss check failed:", repr(exc))
        if phase == "open" and hm >= (9, 35):
            equity = self.equity(quotes)
            reg = self.volatility()
            self.plan = self.desk.orchestrator.plan(quotes, t, equity, reg)
            m = self.plan.mandates
            steps = []
            if self.cfg.opt_enabled:
                steps.append(("options", lambda: self.desk.options.run(quotes, t, equity, m["options"])))
            steps += [("day", lambda: self.desk.day.run(quotes, t, equity, m["day"], reg, hm)),
                      ("growth", lambda: self.desk.growth.run(quotes, t, equity, m["growth"], reg, hm))]
            for name, fn in steps:
                try:
                    fn()
                except Exception as exc:
                    print(f"[paper] {name} agent failed:", repr(exc))
        equity = self.equity(quotes)
        self.s["equity_log"].append([t.isoformat(), equity])
        self.s["equity_log"] = self.s["equity_log"][-4000:]
        if phase == "open":
            self.maybe_post_half_hour(t, quotes, equity)
        elif phase == "close" and not day["eod_posted"]:
            self.n.post("updates", self.summary(t, quotes, equity, daily=True), **self._session_chart_kwargs(t, equity))
            day["eod_posted"] = True
        self.store.save(self.s)
        return phase

    def _session_chart_kwargs(self, t, equity):
        """Best-effort half-hour chart of the portfolio vs SPY/DIA; the summary posts without it on any failure."""
        try:
            from . import session_chart
            syms = list(session_chart.BENCHMARKS.values())
            bars = self.data.bars(syms, "30minute", 2)
            prev = {s: (q or {}).get("prev_close") for s, q in self.data.quotes(syms).items()}
            path = session_chart.build_chart(self.s["equity_log"], self.s["day"]["open_equity"], bars, prev, t.date())
            return {"image_path": path} if path else {}
        except Exception as exc:
            print("[paper] session chart failed:", repr(exc))
            return {}

    def maybe_post_half_hour(self, t, quotes, equity):
        slot = t.replace(minute=0 if t.minute < 30 else 30, second=0, microsecond=0)
        if (t.hour, t.minute) >= (10, 0) and datetime.fromisoformat(self.s["last_summary"]["ts"]) < slot:
            self.n.post("realtime", self.summary(t, quotes, equity, daily=False))
            self.s["last_summary"] = {"ts": t.isoformat(), "equity": equity}

    # ---- summaries
    def _holdings(self, quotes, equity):
        rows = []
        for sym, p in sorted(self.s["positions"].items()):
            px = (quotes.get(sym) or {}).get("price") or p["avg"]
            val = p["qty"] * px
            rows.append(f"- {sym} ({p['sleeve']}): {p['qty']:g} sh, {_money(val)}, {(px / p['avg'] - 1):+.1%} vs cost, "
                        f"{val / equity:.0%} of portfolio")
        return rows or ["- none (all cash)"]

    def trending(self, equity, t):
        log = [(datetime.fromisoformat(a), b) for a, b in self.s["equity_log"] if a[:10] == t.date().isoformat()]
        recent = [e for _, e in log[-12:]]
        if len(recent) < 3:
            return "not enough data yet"
        slope = float(np.polyfit(range(len(recent)), recent, 1)[0]) * len(recent) / recent[0]
        word = "trending up" if slope > 0.0015 else "trending down" if slope < -0.0015 else "flat / range-bound"
        return f"{word} ({slope:+.2%} over the last ~{len(recent) * self.cfg.cycle // 60} min)"

    @staticmethod
    def goal_line(name, ret, lo, hi):
        state = "below target" if ret < lo else "on target" if ret <= hi else "above target"
        return f"{name}: {ret:+.2%} vs goal {lo:.0%}-{hi:.0%} ({state})"

    def desk_lines(self, quotes, equity, t):
        desk, cfg = self.s.get("desk") or {}, self.cfg
        if not desk.get("mandates"):
            return []
        rows = self.desk.orchestrator.attribution(quotes, t)
        week_open = self.s["week"]["open_equity"]
        premium_wk = sum(float(x["px"]) * 100 * x["qty"] for x in self.s["trades"]
                         if x["side"] == "option" and x["desc"].startswith("SELL TO OPEN")
                         and x["ts"][:10] >= (t - timedelta(days=t.weekday())).date().isoformat())
        L = ["", f"Desk (orchestrator, stance {desk['stance']}): day {desk['day_ret']:+.2%} / week {desk['week_ret']:+.2%}"]
        L += [f"- Orchestrator: {n}" for n in desk.get("notes", [])]
        for a in AGENTS:
            m, r = desk["mandates"][a], rows[a]
            line = (f"- {LABELS[a]}: budget {m['budget_pct'] * m['scale']:.0%}, deployed {_money(r['value'])} "
                    f"({r['value'] / equity:.0%}), realized today {_money(r['today'], True)} / week {_money(r['week'], True)}, "
                    f"open {_money(r['open'], True)}")
            if a == "options":
                line += (f", premium this week {_money(premium_wk)} vs goal "
                         f"{_money(cfg.opt_weekly_premium_goal * week_open)}")
            if not m["allow_new"]:
                line += " [holding]"
            L.append(line)
        one = self.s["day"].get("single", {})
        for key, label in (("growth", "Growth agent"), ("day", "Day agent")):
            r = one.get(key)
            L.append(f"- {label} daily trade (1 per day, early open): "
                     + (f"{r['note']}" if r else "not yet taken (waiting for the entry window to qualify)"))
        L.append("- Options agent: no daily limit")
        return L

    def summary(self, t, quotes, equity, daily):
        s, cfg = self.s, self.cfg
        since = datetime.fromisoformat(s["last_summary"]["ts"])
        day_start = t.replace(hour=0, minute=0, second=0, microsecond=0)
        trades = [x for x in s["trades"] if datetime.fromisoformat(x["ts"]) > (day_start if daily else since)]
        base = s["day"]["open_equity"] if daily else s["last_summary"]["equity"]
        pl, day_pl, tot_pl = equity - base, equity - s["day"]["open_equity"], equity - s["start_cash"]
        fees = sum(x["fee"] for x in trades)
        sells = [x for x in trades if x["side"] == "sell"]
        opt_trades = [x for x in trades if x["side"] == "option"]
        opt_real = [x for x in opt_trades if "realized" in x]
        premium = sum(float(x["px"]) * 100 * x["qty"] for x in opt_trades if x["desc"].startswith("SELL TO OPEN"))
        closed = [x for x in sells if x.get("closed")]
        invested = equity - s["cash"]
        reg = s.get("regime") or {}
        spy, spy_open = quotes.get("SPY", {}), s["day"].get("spy_open")
        title = "PAPER TRADER - DAILY SUMMARY" if daily else "PAPER TRADER - 30 MIN UPDATE"
        L = [f"**{title}**", "Time:", t.strftime("%a %b %d, %I:%M %p ET"), "",
             "Profit/Loss (net of fees):",
             f"{'Today' if daily else 'This period'}: {_money(pl, True)} ({pl / base:+.2%})"]
        if not daily:
            L.append(f"Today: {_money(day_pl, True)} ({day_pl / s['day']['open_equity']:+.2%})")
        L += [f"Since start: {_money(tot_pl, True)} ({tot_pl / s['start_cash']:+.2%})", "",
              "Fees paid:", f"{'Today' if daily else 'This period'}: {_money(fees)} | Total: {_money(s['fees_total'])}", "",
              "Realized P/L (after fees):",
              f"{'Today' if daily else 'This period'}: {_money(sum(x['realized'] for x in sells + opt_real), True)} | "
              f"Total: {_money(s['realized_total'], True)}", "",
              "Equity:", f"{_money(equity)} (cash {_money(s['cash'])} / invested {_money(invested)})", "",
              "Trades:"]
        def _tline(x):
            if x["side"] == "option":
                return f"- {x['desc']}" + (f", net {_money(x['realized'], True)}" if "realized" in x else "") + f" [{x['reason']}]"
            return (f"- {x['side'].upper()} {x['sym']} {x['qty']:g} @ {_money(x['px'])} ({_money(x['value'])})"
                    + (f", net {_money(x['realized'], True)} after {_money(x['fee'])} fees" if x["side"] == "sell" else "")
                    + f" [{x['reason']}]")
        L += [_tline(x) for x in trades[-12:]] or ["- none"]
        if len(trades) > 12:
            L.append(f"- ...and {len(trades) - 12} earlier")
        L += ["", "Holdings maintained:"] + self._holdings(quotes, equity) + ["", "Holdings let go:"]
        L += [f"- {x['sym']}: sold {x['qty']:g} @ {_money(x['px'])}, net {_money(x['realized'], True)} [{x['reason']}]"
              for x in closed] or ["- none"]
        L += ["", "Portfolio trending:", self.trending(equity, t)]
        if spy.get("price") and spy_open:
            L.append(f"vs SPY today: portfolio {day_pl / s['day']['open_equity']:+.2%} / SPY {spy['price'] / spy_open - 1:+.2%}")
        if reg:
            hedge = s["positions"].get(cfg.hedge)
            hv = hedge["qty"] * ((quotes.get(cfg.hedge) or {}).get("price") or hedge["avg"]) if hedge else 0.0
            L += ["", "Volatility / hedge:",
                  f"Regime {reg['name']} (VIX {reg['vix'] or 0:.1f}, SPY 20d vol {(reg['spy_vol20'] or 0):.0%}"
                  f"{', SPY below MA50' if reg.get('spy_below_ma50') else ''})",
                  f"Hedge {cfg.hedge}: target {reg['hedge_target']:.0%}, held {hv / equity:.1%}"]
        if daily:
            wins = [x for x in closed if x["realized"] > 0]
            L += ["", "Day stats:",
                  f"Closed trades {len(closed)} | wins {len(wins)} | win rate {len(wins) / len(closed):.0%}" if closed
                  else "No closed trades today",
                  f"Daily goal +10%: {'met' if day_pl / s['day']['open_equity'] >= 0.10 else 'not met'} "
                  f"(today {day_pl / s['day']['open_equity']:+.2%})"]
        L += ["", "Options income (covered calls / cash-secured puts only, never naked):",
              f"Premium sold {'today' if daily else 'this period'}: {_money(premium)} | "
              f"Collateral reserved: {_money(self.income.collateral())}"]
        L += self.income.lines(quotes) or ["- no open options"]
        note = (s.get("desk") or {}).get("options_note")
        if note and not self.income.opts:
            L.append(f"Last scan: {note}")
        L += self.desk_lines(quotes, equity, t)
        L += ["", "Goals:", self.goal_line("Day", equity / s["day"]["open_equity"] - 1, cfg.daily_min, cfg.daily_max),
              self.goal_line("Week", equity / s["week"]["open_equity"] - 1, cfg.week_min, cfg.week_max)]
        limited = self.pdt_limited()
        L += ["", "Day-trade rule:",
              (f"Limited: {self.day_trades_5d(t)}/{cfg.pdt_max} day trades used (5 business days)" if limited else
               f"No limit ({cfg.account_type} account, equity >= {_money(cfg.pdt_free_min)})")]
        L += ["", "Paper account only. No live orders are placed."]
        return "\n".join(L)

    # ---- loop
    def run_forever(self):
        print("[paper] running; start cash", self.s["start_cash"], "| universe", self.universe())
        while True:
            try:
                phase = self.step()
            except Exception as exc:
                print("[paper] step failed:", repr(exc))
                phase = "error"
            time.sleep(self.cfg.cycle if phase == "open" else 60)


def build(echo=True):
    os.environ.setdefault("TRADING_MODE", "paper")
    from .notify.discord import DiscordNotifier
    from .robinhood.data import shared
    return PaperTrader(shared(), DiscordNotifier(Settings.from_env(), echo=echo), Store())


def status_text(t=None):
    """Compact status for Telegram (/paper): reads stored state, no network calls."""
    st = Store().load()
    if not st:
        return "Paper trader has not started yet."
    eq = st["equity_log"][-1][1] if st["equity_log"] else st["start_cash"]
    L = ["Paper trader (internal, no live orders)", "Equity:", f"{_money(eq)} ({_money(eq - st['start_cash'], True)} since start, "
         f"{(eq / st['start_cash'] - 1):+.2%})", "", "Fees paid:", _money(st["fees_total"]), "",
         "Realized P/L (after fees):", _money(st["realized_total"], True), "", "Holdings:"]
    L += [f"- {s} ({p['sleeve']}): {p['qty']:g} sh @ {_money(p['avg'])}" for s, p in sorted(st["positions"].items())] or ["- none"]
    for o in st.get("options", []):
        L += [f"- option: {o['sym']} {o['exp']} {o['strike']:g}{'C' if o['type'] == 'call' else 'P'} x{o['qty']} "
              f"({'covered call' if o['type'] == 'call' else 'cash-secured put'}), credit ${o['credit']:.2f}"]
    desk = st.get("desk") or {}
    if desk.get("stance"):
        L += ["", f"Desk stance: {desk['stance']} (day {desk['day_ret']:+.2%}, week {desk['week_ret']:+.2%})"]
        L += [f"- {n}" for n in desk.get("notes", [])]
        if desk.get("options_note"):
            L.append(f"- Options: {desk['options_note']}")
    reg = st.get("regime") or {}
    if reg:
        L += ["", "Volatility regime:", f"{reg['name']} (hedge target {reg['hedge_target']:.0%})"]
    L += ["", "Last update:", st["equity_log"][-1][0][:16].replace("T", " ") if st["equity_log"] else "n/a"]
    return "\n".join(L)
