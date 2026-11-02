"""World Bank Open Data client (no API key): country economic, demographic and governance indicators.

Responses are cached in shared_storage (indicators for a day, the country list for 30 days); failures return None.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import requests

BASE = "https://api.worldbank.org/v2"
ROOT = Path(__file__).resolve().parents[3]
NS = "worldbank"
TTL, COUNTRY_TTL = 86400, 30 * 86400
CODE = re.compile(r"^[A-Za-z0-9._]{2,30}$")

_storage_obj: object = False


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


class WorldBank:
    def __init__(self, timeout=15):
        self.timeout = timeout
        self.last_error = None

    def _get(self, path, **params):
        resp = requests.get(f"{BASE}/{path}", params={"format": "json", **params}, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _cached(self, key, ttl, fn):
        disk = _storage()
        dkey = disk.build_cache_key(key) if disk else None
        if disk:
            try:
                hit = disk.get_cached_data(NS, dkey)
                if hit is not None:
                    return hit
            except Exception:
                pass
        try:
            value = fn()
        except Exception as exc:
            self.last_error = repr(exc)
            return None
        if value is not None and disk:
            try:
                disk.set_cached_data(NS, dkey, value, ttl)
            except Exception:
                pass
        return value

    def countries(self):
        """{iso2: name} for real countries (aggregates such as 'World' are excluded)."""
        def load():
            data = self._get("country", per_page=400)
            return {c["iso2Code"]: c["name"] for c in data[1] if c.get("region", {}).get("value") != "Aggregates"}
        return self._cached(("countries",), COUNTRY_TTL, load) or {}

    def indicator(self, country, code, years=6):
        """Latest values, newest first: {'name','country','rows':[{'date','value'}]} or None."""
        if not CODE.match(country or "") or not CODE.match(code or ""):
            raise ValueError("bad country or indicator code")

        def load():
            data = self._get(f"country/{country}/indicator/{code}", mrv=years)
            rows = [{"date": r["date"], "value": r["value"]} for r in (data[1] or []) if r.get("value") is not None]
            if not rows:
                return None
            first = data[1][0]
            return {"name": first["indicator"]["value"], "country": first["country"]["value"], "rows": rows}
        return self._cached(("indicator", country, code, years), TTL, load)
