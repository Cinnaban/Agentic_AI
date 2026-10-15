"""Push live-quote data to the gaming PC quant worker (root GamingPCBridge config), falling back to local compute."""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import requests

from . import quant_live

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))


def _cfg():
    try:
        from configs.config import Config
        return Config.GAMING_PC_HEALTH_URL, Config.GAMING_PC_COMPUTE_URL, Config.GAMING_PC_TIMEOUT
    except Exception:
        return None, None, 0


def online(timeout: float = 3.0) -> bool:
    health, _, _ = _cfg()
    if not health:
        return False
    try:
        s = requests.Session()
        s.trust_env = False
        return s.get(health, timeout=timeout).json().get("status") == "online"
    except Exception:
        return False


def quant(symbols: list[str], data=None) -> dict:
    """Compute live metrics locally, then push them (with the live quotes) to the gaming PC.

    Returns {"local": {...}, "gaming_pc": {"status": ..., "results": [...]}}. Local metrics are always returned.
    """
    local = quant_live.analyze(symbols, data=data)
    out = {"local": local, "gaming_pc": {"status": "offline"}}
    if not online():
        return out
    _, url, timeout = _cfg()
    payload = {
        "job_id": f"rh-live-{uuid.uuid4().hex[:8]}",
        "companies": [{"name": s, "ticker": s} for s in local if "error" not in local[s]],
        "original_message": "live quote quant refresh",
        "requested_tasks": ["quant"],
        "source": "agentic_trader",
        "live_data": {s: {k: v for k, v in m.items() if k != "scorecard"} for s, m in local.items() if "error" not in m},
    }
    try:
        s = requests.Session()
        s.trust_env = False
        r = s.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        body = r.json()
        out["gaming_pc"] = {"status": "completed" if body.get("results") else "empty",
                            "results": body.get("results", []), "error": body.get("error")}
    except Exception as exc:
        out["gaming_pc"] = {"status": "error", "error": str(exc)[:200]}
    return out
