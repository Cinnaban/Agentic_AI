"""News sentiment and the cash rate for the trading agents, from Alpha Vantage under a strict request budget.

The 25-requests/day free tier is shared with the root bots, so the trader only spends a few calls a day and always
leaves a reserve for them. Everything fails open: no key, no budget or no data means neutral values.
"""
from __future__ import annotations

import os
import time

DEFAULT_CASH_RATE = 0.04
BEARISH = -0.25  # AV labels this range "Somewhat-Bearish" or worse
MIN_ARTICLES = 3
MIN_RELEVANCE = 0.3


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def score_feed(feed, symbols):
    """{sym: {"score": -1..1, "n": articles}} as the relevance-weighted mean ticker sentiment."""
    acc = {s: [0.0, 0.0, 0] for s in symbols}
    for item in feed or []:
        for ts in item.get("ticker_sentiment") or []:
            sym = ts.get("ticker")
            rel, val = _f(ts.get("relevance_score")), _f(ts.get("ticker_sentiment_score"))
            if sym in acc and rel is not None and val is not None and rel >= MIN_RELEVANCE:
                acc[sym][0] += rel * val
                acc[sym][1] += rel
                acc[sym][2] += 1
    return {s: {"score": a / w, "n": n} for s, (a, w, n) in acc.items() if w > 0 for n in [acc[s][2]]}


class MarketSignals:
    def __init__(self, av=None, enabled=True, ttl=7200, max_calls_per_day=6, reserve=10):
        self.enabled = enabled and os.getenv("PAPER_NEWS_SIGNAL", "1") not in ("0", "false", "off")
        self.av, self.ttl, self.max_calls, self.reserve = av, ttl, max_calls_per_day, reserve
        self.news, self._at, self._calls, self._day = {}, 0.0, 0, None
        self._rate = None

    def _client(self):
        if self.av is None:
            from .market_apis.alpha_vantage import AlphaVantage
            self.av = AlphaVantage()
        return self.av

    def _budget_ok(self, av):
        today = time.strftime("%Y-%m-%d", time.gmtime())
        if self._day != today:
            self._day, self._calls = today, 0
        return self._calls < self.max_calls and av.used_today() < av.daily_limit - self.reserve

    def refresh(self, symbols):
        """Update sentiment for symbols; at most one batched request per ttl. Never raises."""
        if not self.enabled or not symbols or time.time() - self._at < self.ttl:
            return
        try:
            av = self._client()
            if not av.configured() or not self._budget_ok(av):
                return
            syms = sorted(set(symbols))[:12]
            self._calls += 1
            body = av.call("NEWS_SENTIMENT", ttl=self.ttl, tickers=",".join(syms), sort="LATEST", limit=50)
            self._at = time.time()
            if body and body.get("feed"):
                self.news = score_feed(body["feed"], syms)
        except Exception as exc:
            print("[news] unavailable:", repr(exc), flush=True)

    def sentiment(self, sym):
        r = self.news.get(sym)
        return (r["score"], r["n"]) if r else (0.0, 0)

    def bearish(self, sym):
        score, n = self.sentiment(sym)
        return n >= MIN_ARTICLES and score <= BEARISH

    def cash_rate(self):
        """Latest federal funds rate as a fraction (the absolute-momentum hurdle), else a 4% default."""
        if self._rate is not None:
            return self._rate
        rate = DEFAULT_CASH_RATE
        if self.enabled:
            try:
                av = self._client()
                if av.configured() and self._budget_ok(av):
                    self._calls += 1
                    rows = av.economic("FEDERAL_FUNDS_RATE", interval="monthly")["rows"]
                    v = _f(rows[0]["value"]) if rows else None
                    if v is not None and 0 <= v < 25:
                        rate = v / 100
            except Exception as exc:
                print("[news] cash rate unavailable:", repr(exc), flush=True)
        self._rate = rate
        return rate
