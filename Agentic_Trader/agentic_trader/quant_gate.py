"""Pre-trade quant gate. Before a day, options or long-hold entry the agents ask for the quant suite on the candidate.

The suite runs on the Gaming PC quant worker (`python -m agentic_trader.quant_worker`, optional CuPy) when it answers
its health check, and locally otherwise. Results are cached per mode, persisted to state/quant_suite.json (read by the
Grafana export) and fail open: if bars or compute are unavailable the agents trade on their own rules, and say so.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from . import quant_suite
from .config import PROJECT_ROOT, STATE_DIR

ROOT = PROJECT_ROOT.parent
SPEC = {  # mode -> (bars interval, days back, horizon, cache seconds)
    "day": ("5minute", 7, 1, 1800),
    "options": ("day", 400, 1, 6 * 3600),
    "long": ("day", 400, 1, 6 * 3600),
}
OUT = STATE_DIR / "quant_suite.json"
WORKER_PORT = 8011


def _remote_url():
    url = os.getenv("TRADER_QUANT_URL", "").strip()
    if url:
        return url.rstrip("/")
    try:
        if str(ROOT) not in sys.path:
            sys.path.append(str(ROOT))
        from configs.config import Config
        return f"http://{Config.GAMING_PC_HOST}:{WORKER_PORT}"
    except Exception:
        return None


class QuantGate:
    def __init__(self, data, enabled=True, remote=True, path=OUT):
        self.data, self.enabled, self.use_remote, self.path = data, enabled, remote, path
        self.cache = {}  # (mode, symbol) -> (epoch, result)
        self._online = (0.0, False)
        self.last_where = "local"
        self.last_error = None

    # ---- compute location
    def _worker(self):
        if not self.use_remote:
            return None
        url = _remote_url()
        if not url:
            return None
        ts, ok = self._online
        if time.time() - ts < 60:
            return url if ok else None
        try:
            s = requests.Session()
            s.trust_env = False
            ok = s.get(url + "/health", timeout=2).json().get("status") == "online"
        except Exception:
            ok = False
        self._online = (time.time(), ok)
        return url if ok else None

    def _remote(self, url, mode, interval, h, bars):
        s = requests.Session()
        s.trust_env = False
        headers = {"X-Quant-Token": os.getenv("TRADER_QUANT_TOKEN", "")}
        body = {"mode": mode, "interval": interval, "horizon": h, "bars": {
            sym: [{k: b.get(k) for k in ("close", "volume")} for b in rows] for sym, rows in bars.items()}}
        r = s.post(url + "/suite", json=body, headers=headers, timeout=120)
        r.raise_for_status()
        return r.json()["results"]

    # ---- public
    def get(self, sym, mode):
        hit = self.cache.get((mode, sym))
        return hit[1] if hit else None

    def ensure(self, symbols, mode):
        """Compute the suite for symbols that are missing or stale. Never raises."""
        if not self.enabled:
            return
        interval, days, h, ttl = SPEC[mode]
        now = time.time()
        todo = [s for s in dict.fromkeys(symbols) if now - (self.cache.get((mode, s), (0, 0))[0]) > ttl]
        if not todo:
            return
        try:
            bars = self.data.bars(todo, interval, days, ttl=ttl // 2)
            bars = {s: b for s, b in (bars or {}).items() if b}
            if not bars:
                return
            results, where = None, "local"
            url = self._worker()
            if url:
                try:
                    results, where = self._remote(url, mode, interval, h, bars), "gaming_pc"
                except Exception as exc:
                    self.last_error = f"gaming PC quant worker failed ({exc!r}); computed locally"
                    self._online = (time.time(), False)
            if results is None:
                results = {s: quant_suite.analyze(b, interval, h, mode) for s, b in bars.items()}
            self.last_where = where
            for s, res in results.items():
                res["where"] = where
                res["ts"] = datetime.now(timezone.utc).isoformat()
                self.cache[(mode, s)] = (now, res)
            self._save()
        except Exception as exc:
            self.last_error = repr(exc)
            print("[quant] suite unavailable:", self.last_error, flush=True)

    def verdict(self, sym, mode):
        """(veto, score, size_mult, note) with neutral defaults when the suite has nothing for the symbol."""
        r = self.get(sym, mode)
        if not r or "error" in r:
            return False, 0.0, 1.0, ""
        edge = "edge" if r["edge"] else "no OOS edge"
        return r["veto"], r["score"], r["size_mult"], f"quant {r['score']:+.2f} ({edge}, size x{r['size_mult']:.2f})"

    def account(self, state):
        return quant_suite.account_performance(state.get("equity_log") or [], state.get("trades") or [])

    def lines(self, state=None):
        rows = [(m, s, r) for (m, s), (_, r) in self.cache.items() if "error" not in r]
        if not rows and not state:
            return []
        out = []
        if rows:
            where = rows[0][2].get("where", "local")
            vetoed = sorted(f"{s}({m})" for m, s, r in rows if r["veto"])
            out.append(f"- Quant gate ({'Gaming PC' if where == 'gaming_pc' else 'local compute'}): {len(rows)} scored, "
                       f"{len(vetoed)} vetoed" + (f": {', '.join(vetoed[:6])}" if vetoed else ""))
        if state:
            a = self.account(state)
            if a.get("n"):
                f = lambda x, p="%.2f": "n/a" if x is None else p % x
                out.append(f"- Account quality: Sharpe {f(a.get('sharpe'))}, Sortino {f(a.get('sortino'))}, "
                           f"Max DD {a['max_dd']:.1%}, Profit factor {f(a.get('trade_profit_factor'))} "
                           f"({a.get('closed_trades', 0)} closed trades)")
        return out

    def _save(self):
        try:
            payload = {"ts": datetime.now(timezone.utc).isoformat(),
                       "symbols": {f"{m}:{s}": r for (m, s), (_, r) in self.cache.items()}}
            tmp = Path(str(self.path) + ".tmp")
            tmp.write_text(json.dumps(payload, default=float))
            os.replace(tmp, self.path)
        except Exception as exc:
            print("[quant] could not persist suite:", repr(exc), flush=True)
