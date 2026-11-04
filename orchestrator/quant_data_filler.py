"""Fills quant ratings the Gaming PC could not compute from its own fundamentals.

The quant worker returns "Missing Financial Data" (stability) or a hard "Poor" (financial strength, for ETFs
that have no company statements). When that happens the rating is derived from Robinhood price history and
fundamentals and the Alpha Vantage ETF profile instead. Ratings the quant did compute are never changed.
"""
import math
import sys
import time
from pathlib import Path

TRADER_DIR = Path(__file__).resolve().parents[1] / "Agentic_Trader"
TIERS = ("Poor", "Average", "Good", "Excellent")
MISSING = {"", "missing financial data", "insufficient history", "insufficient data", "n/a", "none", "unknown"}
CACHE_TTL = 3600


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _is_missing(value):
    return value is None or str(value).strip().lower() in MISSING


def _tier(points, cuts):
    """cuts: ascending thresholds for Average, Good, Excellent."""
    return TIERS[sum(1 for cut in cuts if points >= cut)]


class QuantDataFiller:
    def __init__(self, robinhood=None, alpha_vantage=None):
        self._robinhood = robinhood
        self._alpha = alpha_vantage
        self._cache = {}

    def _rh(self):
        if self._robinhood is None:
            if str(TRADER_DIR) not in sys.path:
                sys.path.append(str(TRADER_DIR))
            from agentic_trader.robinhood import oauth
            if not oauth.is_configured():
                return None
            from agentic_trader.robinhood.data import shared
            self._robinhood = shared()
        return self._robinhood

    def _av(self):
        if self._alpha is None:
            if str(TRADER_DIR) not in sys.path:
                sys.path.append(str(TRADER_DIR))
            from agentic_trader.market_apis.alpha_vantage import AlphaVantage
            client = AlphaVantage()
            self._alpha = client if client.configured() else False
        return self._alpha or None

    def _cached(self, key, loader):
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < CACHE_TTL:
            return hit[1]
        try:
            value = loader()
        except Exception as exc:
            print("QUANT GAP FILL SOURCE FAILED:", key, repr(exc))
            value = None
        self._cache[key] = (time.time(), value)
        return value

    def fill(self, analysis):
        """Returns {metric_key: (rating, source)} for ratings the quant left empty or unsupported."""
        if not isinstance(analysis, dict):
            return {}
        ticker = str(analysis.get("ticker") or "").upper()
        if not ticker:
            return {}
        out = {}
        if _is_missing(analysis.get("stability_rating")):
            rating = self._stability(ticker)
            if rating:
                out["stability_rating"] = (rating, "Robinhood price history")
        if self._needs_fund_strength(analysis):
            rating = self._fund_strength(ticker)
            if rating:
                out["financial_strength_rating"] = (rating, "Robinhood and Alpha Vantage fund data")
        return out

    @staticmethod
    def _needs_fund_strength(analysis):
        # No company statements behind the score: a 0 here reflects absent inputs, not a weak fund.
        no_statements = all(analysis.get(k) in (None, "") for k in ("price", "market_cap", "price_to_book", "peg_ratio"))
        rating = analysis.get("financial_strength_rating")
        return no_statements and (analysis.get("financial_strength_score") in (0, None)) and (
            _is_missing(rating) or str(rating).strip().lower() == "poor"
        )

    def _closes(self, ticker):
        rh = self._rh()
        if rh is None:
            return None

        def load():
            bars = rh.bars([ticker, "SPY"], "day", 400)
            return {s: [b["close"] for b in rows if b.get("close")] for s, rows in bars.items()}

        return self._cached(("bars", ticker), load)

    def _stability(self, ticker):
        data = self._closes(ticker) or {}
        closes = data.get(ticker) or []
        if len(closes) < 120:
            return None
        closes = closes[-252:]
        returns = [b / a - 1 for a, b in zip(closes, closes[1:]) if a]
        mean = sum(returns) / len(returns)
        vol = math.sqrt(sum((r - mean) ** 2 for r in returns) / max(len(returns) - 1, 1)) * math.sqrt(252) * 100
        peak, drawdown = closes[0], 0.0
        for close in closes:
            peak = max(peak, close)
            drawdown = min(drawdown, (close / peak - 1) * 100)
        points = (
            (3 if vol < 12 else 2 if vol < 20 else 1 if vol < 32 else 0)
            + (3 if drawdown > -8 else 2 if drawdown > -15 else 1 if drawdown > -28 else 0)
        )
        return _tier(points, (2, 4, 6))

    def _fund_strength(self, ticker):
        aum = er = None
        leveraged = False
        rh = self._rh()
        if rh is not None:
            fundamentals = self._cached(("fund", ticker), lambda: rh.fundamentals([ticker]).get(ticker))
            aum = _num((fundamentals or {}).get("market_cap"))
        av = self._av()
        if av is not None:
            profile = self._cached(("etf", ticker), lambda: av.etf_profile(ticker))
            if profile:
                aum = _num(profile.get("net_assets")) or aum
                er = _num(profile.get("net_expense_ratio"))
                if er is not None:
                    er *= 100  # Alpha Vantage gives a fraction
                leveraged = str(profile.get("leveraged", "")).upper() == "YES"
        if aum is None and er is None:
            return None
        points = 0
        if aum is not None:
            points += 3 if aum >= 10e9 else 2 if aum >= 1e9 else 1 if aum >= 100e6 else 0
        if er is not None:
            points += 2 if er <= 0.20 else 1 if er <= 0.60 else 0
        if leveraged:
            points -= 1
        scale = (aum is not None) * 3 + (er is not None) * 2
        return _tier(points / scale * 5, (1.5, 3.0, 4.0))
