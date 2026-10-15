"""Real-time Robinhood market data as a live-market evidence backend (read-only).

Uses Agentic_Trader's shared, market-data-only MCP client. Returns quote, analyst consensus
and earnings timing for a detected ticker. It never reads accounts, positions, portfolio
values or orders; the client refuses every tool outside its market-data allow-list.
"""
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

TRADER_DIR = Path(__file__).resolve().parents[3] / "Agentic_Trader"


class RobinhoodBackend:

    SOURCE = "Robinhood (real-time)"

    def __init__(self):
        self._research = None

    def _load(self):
        if self._research is None:
            if str(TRADER_DIR) not in sys.path:
                sys.path.append(str(TRADER_DIR))
            from agentic_trader.robinhood import oauth, research
            if not oauth.is_configured():
                return None
            self._research = research
        return self._research

    @staticmethod
    def _ticker(company):
        if isinstance(company, dict):
            for key in ("ticker", "symbol"):
                value = company.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip().upper()
        return None

    STOP = {"I", "A", "AI", "ETF", "IPO", "CEO", "CFO", "USA", "US", "EPS", "PE", "GDP", "CPI", "FED", "SEC", "NOW", "RIGHT",
            "TODAY", "HOW", "WHAT", "WHY", "IS", "THE", "AND", "OR", "ARE", "TELL", "ME", "ABOUT", "DOING", "TRADING"}

    def _from_query(self, query, research):
        """Detect a ticker ($NVDA / NVDA) or a company name in free text via Robinhood search."""
        text = str(query or "")
        for tok in re.findall(r"\$?\b([A-Z]{1,5})\b", text):
            if tok not in self.STOP:
                return tok
        for word in re.findall(r"\b([A-Z][a-z]{2,})\b", text):
            if word.lower() in {w.lower() for w in self.STOP}:
                continue
            try:
                for hit in research.shared().search(word, 3):
                    name = (hit.get("simple_name") or hit.get("name") or "").lower()
                    if name.startswith(word.lower()):
                        return hit["symbol"]
            except Exception:
                return None
        return None

    @staticmethod
    def _quant_line(symbol):
        """Compact live-quote quant metrics; also pushes them to the gaming PC in the background."""
        try:
            from agentic_trader import gaming_pc, quant_live
            m = quant_live.analyze([symbol])[symbol]
            threading.Thread(target=gaming_pc.quant, args=([symbol],), daemon=True).start()
            if "error" in m:
                return ""
            sc = m.get("scorecard", {})
            return (f" Quant: signal {m['signal_score']:+.2f}, RSI {m.get('rsi14') or 0:.0f}, "
                    f"VWAP dev {m['vwap_dev_pct']:+.2%}, realized vol {m['realized_vol_ann']:.0%}, "
                    f"beta vs SPY {m.get('beta_vs_spy') or 0:.2f}; walk-forward IC {sc.get('ic', 0):+.2f}, "
                    f"hit rate {sc.get('hit_rate', 0):.0%}.")
        except Exception:
            return ""

    def search(self, company, query):
        research = self._load()
        if research is None:
            return []
        symbol = self._ticker(company) or self._from_query(query, research)
        if not symbol:
            return []
        snap = research.snapshot([symbol]).get(symbol)
        if not snap or not snap["quote"] or not snap["quote"]["price"]:
            return []
        now = datetime.now(timezone.utc).isoformat()
        return [{
            "title": f"{symbol} real-time quote and analyst view (Robinhood)",
            "source": self.SOURCE,
            "summary": research.describe(symbol, snap) + self._quant_line(symbol),
            "published_at": now,
            "source_type": "live_market",
            "authoritative": True,
            "url": f"https://robinhood.com/us/en/stocks/{symbol}/",
            "data": {
                "symbol": symbol,
                "price": snap["quote"]["price"],
                "change_pct": snap["quote"]["change_pct"],
                "session": snap["quote"]["session"],
                "consensus": snap["consensus"],
                "next_earnings": snap["next_earnings"],
            },
        }]
