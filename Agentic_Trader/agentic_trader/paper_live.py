"""Internal live paper trading on real Robinhood market data (read-only data path only).

- Starts with PAPER_START_CASH ($5,000). Orders are simulated here; nothing is ever sent to Robinhood.
- State lives in the shared_storage cache (namespace `paper_trader`) with a JSON mirror in state/.
- Sleeves: ETF core (trend-filtered), day trader (live-quote quant signal, inverse-vol sizing, flat by close),
  and a volatility hedge (VIX + SPY realized vol -> long-only inverse ETF + smaller day-trade size).
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
        self.day_pct = float(os.getenv("PAPER_DAY_PCT", "0.25"))
        self.etfs = _csv("PAPER_ETFS", "VOO,QQQ,SCHD,VXUS")
        self.day_symbols = _csv("PAPER_DAY_SYMBOLS", "NVDA,AAPL,AMD,TSLA,MSFT,META")
        self.hedge = os.getenv("PAPER_HEDGE_SYMBOL", "SH").upper()
        self.cycle = int(os.getenv("PAPER_CYCLE_SECONDS", "300"))
        self.entry = float(os.getenv("PAPER_ENTRY_SIGNAL", "0.20"))
        self.stop = float(os.getenv("PAPER_STOP_PCT", "0.015"))
        self.target = float(os.getenv("PAPER_TARGET_PCT", "0.02"))
        self.max_day_positions = int(os.getenv("PAPER_MAX_DAY_POSITIONS", "3"))
        self.min_trade = float(os.getenv("PAPER_MIN_TRADE_USD", "5"))
        # 2026 rule: margin accounts with >= $2,000 equity have no day-trade limit; otherwise the
        # legacy limit (max 3 day trades per 5 business days under $25,000) applies.
        self.account_type = os.getenv("PAPER_ACCOUNT_TYPE", "margin").lower()
        self.pdt_free_min = float(os.getenv("PAPER_PDT_FREE_MIN_EQUITY", "2000"))
        self.pdt_max = int(os.getenv("PAPER_PDT_MAX_DAY_TRADES", "3"))
        self.pdt_legacy_equity = float(os.getenv("PAPER_PDT_LEGACY_EQUITY", "25000"))
        self.cooldown_min = int(os.getenv("PAPER_COOLDOWN_MIN", "30"))


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
        return sorted(set(c.etfs) | set(c.day_symbols) | {c.hedge, "SPY"} | set(self.s["positions"]))

    def equity(self, quotes):
        return self.s["cash"] + sum(p["qty"] * (quotes.get(sym, {}).get("price") or p["avg"])
                                    for sym, p in self.s["positions"].items())

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
    def buy(self, sym, usd, sleeve, reason, q, t):
        px = self.fill_px(q, "buy")
        usd = min(usd, self.s["cash"])
        if not px or usd < self.cfg.min_trade:
            return False
        qty = round(usd / px, 6)
        cost = qty * px
        pos = self.s["positions"].setdefault(sym, {"qty": 0.0, "avg": 0.0, "sleeve": sleeve, "opened": t.isoformat()})
        pos["avg"] = (pos["avg"] * pos["qty"] + cost) / (pos["qty"] + qty)
        pos["qty"] = round(pos["qty"] + qty, 6)
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
        qty = min(qty, pos["qty"])
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

    def core_sleeve(self, quotes, t, equity):
        target = equity * self.cfg.core_pct / max(1, len(self.cfg.etfs))
        bars = self.data.bars(self.cfg.etfs, "day", 120, ttl=1800)
        for sym in self.cfg.etfs:
            q, closes = quotes.get(sym), [b["close"] for b in bars.get(sym, []) if b.get("close")]
            if not q or not q.get("price") or len(closes) < 50:
                continue
            ma50, px, held = float(np.mean(closes[-50:])), q["price"], self.s["positions"].get(sym)
            if held and px < ma50 * 0.985:
                self.sell(sym, held["qty"], f"ETF trend break (below MA50 {ma50:.2f})", q, t)
            elif not held and px > ma50:
                self.buy(sym, min(target, self.s["cash"]), "core", f"ETF trend up (above MA50 {ma50:.2f})", q, t)

    def hedge_sleeve(self, quotes, t, equity, reg):
        sym = self.cfg.hedge
        q = quotes.get(sym)
        if not q or not q.get("price"):
            return
        held = self.s["positions"].get(sym)
        cur = (held["qty"] * q["price"]) if held else 0.0
        want = equity * reg["hedge_target"]
        band = max(self.cfg.min_trade, equity * 0.025)
        why = f"{reg['name']} volatility (VIX {reg['vix'] or 0:.1f}, SPY 20d vol {(reg['spy_vol20'] or 0):.0%})"
        if want - cur > band:
            self.buy(sym, want - cur, "hedge", f"hedge up: {why}", q, t)
        elif cur - want > band and held:
            self.sell(sym, min(held["qty"], (cur - want) / q["price"]) if want > 0 else held["qty"],
                      f"hedge down: {why}", q, t)

    def day_sleeve(self, quotes, t, equity, reg, phase_hm):
        c = self.cfg
        day_syms = [s for s, p in self.s["positions"].items() if p["sleeve"] == "day"]
        flatten = phase_hm >= FLATTEN_AT
        sig = {}
        try:
            sig = self.analyze(c.day_symbols)
        except Exception as exc:
            print("[paper] analyze failed:", repr(exc))
        for sym in day_syms:
            p, q = self.s["positions"][sym], quotes.get(sym, {})
            px = q.get("price")
            if not px:
                continue
            ret = px / p["avg"] - 1
            score = (sig.get(sym) or {}).get("signal_score")
            reason = ("end-of-day flatten" if flatten else f"stop {ret:+.1%}" if ret <= -c.stop else
                      f"target {ret:+.1%}" if ret >= c.target else
                      f"signal flipped ({score:+.2f})" if score is not None and score <= -0.10 else None)
            if reason:
                self.sell(sym, p["qty"], reason, q, t)
        if flatten or phase_hm >= NO_ENTRY_AFTER:
            return
        if self.pdt_limited() and self.day_trades_5d(t) >= c.pdt_max:
            return
        open_n = sum(1 for p in self.s["positions"].values() if p["sleeve"] == "day")
        budget = equity * c.day_pct - sum(p["qty"] * (quotes.get(s, {}).get("price") or p["avg"])
                                          for s, p in self.s["positions"].items() if p["sleeve"] == "day")
        ranked = sorted(((m.get("signal_score") or -9, s, m) for s, m in sig.items()
                         if isinstance(m, dict) and "error" not in m and s in c.day_symbols), reverse=True)
        for score, sym, m in ranked:
            if open_n >= c.max_day_positions or budget < c.min_trade:
                break
            q = quotes.get(sym)
            cd = self.s["cooldown"].get(sym)
            if (sym in self.s["positions"] or not q or score < c.entry or (m.get("rsi14") or 50) >= 75
                    or (cd and (t - datetime.fromisoformat(cd)).total_seconds() < c.cooldown_min * 60)):
                continue
            vol = m.get("realized_vol_ann") or 0.3
            size = min(budget, equity * c.day_pct / c.max_day_positions * reg["day_scale"] * min(1.0, 0.35 / max(vol, 0.05)))
            if self.buy(sym, size, "day", f"signal {score:+.2f}, RSI {m.get('rsi14') or 0:.0f}, vol {vol:.0%}", q, t):
                open_n += 1
                budget -= size

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
        hm = (t.hour, t.minute)
        if phase == "open" and hm >= (9, 35):
            equity = self.equity(quotes)
            reg = self.volatility()
            for fn, args in ((self.day_sleeve, (quotes, t, equity, reg, hm)), (self.core_sleeve, (quotes, t, equity)),
                             (self.hedge_sleeve, (quotes, t, equity, reg))):
                try:
                    fn(*args)
                except Exception as exc:
                    print(f"[paper] {fn.__name__} failed:", repr(exc))
        equity = self.equity(quotes)
        self.s["equity_log"].append([t.isoformat(), equity])
        self.s["equity_log"] = self.s["equity_log"][-4000:]
        if phase == "open":
            self.maybe_post_half_hour(t, quotes, equity)
        elif phase == "close" and not day["eod_posted"]:
            self.n.post("updates", self.summary(t, quotes, equity, daily=True))
            day["eod_posted"] = True
        self.store.save(self.s)
        return phase

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

    def summary(self, t, quotes, equity, daily):
        s, cfg = self.s, self.cfg
        since = datetime.fromisoformat(s["last_summary"]["ts"])
        day_start = t.replace(hour=0, minute=0, second=0, microsecond=0)
        trades = [x for x in s["trades"] if datetime.fromisoformat(x["ts"]) > (day_start if daily else since)]
        base = s["day"]["open_equity"] if daily else s["last_summary"]["equity"]
        pl, day_pl, tot_pl = equity - base, equity - s["day"]["open_equity"], equity - s["start_cash"]
        fees = sum(x["fee"] for x in trades)
        sells = [x for x in trades if x["side"] == "sell"]
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
              f"{'Today' if daily else 'This period'}: {_money(sum(x['realized'] for x in sells), True)} | "
              f"Total: {_money(s['realized_total'], True)}", "",
              "Equity:", f"{_money(equity)} (cash {_money(s['cash'])} / invested {_money(invested)})", "",
              "Trades:"]
        L += [f"- {x['side'].upper()} {x['sym']} {x['qty']:g} @ {_money(x['px'])} ({_money(x['value'])})"
              + (f", net {_money(x['realized'], True)} after {_money(x['fee'])} fees" if x["side"] == "sell" else "")
              + f" [{x['reason']}]" for x in trades[-12:]] or ["- none"]
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
                  else "No closed trades today"]
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
    reg = st.get("regime") or {}
    if reg:
        L += ["", "Volatility regime:", f"{reg['name']} (hedge target {reg['hedge_target']:.0%})"]
    L += ["", "Last update:", st["equity_log"][-1][0][:16].replace("T", " ") if st["equity_log"] else "n/a"]
    return "\n".join(L)
