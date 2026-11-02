"""Alpha Vantage client (read-only market data) with shared_storage caching and a request budget.

Key: ALPHA_VANTAGE_API_KEY. The free tier is small (25 requests/day, 5/minute), so every call is cached in
shared_storage (a stale copy is kept as a fallback) and counted against ALPHA_VANTAGE_DAILY_LIMIT /
ALPHA_VANTAGE_PER_MINUTE. When the budget is spent or the API throttles, callers get None and move on.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

URL = "https://www.alphavantage.co/query"
ROOT = Path(__file__).resolve().parents[3]
NS, NS_STALE, NS_BUDGET = "alphavantage", "alphavantage_stale", "alphavantage_budget"

# seconds a cached answer stays fresh
TTL = {"GLOBAL_QUOTE": 300, "OVERVIEW": 86400, "ETF_PROFILE": 86400, "NEWS_SENTIMENT": 1800,
       "CURRENCY_EXCHANGE_RATE": 300, "TOP_GAINERS_LOSERS": 900, "TREASURY_YIELD": 21600, "FEDERAL_FUNDS_RATE": 21600}
DEFAULT_TTL = 43200  # economic series and commodities move slowly
STALE_TTL = 7 * 86400

ECONOMIC = {"REAL_GDP", "REAL_GDP_PER_CAPITA", "TREASURY_YIELD", "FEDERAL_FUNDS_RATE", "CPI", "INFLATION", "RETAIL_SALES",
            "DURABLES", "UNEMPLOYMENT", "NONFARM_PAYROLL"}
COMMODITIES = {"WTI", "BRENT", "NATURAL_GAS", "COPPER", "ALUMINUM", "WHEAT", "CORN", "COTTON", "SUGAR", "COFFEE", "ALL_COMMODITIES"}

_storage_obj: object = False
_lock = threading.Lock()
_recent: list = []
_last_call = [0.0]
MIN_GAP = 1.2  # the free tier throttles bursts faster than 1 request/second


def _storage():
    global _storage_obj
    if _storage_obj is False:
        try:
            if str(ROOT) not in sys.path:
                sys.path.append(str(ROOT))
            from shared_storage.storage_manager import StorageManager
            _storage_obj = StorageManager()
        except Exception:
            _storage_obj = None
    return _storage_obj


def _load_env():
    try:
        from ..config import load_env_files
        load_env_files()
    except Exception:
        pass


class AlphaVantage:
    def __init__(self, key=None):
        _load_env()
        self.key = key or os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
        self.daily_limit = int(os.getenv("ALPHA_VANTAGE_DAILY_LIMIT", "25"))
        self.per_minute = int(os.getenv("ALPHA_VANTAGE_PER_MINUTE", "5"))
        self.last_error = None

    def configured(self):
        return bool(self.key)

    # ---- budget
    def _day_key(self):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def used_today(self):
        disk = _storage()
        if not disk:
            return 0
        try:
            return int(disk.get_cached_data(NS_BUDGET, self._day_key()) or 0)
        except Exception:
            return 0

    def _spend(self):
        """Reserve one request; False when the daily or per-minute budget is exhausted."""
        with _lock:
            now = time.time()
            _recent[:] = [x for x in _recent if now - x < 60]
            if len(_recent) >= self.per_minute:
                self.last_error = "per-minute limit reached"
                return False
            used = self.used_today()
            if used >= self.daily_limit:
                self.last_error = "daily request budget used"
                return False
            wait = MIN_GAP - (now - _last_call[0])
            if wait > 0:
                time.sleep(wait)
            _last_call[0] = time.time()
            _recent.append(_last_call[0])
            disk = _storage()
            if disk:
                try:
                    disk.set_cached_data(NS_BUDGET, self._day_key(), used + 1, 2 * 86400)
                except Exception:
                    pass
            return True

    # a premium-only endpoint is remembered for a day so it never burns the free request budget again
    def _premium_only(self, function):
        try:
            return bool(_storage().get_cached_data(NS_BUDGET, f"premium_{function}"))
        except Exception:
            return False

    def _mark_premium(self, function):
        try:
            _storage().set_cached_data(NS_BUDGET, f"premium_{function}", True, 86400)
        except Exception:
            pass

    # ---- plumbing
    def call(self, function, ttl=None, **params):
        """JSON for one API function, from cache when fresh. None when unavailable (never raises)."""
        if not self.configured():
            self.last_error = "ALPHA_VANTAGE_API_KEY not set"
            return None
        args = {"function": function, **{k: v for k, v in params.items() if v is not None}}
        disk = _storage()
        dkey = disk.build_cache_key(args) if disk else None
        if disk:
            try:
                hit = disk.get_cached_data(NS, dkey)
                if hit is not None:
                    return hit
            except Exception:
                pass
        data = None
        if disk and self._premium_only(function):
            self.last_error = f"{function} needs a premium Alpha Vantage plan"
        elif self._spend():
            try:
                resp = requests.get(URL, params={**args, "apikey": self.key}, timeout=20)
                resp.raise_for_status()
                body = resp.json()
                note = body.get("Note") or body.get("Information") or body.get("Error Message")
                if isinstance(body, dict) and note:
                    self.last_error = str(note)[:160]
                    if "premium" in str(note).lower() and "per day" not in str(note).lower():
                        self._mark_premium(function)
                elif isinstance(body, dict) and body:
                    data = body
            except (requests.RequestException, ValueError) as exc:
                self.last_error = f"{type(exc).__name__}"
        if data is not None and disk:
            try:
                disk.set_cached_data(NS, dkey, data, int(ttl or TTL.get(function, DEFAULT_TTL)))
                disk.set_cached_data(NS_STALE, dkey, data, STALE_TTL)
            except Exception:
                pass
        if data is None and disk:
            try:
                data = disk.get_cached_data(NS_STALE, dkey)
            except Exception:
                data = None
        return data

    # ---- endpoints
    def quote(self, symbol):
        return (self.call("GLOBAL_QUOTE", symbol=symbol) or {}).get("Global Quote") or None

    def overview(self, symbol):
        data = self.call("OVERVIEW", symbol=symbol)
        return data if data and data.get("Symbol") else None

    def etf_profile(self, symbol):
        data = self.call("ETF_PROFILE", symbol=symbol)
        return data if data and (data.get("holdings") or data.get("net_assets")) else None

    def news(self, tickers=None, topics=None, limit=8):
        return (self.call("NEWS_SENTIMENT", tickers=tickers, topics=topics, sort="LATEST", limit=limit) or {}).get("feed") or []

    def fx_rate(self, from_currency, to_currency):
        data = self.call("CURRENCY_EXCHANGE_RATE", from_currency=from_currency, to_currency=to_currency)
        return (data or {}).get("Realtime Currency Exchange Rate")

    def economic(self, function, **kw):
        """Latest observations of an economic series or commodity: [{'date','value'}, ...] newest first."""
        if function not in ECONOMIC | COMMODITIES:
            raise ValueError(f"unsupported series {function}")
        data = self.call(function, interval=kw.get("interval"), maturity=kw.get("maturity"))
        rows = (data or {}).get("data") or []
        return {"name": (data or {}).get("name") or function, "unit": (data or {}).get("unit", ""), "rows": rows[:14]}

    def movers(self):
        return self.call("TOP_GAINERS_LOSERS")

    def summary(self):
        return json.dumps({"configured": self.configured(), "used_today": self.used_today(), "daily_limit": self.daily_limit})
