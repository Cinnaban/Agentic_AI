"""High-level, read-only Robinhood market data (plain dicts, no pandas). Shared by the trader and the root project.

Only calls tools in mcp_client.SAFE_TOOLS. Never touches accounts, positions, portfolio or orders.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .mcp_client import SAFE_TOOLS, RobinhoodMCP

QUOTE_TTL, BARS_TTL, RESEARCH_TTL = 5.0, 20.0, 600.0
STALE_TTL = 24 * 3600  # last-known-good copy used only if the MCP call fails
ROOT = Path(__file__).resolve().parents[3]


def _storage():
    """Root shared_storage StorageManager (market data only), or None if unavailable."""
    global _STORAGE
    if _STORAGE is False:
        try:
            if str(ROOT) not in sys.path:
                sys.path.append(str(ROOT))
            from shared_storage.storage_manager import StorageManager
            _STORAGE = StorageManager()
        except Exception:
            _STORAGE = None
    return _STORAGE


_STORAGE: object = False


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


class RobinhoodData:
    def __init__(self):
        self._client: RobinhoodMCP | None = None
        self._cache: dict = {}
        self._lock = threading.Lock()

    # ---- plumbing ----
    def _call(self, tool: str, args: dict, ttl: float):
        key = (tool, json.dumps(args, sort_keys=True))
        with self._lock:
            hit = self._cache.get(key)
            if hit and time.time() - hit[0] < ttl:
                return hit[1]
            disk = _storage()
            dkey = disk.build_cache_key({"tool": tool, "args": args}) if disk else None
            if disk:
                try:
                    cached = disk.get_cached_data("robinhood_market", dkey)
                    if cached is not None:
                        self._cache[key] = (time.time(), cached)
                        return cached
                except Exception:
                    pass
            try:
                data = self._fetch(tool, args)
            except Exception:
                stale = None
                if disk:
                    try:
                        stale = disk.get_cached_data("robinhood_stale", dkey)
                    except Exception:
                        pass
                if stale is None:
                    raise
                return stale
            self._cache[key] = (time.time(), data)
            if disk:
                try:
                    disk.set_cached_data("robinhood_market", dkey, data, max(1, int(ttl)))
                    disk.set_cached_data("robinhood_stale", dkey, data, STALE_TTL)
                except Exception:
                    pass
            return data

    def _fetch(self, tool: str, args: dict):
        for attempt in (0, 1):  # one reconnect if the MCP session expired
            try:
                if self._client is None:
                    self._client = RobinhoodMCP(allow=set(SAFE_TOOLS))
                    self._client.initialize()
                res = self._client.call(tool, args)
                break
            except RuntimeError as exc:
                self._client = None
                if attempt or "not in" in str(exc) or "Not signed in" in str(exc):
                    raise
        if res.get("isError"):
            raise RuntimeError(f"{tool}: {res['content'][0].get('text', '')[:200]}")
        return json.loads(res["content"][0]["text"]).get("data", {})

    # ---- quotes ----
    def quotes(self, symbols: list[str]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        syms = [s.upper() for s in symbols]
        for i in range(0, len(syms), 20):
            for r in self._call("get_equity_quotes", {"symbols": syms[i:i + 20]}, QUOTE_TTL).get("results", []):
                q = r.get("quote") or {}
                if not q.get("symbol"):
                    continue
                cands = [(_ts(q.get("venue_last_trade_time")), _f(q.get("last_trade_price")), "regular"),
                         (_ts(q.get("venue_last_non_reg_trade_time")), _f(q.get("last_non_reg_trade_price")), "extended")]
                cands = [c for c in cands if c[0] and c[1]]
                as_of, price, session = max(cands, key=lambda c: c[0]) if cands else (None, None, "none")
                prev = _f(q.get("adjusted_previous_close")) or _f(q.get("previous_close"))
                out[q["symbol"]] = {
                    "symbol": q["symbol"], "price": price, "session": session, "as_of": as_of,
                    "prev_close": prev, "change_pct": (price / prev - 1) if price and prev else None,
                    "bid": _f(q.get("bid_price")), "ask": _f(q.get("ask_price")), "state": q.get("state")}
        return out

    # ---- bars ----
    def bars(self, symbols: list[str], interval: str = "minute", days_back: float = 5, bounds: str = "regular") -> dict[str, list[dict]]:
        """interval per Robinhood: minute, 5minute, 10minute, 30minute, hour, day, ..."""
        start = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
        out: dict[str, list[dict]] = {}
        syms = [s.upper() for s in symbols]
        for i in range(0, len(syms), 10):
            data = self._call("get_equity_historicals", {"symbols": syms[i:i + 10], "start_time": start,
                                                         "interval": interval, "bounds": bounds}, BARS_TTL)
            for r in data.get("results", []):
                out[r["symbol"]] = [{"ts": _ts(b["begins_at"]), "open": _f(b["open_price"]), "high": _f(b["high_price"]),
                                     "low": _f(b["low_price"]), "close": _f(b["close_price"]), "volume": b.get("volume") or 0}
                                    for b in r.get("bars", []) if not b.get("interpolated")]
        return out

    # ---- research ----
    def ratings(self, symbols: list[str]) -> dict[str, dict | None]:
        syms = [s.upper() for s in symbols]
        data = self._call("get_equity_analyst_ratings", {"symbols": syms}, RESEARCH_TTL)
        return {s: (r or {}).get("ratings") for s, r in zip(syms, data.get("results", []))}

    def earnings(self, days: int = 7, high_cap_only: bool = False) -> list[dict]:
        args = {"days": days}
        if high_cap_only:
            args["filter"] = "high_market_cap"
        return self._call("get_earnings_calendar", args, RESEARCH_TTL).get("results", [])

    def search(self, query: str, limit: int = 5) -> list[dict]:
        return self._call("search", {"query": query, "limit": limit}, RESEARCH_TTL).get("results", [])

    def sec_filings(self, symbol: str, forms: list[str] | None = None, since: str | None = None) -> list[dict]:
        args: dict = {"symbol": symbol.upper()}
        if forms:
            args["form_type"] = forms
        if since:
            args["since"] = since
        data = self._call("get_sec_filing_index", args, RESEARCH_TTL)
        return data.get("filings") or data.get("results", [])


_shared: RobinhoodData | None = None


def shared() -> RobinhoodData:
    global _shared
    if _shared is None:
        _shared = RobinhoodData()
    return _shared
