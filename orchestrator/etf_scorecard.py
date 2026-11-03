"""Scores ETFs in a comparison on cost, execution, risk-adjusted return and structure/liquidity.

Metrics with no data are skipped silently and the remaining weights are renormalised.
"""
import math
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

from orchestrator.table_format import table

BENCHMARK = "SPY"
CACHE_TTL = 3600
_cache = {}

BROAD_CATEGORY = re.compile(
    r"large|mid-?cap|small|blend|total|foreign|world|diversified|aggregate|bond|treasury|government",
    re.IGNORECASE,
)

# key: (label, category, weight)
METRICS = {
    "expense": ("Expense ratio", "Costs", 15),
    "spread": ("Bid-ask spread", "Costs", 10),
    "track_diff": ("Tracking diff vs S&P 500 (1y)", "Execution", 7),
    "track_err": ("Tracking error vs S&P 500", "Execution", 7),
    "premium": ("Premium/discount to NAV", "Execution", 6),
    "sharpe": ("Sharpe ratio (1y)", "Risk-adj", 12),
    "beta": ("Beta vs S&P 500 (1y)", "Risk-adj", 8),
    "drawdown": ("Max drawdown (1y)", "Risk-adj", 10),
    "aum": ("AUM", "Structure", 10),
    "volume": ("Avg daily volume", "Structure", 8),
    "concentration": ("Top-10 holdings weight", "Structure", 7),
}
CATEGORIES = ("Costs", "Execution", "Risk-adj", "Structure")
TARGETS = {
    "expense": "<0.10% broad / <0.50% thematic",
    "spread": "<0.05%",
    "track_diff": "within expense ratio",
    "track_err": "near 0%",
    "premium": "near 0%",
    "sharpe": ">1.0 good, >2.0 great",
    "beta": "<1.0 lower risk",
    "drawdown": "lower than peers",
    "aum": ">$100M",
    "volume": "higher is better",
    "concentration": "lower than peers",
}


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _money(value):
    for limit, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= limit:
            return f"${value / limit:.1f}{suffix}"
    return f"${value:.0f}"


def _volume(value):
    for limit, suffix in ((1e6, "M"), (1e3, "K")):
        if value >= limit:
            return f"{value / limit:.1f}{suffix}"
    return f"{value:.0f}"


FORMATS = {
    "expense": lambda v: f"{v:.2f}%",
    "spread": lambda v: f"{v:.2f}%",
    "track_diff": lambda v: f"{v + 0.0:+.1f}%".replace("-0.0", "+0.0"),
    "track_err": lambda v: f"{v:.1f}%",
    "premium": lambda v: f"{v:+.2f}%",
    "sharpe": lambda v: f"{v:.2f}",
    "beta": lambda v: f"{v:.2f}",
    "drawdown": lambda v: f"{v:.1f}%",
    "aum": _money,
    "volume": _volume,
    "concentration": lambda v: f"{v:.0f}%",
}


def _steps(value, steps):
    """steps: [(limit, score)] checked in order for value <= limit; anything beyond scores 0."""
    for limit, score in steps:
        if value <= limit:
            return score
    return 0.0


def _rank_scores(values, lower_better):
    """Peer-relative scores: best 1.0, worst 0.0, others in between."""
    known = {t: v for t, v in values.items() if v is not None}
    if len(known) < 2 or len(set(known.values())) == 1:
        return {t: 0.5 for t in known} if len(known) >= 2 else {}
    low, high = min(known.values()), max(known.values())
    span = high - low
    return {
        t: ((high - v) / span if lower_better else (v - low) / span)
        for t, v in known.items()
    }


def _fetch(ticker):
    """Raw ETF facts and 1y daily returns from Yahoo Finance, or None for non-ETFs."""
    import yfinance as yf

    cached = _cache.get(ticker)
    if cached and time.time() - cached[0] < CACHE_TTL:
        return cached[1]
    result = None
    try:
        handle = yf.Ticker(ticker)
        info = handle.info or {}
        if str(info.get("quoteType", "")).upper() == "ETF":
            holdings = []
            try:
                top = handle.funds_data.top_holdings
                if top is not None and len(top):
                    holdings = [
                        (str(symbol), float(row["Holding Percent"]))
                        for symbol, row in top.iterrows()
                        if _num(row.get("Holding Percent")) is not None
                    ][:10]
            except Exception:
                holdings = []
            closes = handle.history(period="1y")["Close"].dropna()
            result = {
                "info": info,
                "holdings": holdings,
                "closes": closes,
            }
    except Exception as exc:
        print("ETF SCORECARD FETCH FAILED:", ticker, repr(exc))
    _cache[ticker] = (time.time(), result)
    return result


def _benchmark_closes():
    cached = _cache.get("__bench__")
    if cached and time.time() - cached[0] < CACHE_TTL:
        return cached[1]
    import yfinance as yf
    closes = yf.Ticker(BENCHMARK).history(period="1y")["Close"].dropna()
    _cache["__bench__"] = (time.time(), closes)
    return closes


def _raw_metrics(raw, bench):
    info = raw["info"]
    out = {}
    er = _num(info.get("netExpenseRatio")) or _num(info.get("annualReportExpenseRatio"))
    if er is not None:
        out["expense"] = er
    bid, ask = _num(info.get("bid")), _num(info.get("ask"))
    if bid and ask and ask >= bid:
        spread = (ask - bid) / ((ask + bid) / 2) * 100
        if spread < 3:  # wider quotes are stale after-hours snapshots, not real spreads
            out["spread"] = spread
    nav = _num(info.get("navPrice"))
    last = _num(info.get("previousClose")) or _num(info.get("regularMarketPrice"))
    if nav and last:
        out["premium"] = (last - nav) / nav * 100
    aum = _num(info.get("totalAssets"))
    if aum:
        out["aum"] = aum
    volume = _num(info.get("averageVolume")) or _num(info.get("averageDailyVolume10Day"))
    if volume:
        out["volume"] = volume
    weights = [w for _, w in raw["holdings"]]
    if weights:
        out["concentration"] = sum(weights) * 100

    closes = raw["closes"]
    if len(closes) >= 60:
        returns = closes.pct_change().dropna()
        std = returns.std()
        if std and std > 0:
            rf = _num(os.getenv("RISK_FREE_RATE")) or 0.04
            out["sharpe"] = (returns.mean() * 252 - rf) / (std * math.sqrt(252))
        peak = closes.cummax()
        out["drawdown"] = float(((closes - peak) / peak).min() * 100)
        if bench is not None and len(bench) >= 60:
            pair = returns.to_frame("etf").join(bench.pct_change().dropna().rename("bench"), how="inner").dropna()
            if len(pair) >= 60 and pair["bench"].var() > 0:
                out["beta"] = float(pair["etf"].cov(pair["bench"]) / pair["bench"].var())
                # tracking figures only mean something for funds that follow the S&P 500
                if pair["etf"].corr(pair["bench"]) >= 0.95:
                    diff = pair["etf"] - pair["bench"]
                    out["track_err"] = float(diff.std() * math.sqrt(252) * 100)
                    out["track_diff"] = float(((1 + pair["etf"]).prod() - (1 + pair["bench"]).prod()) * 100)
    return out


def _absolute_scores(metrics, broad):
    scores = {}
    if "expense" in metrics:
        target = 0.10 if broad else 0.50
        scores["expense"] = _steps(metrics["expense"], [(target, 1.0), (target * 1.5, 0.5)])
    if "spread" in metrics:
        scores["spread"] = _steps(metrics["spread"], [(0.05, 1.0), (0.25, 0.5)])
    if "premium" in metrics:
        scores["premium"] = _steps(abs(metrics["premium"]), [(0.10, 1.0), (0.50, 0.5)])
    if "track_err" in metrics:
        scores["track_err"] = _steps(metrics["track_err"], [(0.5, 1.0), (1.5, 0.5)])
    if "track_diff" in metrics:
        margin = max(metrics.get("expense", 0.0), 0.05)
        scores["track_diff"] = _steps(abs(metrics["track_diff"]), [(margin, 1.0), (margin + 1.0, 0.5)])
    if "sharpe" in metrics:
        sharpe = metrics["sharpe"]
        scores["sharpe"] = 1.0 if sharpe > 2 else 0.8 if sharpe > 1 else 0.4 if sharpe > 0 else 0.0
    if "beta" in metrics:
        scores["beta"] = _steps(metrics["beta"], [(1.0, 1.0), (1.3, 0.5)])
    if "aum" in metrics:
        scores["aum"] = 1.0 if metrics["aum"] > 100e6 else 0.5 if metrics["aum"] > 50e6 else 0.0
    return scores


class ETFScorecard:
    def __init__(self, loader=None, benchmark_loader=None):
        self._loader = loader or _fetch
        self._benchmark_loader = benchmark_loader or _benchmark_closes

    def build(self, tickers):
        """Returns the scorecard text, or '' unless at least two of the tickers are ETFs with data."""
        profiles = self.score(tickers)
        if len(profiles) < 2:
            return ""
        return "\n\n".join(
            part for part in (
                "**ETF Scorecard**",
                self._metric_table(profiles),
                self._score_table(profiles),
                self._read(profiles),
            ) if part
        )

    def score(self, tickers):
        tickers = [str(t).upper() for t in dict.fromkeys(tickers or [])]
        if len(tickers) < 2:
            return {}
        with ThreadPoolExecutor(max_workers=min(4, len(tickers))) as pool:
            fetched = list(pool.map(self._safe_load, tickers))
        raws = {t: r for t, r in zip(tickers, fetched) if r}
        if len(raws) < 2:
            return {}
        try:
            bench = self._benchmark_loader()
        except Exception as exc:
            print("ETF SCORECARD BENCHMARK FAILED:", repr(exc))
            bench = None

        profiles = {}
        for ticker, raw in raws.items():
            metrics = _raw_metrics(raw, bench)
            category = str(raw["info"].get("category") or "")
            broad = bool(BROAD_CATEGORY.search(category))
            profiles[ticker] = {
                "metrics": metrics,
                "scores": _absolute_scores(metrics, broad),
                "holdings": dict(raw["holdings"]),
                "name": raw["info"].get("longName") or ticker,
            }
        for key, lower_better in (("drawdown", False), ("volume", False), ("concentration", True)):
            ranked = _rank_scores({t: p["metrics"].get(key) for t, p in profiles.items()}, lower_better)
            for ticker, score in ranked.items():
                profiles[ticker]["scores"][key] = score
        for profile in profiles.values():
            profile.update(self._rollup(profile["scores"]))
        return profiles

    def _safe_load(self, ticker):
        try:
            return self._loader(ticker)
        except Exception as exc:
            print("ETF SCORECARD LOAD FAILED:", ticker, repr(exc))
            return None

    @staticmethod
    def _rollup(scores):
        by_category = {}
        for key, score in scores.items():
            _, category, weight = METRICS[key]
            earned, total = by_category.get(category, (0.0, 0.0))
            by_category[category] = (earned + score * weight, total + weight)
        earned_all = sum(e for e, _ in by_category.values())
        total_all = sum(t for _, t in by_category.values())
        return {
            "category_scores": {c: round(e / t * 100) for c, (e, t) in by_category.items() if t},
            "total": round(earned_all / total_all * 100) if total_all else None,
        }

    def _metric_table(self, profiles):
        tickers = list(profiles)
        rows = []
        for key, (label, _, _) in METRICS.items():
            values = [profiles[t]["metrics"].get(key) for t in tickers]
            if all(v is None for v in values):
                continue
            rows.append(
                [label.replace(" vs S&P 500", "").replace(" (1y)", "")]
                + [FORMATS[key](v) if v is not None else "-" for v in values]
                + [TARGETS[key]]
            )
        if not rows:
            return ""
        return table(["Metric"] + tickers + ["Target"], rows, aligns="l" + "r" * len(tickers) + "l")

    def _score_table(self, profiles):
        rows = []
        for ticker, p in sorted(profiles.items(), key=lambda item: item[1]["total"] or -1, reverse=True):
            if p["total"] is None:
                continue
            rows.append(
                [ticker]
                + [str(p["category_scores"].get(c, "-")) for c in CATEGORIES]
                + [f"{p['total']}/100"]
            )
        if not rows:
            return ""
        return table(["Ticker", "Costs", "Execution", "Risk-adj", "Structure", "Score"], rows, aligns="lrrrrr")

    def _read(self, profiles):
        ranked = sorted(
            ((t, p) for t, p in profiles.items() if p["total"] is not None),
            key=lambda item: item[1]["total"],
            reverse=True,
        )
        if len(ranked) < 2:
            return ""
        (top, top_p), (second, second_p) = ranked[0], ranked[1]
        gaps = {
            c: top_p["category_scores"][c] - second_p["category_scores"][c]
            for c in CATEGORIES
            if c in top_p["category_scores"] and c in second_p["category_scores"]
        }
        lines = []
        if top_p["total"] - second_p["total"] < 5:
            lines.append(
                f"**Scorecard read:** {top} ({top_p['total']}) and {second} ({second_p['total']}) are too close "
                "on cost, execution, risk and structure to separate."
            )
        else:
            driver = max(gaps, key=gaps.get) if gaps else None
            lines.append(
                f"**Scorecard read:** {top} scores highest ({top_p['total']}/100)"
                + (f", mostly on {driver.lower()}" if driver and gaps[driver] > 0 else "")
                + f", ahead of {second} ({second_p['total']})."
            )
        weakest = [
            f"{t} on {min(p['category_scores'], key=p['category_scores'].get).lower()}"
            for t, p in ranked
            if p["category_scores"] and min(p["category_scores"].values()) <= 25
        ]
        if weakest:
            lines.append("Weak spots: " + ", ".join(weakest) + ".")
        overlap = self._overlap(profiles)
        if overlap:
            lines.append(overlap)
        if ranked[0][1]["total"] < 50:
            lines.append("No fund clears 50/100, so the scores favour caution on all of them.")
        return " ".join(lines)

    @staticmethod
    def _overlap(profiles):
        tickers = list(profiles)
        pairs = []
        for i, a in enumerate(tickers):
            for b in tickers[i + 1:]:
                ha, hb = profiles[a]["holdings"], profiles[b]["holdings"]
                shared = sum(min(ha[s], hb[s]) for s in set(ha) & set(hb))
                if shared >= 0.5:
                    pairs.append(f"{a}/{b} {shared * 100:.0f}%")
        if not pairs:
            return ""
        return "Top-10 holdings overlap: " + ", ".join(pairs) + " (holding both adds little diversification)."
