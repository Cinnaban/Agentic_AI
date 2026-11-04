"""Historical ranking of single indicators and two-metric combinations.

Every candidate is a causal, boolean entry condition on daily bars. Forward returns (1 and 5 days, net of cost) are
measured against SPY over the same window, using non-overlapping events per symbol. To avoid look-ahead and
selection bias the history is split by TIME (never randomly):

  train    first `TRAIN_FRAC` of the dates: used only to rank candidates
  holdout  the rest, after a purge gap of `HORIZON` bars: used only to confirm the ranking

A candidate earns priority weight only if it is positive on the holdout as well; everything else gets zero.
Tiers: "confirmed" (strong on train and a significant holdout) gets up to full weight, "provisional" (strong on train,
merely positive on the holdout) gets a small fixed weight, everything else none.
With many candidates tested, some pass by luck, so the output also reports how many were tested and how many
confirmed. Run: python -m agentic_trader.signal_research
"""
from __future__ import annotations

import itertools
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent.parent / "state" / "signal_ranking.json"
HORIZON = 5
COST = 0.0005
TRAIN_FRAC = 0.6
MIN_TRAIN, MIN_HOLD = 120, 50
PROVISIONAL_WEIGHT = 0.25


def _rsi(c, n):
    d = np.diff(c, prepend=c[0])
    up, dn = np.clip(d, 0, None), np.clip(-d, 0, None)
    au, ad = np.zeros(len(c)), np.zeros(len(c))
    for i in range(1, len(c)):
        au[i] = (au[i - 1] * (n - 1) + up[i]) / n
        ad[i] = (ad[i - 1] * (n - 1) + dn[i]) / n
    return np.where(ad == 0, 100.0, 100 - 100 / (1 + au / np.where(ad == 0, 1, ad)))


def _roll(x, n, fn):
    out = np.full(len(x), np.nan)
    for i in range(n - 1, len(x)):
        out[i] = fn(x[i - n + 1:i + 1])
    return out


def _ema(x, n):
    out, a = np.empty(len(x)), 2 / (n + 1)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def conditions(o, h, l, c, v):
    """Name -> boolean array. All values at bar i use data up to and including bar i."""
    n = len(c)
    sma = lambda k: _roll(c, k, np.mean)
    s20, s50, s200 = sma(20), sma(50), sma(200)
    sd20 = _roll(c, 20, np.std)
    z = (c - s20) / np.where(sd20 == 0, np.nan, sd20)
    ret = np.diff(np.log(c), prepend=np.log(c[0]))
    rv = _roll(ret, 20, np.std) * math.sqrt(252)
    rv_med = _roll(rv, 120, np.nanmedian)
    rvol = v / _roll(v.astype(float), 20, np.mean)
    macd = _ema(c, 12) - _ema(c, 26)
    hist = macd - _ema(macd, 9)
    hi20 = np.concatenate([[np.nan], _roll(h, 20, np.max)[:-1]])
    lo20 = np.concatenate([[np.nan], _roll(l, 20, np.min)[:-1]])
    mom = np.full(n, np.nan)
    if n > 252:
        mom[252:] = c[231:n - 21] / c[:n - 252] - 1
    pc = np.concatenate([[np.nan], c[:-1]])
    gap = o / pc - 1
    rng = h - l
    clv = np.where(rng == 0, 0.5, (c - l) / np.where(rng == 0, 1, rng))
    nr7 = rng <= _roll(rng, 7, np.min)
    r2, r14 = _rsi(c, 2), _rsi(c, 14)
    ok = lambda a: np.nan_to_num(a, nan=0).astype(bool)
    with np.errstate(invalid="ignore"):
        return {
            "RSI2<10": ok(r2 < 10), "RSI14<35": ok(r14 < 35), "RSI14>60": ok(r14 > 60),
            "MACD hist up": ok((hist > 0) & (np.roll(hist, 1) <= 0)), "MACD>0": ok(macd > 0),
            "Z<-1.5": ok(z < -1.5), "Z>1": ok(z > 1),
            "RVOL>1.5": ok(rvol > 1.5), "RVOL<0.8": ok(rvol < 0.8),
            "RV>median": ok(rv > rv_med), "RV<median": ok(rv < rv_med),
            "Trend>SMA50": ok(c > s50), "Trend>SMA200": ok(c > s200), "SMA20>SMA50": ok(s20 > s50),
            "Breakout20": ok(c > hi20), "Breakdown20": ok(c < lo20),
            "Mom12-1>0": ok(mom > 0), "Gap<-1%": ok(gap < -0.01), "Gap>1%": ok(gap > 0.01),
            "CloseNearHigh": ok(clv > 0.8), "NR7": ok(nr7),
        }


def _events(cond, bench, c, lo, hi):
    """Non-overlapping events in [lo, hi): forward-HORIZON net return and the same-window benchmark return."""
    out, i = [], max(lo, 1)
    while i < min(hi, len(c) - HORIZON - 1):
        if cond[i]:
            # enter next open proxy = next close-to-close from bar i (signal known at the close of bar i)
            out.append((c[i + HORIZON] / c[i] - 1 - COST, bench[i + HORIZON] / bench[i] - 1))
            i += HORIZON
        else:
            i += 1
    return out


def _stats(ev):
    if not ev:
        return {"n": 0, "excess_bp": 0.0, "hit": 0.0, "pf": 0.0, "t": 0.0}
    r = np.array([a for a, _ in ev])
    ex = np.array([a - b for a, b in ev])
    gain, loss = r[r > 0].sum(), -r[r < 0].sum()
    t = ex.mean() / (ex.std(ddof=1) / math.sqrt(len(ex))) if len(ex) > 2 and ex.std(ddof=1) > 0 else 0.0
    return {"n": len(ev), "excess_bp": round(float(ex.mean() * 1e4), 1), "hit": round(float((r > 0).mean()), 3),
            "pf": round(float(gain / loss) if loss else 9.99, 2), "t": round(float(t), 2)}


def run(daily: dict, bench_sym="SPY"):
    """`daily` maps symbol -> bars [{open,high,low,close,volume}], oldest first, aligned to the same dates."""
    bars = {s: b for s, b in daily.items() if len(b) > 300}
    if bench_sym not in bars:
        raise ValueError("benchmark bars missing")
    n = min(len(b) for b in bars.values())
    arr = {s: [np.array([float(x.get(k) or x["close"]) for x in b[-n:]]) for k in ("open", "high", "low", "close", "volume")]
           for s, b in bars.items()}
    bench = arr[bench_sym][3]
    cut = int(n * TRAIN_FRAC)
    conds = {s: conditions(*a) for s, a in arr.items() if s != bench_sym}
    names = list(next(iter(conds.values())))
    cands = [(nm,) for nm in names] + list(itertools.combinations(names, 2))
    rows = []
    for combo in cands:
        tr_ev, ho_ev = [], []
        for s, cd in conds.items():
            mask = np.logical_and.reduce([cd[k] for k in combo])
            c = arr[s][3]
            tr_ev += _events(mask, bench, c, 0, cut)
            ho_ev += _events(mask, bench, c, cut + HORIZON, n)
        a, b = _stats(tr_ev), _stats(ho_ev)
        if a["n"] < MIN_TRAIN:
            continue
        rows.append({"name": " + ".join(combo), "parts": len(combo), "train": a, "holdout": b})
    rows.sort(key=lambda r: (r["train"]["t"], r["train"]["excess_bp"]), reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
        ho_ok = r["holdout"]["n"] >= MIN_HOLD and r["holdout"]["excess_bp"] > 0 and r["train"]["t"] >= 1.5
        r["confirmed"] = bool(ho_ok and r["holdout"]["t"] >= 1.0)
        r["tier"] = "confirmed" if r["confirmed"] else "provisional" if ho_ok else "none"
        if r["tier"] == "confirmed":
            r["weight"] = round(min(1.0, r["holdout"]["t"] / 3.0), 2)  # scales with holdout evidence
        elif r["tier"] == "provisional":
            r["weight"] = PROVISIONAL_WEIGHT
    top = [r for r in rows if r["confirmed"]]
    prio = [r for r in rows if r["tier"] != "none"]
    def _avg(sel, k):
        v = [r["holdout"][k] for r in sel if r["holdout"]["n"] >= MIN_HOLD]
        return round(float(np.mean(v)), 2) if v else 0.0

    one, two = [r for r in rows if r["parts"] == 1], [r for r in rows if r["parts"] == 2]
    top_n = lambda sel: sel[:10]
    summary = {"single_avg_holdout_excess_bp": _avg(one, "excess_bp"), "combo_avg_holdout_excess_bp": _avg(two, "excess_bp"),
               "top10_single_holdout_excess_bp": _avg(top_n(one), "excess_bp"),
               "top10_combo_holdout_excess_bp": _avg(top_n(two), "excess_bp")}
    return {"ts": datetime.now(timezone.utc).isoformat(), "summary": summary, "singles": one, "bars": n, "symbols": len(conds), "horizon": HORIZON,
            "tested": len(rows), "confirmed": len(top), "train_frac": TRAIN_FRAC, "ranking": rows[:60],
            "provisional": len(prio) - len(top),
            "confirmed_list": top[:30], "priority_list": prio[:40]}


def weights(path=OUT):
    """{indicator condition name: weight} for confirmed candidates (empty when no research has been run)."""
    try:
        d = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}
    return {r["name"]: r["weight"] for r in d.get("priority_list", [])}


class SignalRank:
    """Live priority score: the summed weight of confirmed and provisional indicator/combination conditions true on a
    symbol's latest daily bar. Candidates that failed the holdout carry no weight."""

    MAX_AGE_DAYS = 7

    def __init__(self, path=OUT, enabled=True):
        self.path, self.enabled = Path(path), enabled
        self.w = weights(self.path) if enabled else {}

    def reload(self):
        self.w = weights(self.path) if self.enabled else {}

    def stale(self, now=None):
        try:
            ts = datetime.fromisoformat(json.loads(self.path.read_text())["ts"])
        except (OSError, ValueError, KeyError):
            return True
        return ((now or datetime.now(timezone.utc)) - ts).days >= self.MAX_AGE_DAYS

    def refresh(self, data, symbols, now=None):
        """Re-run the research when the saved ranking is older than a week. Returns True when it re-ran."""
        if not self.enabled or not self.stale(now):
            return False
        syms = sorted(set(symbols) | {"SPY"})
        res = run(data.bars(syms, "day", 1900, ttl=3600))
        self.path.parent.mkdir(exist_ok=True)
        self.path.write_text(json.dumps(res, indent=1))
        self.reload()
        return True

    def score(self, bars):
        """(score, [matched condition names]) from daily bars, oldest first."""
        if not self.w or len(bars) < 260:
            return 0.0, []
        try:
            arr = [np.array([float(x.get(k) or x["close"]) for x in bars]) for k in ("open", "high", "low", "close", "volume")]
            cd = conditions(*arr)
        except Exception:
            return 0.0, []
        hit = [nm for nm in self.w if all(cd[p][-1] for p in nm.split(" + ") if p in cd)]
        return round(sum(self.w[nm] for nm in hit), 3), hit


def main():
    from .robinhood.data import RobinhoodData
    from .paper_live import Cfg
    c = Cfg()
    syms = sorted(set(c.etfs) | set(c.day_symbols) | {"SPY"} | set(c.opt_symbols))
    data = RobinhoodData().bars(syms, "day", 1900, ttl=3600)
    res = run(data)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1))
    print(f"tested {res['tested']} candidates on {res['symbols']} symbols x {res['bars']} days; "
          f"{res['confirmed']} confirmed and {res['provisional']} provisional on the holdout")
    print("singles vs combinations (holdout):", res["summary"])
    print("best single indicators:", ", ".join(f"{r['name']} ({r['holdout']['excess_bp']:+.0f}bp)" for r in res["singles"][:5]))
    for r in res["ranking"][:15]:
        print(f"#{r['rank']:2d} {r['name']:34s} train n={r['train']['n']:4d} ex={r['train']['excess_bp']:6.1f}bp t={r['train']['t']:5.2f}"
              f" | hold n={r['holdout']['n']:4d} ex={r['holdout']['excess_bp']:6.1f}bp t={r['holdout']['t']:5.2f}"
              f" {r['tier'].upper() if r['tier'] != 'none' else ''}")


if __name__ == "__main__":
    main()
