"""Gathers independent evidence (Robinhood market data, Firecrawl/news pages) to cross-check the quant model."""
import re

BULLISH_WORDS = (
    "upgrade", "upgrades", "beat", "beats", "raises", "raised", "record", "surge", "surges", "rally", "rallies",
    "outperform", "buyback", "growth", "strong", "gains", "expands", "profit rises", "tops",
)
BEARISH_WORDS = (
    "downgrade", "downgrades", "miss", "misses", "cuts", "cut", "lawsuit", "layoffs", "decline", "declines",
    "plunge", "plunges", "falls", "probe", "investigation", "warning", "weak", "recall", "slump", "loss",
    "losses", "debt", "underperform",
)
SNIPPET_CHARS = 1500
MAX_WEB_ITEMS = 8


def _ticker(execution_results):
    context = execution_results.get("market_context")
    company = context.get("company") if isinstance(context, dict) else None
    if isinstance(company, dict):
        for key in ("ticker", "symbol"):
            value = company.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().upper()
    return None


def headline_tone(text):
    """+1 / -1 / 0 from the balance of bullish vs bearish words."""
    words = re.findall(r"[a-z']+", str(text or "").lower())
    bull = sum(1 for w in words if w in BULLISH_WORDS)
    bear = sum(1 for w in words if w in BEARISH_WORDS)
    return 1 if bull > bear else -1 if bear > bull else 0


class QuantEvidenceBuilder:
    """Collects cross-reference evidence for a ticker. Every source is best-effort: a failure just omits it."""

    def __init__(self, snapshot_fn=None, live_quant_fn=None, web_fn=None):
        self._snapshot_fn = snapshot_fn or self._default_snapshot
        self._live_quant_fn = live_quant_fn or self._default_live_quant
        self._web_fn = web_fn

    @staticmethod
    def _trader_path():
        import sys
        from pathlib import Path
        path = str(Path(__file__).resolve().parents[1] / "Agentic_Trader")
        if path not in sys.path:
            sys.path.append(path)

    def _default_snapshot(self, symbol):
        self._trader_path()
        from agentic_trader.robinhood import oauth, research
        if not oauth.is_configured():
            return None
        return research.snapshot([symbol]).get(symbol)

    def _default_live_quant(self, symbol):
        self._trader_path()
        from agentic_trader import quant_live
        return quant_live.analyze([symbol]).get(symbol)

    def build(self, execution_results):
        if not isinstance(execution_results, dict):
            return {}
        symbol = _ticker(execution_results)
        if not symbol:
            return {}

        evidence = {"symbol": symbol}
        self._add_robinhood(evidence, symbol)
        self._add_live_quant(evidence, symbol)
        web = self._collect_web(execution_results)
        if web:
            evidence["web"] = web
        return evidence if len(evidence) > 1 else {}

    def _add_robinhood(self, evidence, symbol):
        try:
            snap = self._snapshot_fn(symbol)
        except Exception:
            return
        if not isinstance(snap, dict):
            return
        quote = snap.get("quote") or {}
        if quote.get("price"):
            evidence["price"] = quote["price"]
            evidence["change_pct"] = quote.get("change_pct")
        ratings = snap.get("ratings") or {}
        buy, hold, sell = (ratings.get(k) or 0 for k in ("num_buy_ratings", "num_hold_ratings", "num_sell_ratings"))
        if buy + hold + sell:
            evidence["analysts"] = {"buy": buy, "hold": hold, "sell": sell, "n": buy + hold + sell}
        if snap.get("upside_to_target") is not None:
            evidence["target_upside"] = snap["upside_to_target"]
        if snap.get("next_earnings"):
            evidence["next_earnings"] = snap["next_earnings"]

    def _add_live_quant(self, evidence, symbol):
        try:
            m = self._live_quant_fn(symbol)
        except Exception:
            return
        if not isinstance(m, dict) or "error" in m or m.get("signal_score") is None:
            return
        score = m.get("scorecard") or {}
        evidence["live_quant"] = {
            "signal_score": m.get("signal_score"), "rsi14": m.get("rsi14"), "vwap_dev_pct": m.get("vwap_dev_pct"),
            "realized_vol_ann": m.get("realized_vol_ann"), "beta_vs_spy": m.get("beta_vs_spy"),
            "ic": score.get("ic"), "hit_rate": score.get("hit_rate"),
        }

    def _collect_web(self, execution_results):
        """Firecrawl-scraped pages and news headlines already gathered, else a live-market fetch."""
        context = execution_results.get("market_context")
        context = context if isinstance(context, dict) else {}
        items = self._live_results(context.get("live_market_context"))
        if not any(i.get("via") for i in items) and self._web_fn:
            try:
                items += self._live_results(self._web_fn(context.get("company")))
            except Exception:
                pass
        items += self._news_items(context.get("news"))

        seen, out = set(), []
        for item in items:
            key = item["title"].lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out[:MAX_WEB_ITEMS]

    @staticmethod
    def _live_results(live):
        items = []
        results = live.get("results") if isinstance(live, dict) else None
        for r in results or []:
            if not isinstance(r, dict) or r.get("authoritative") or not r.get("title"):
                continue
            text = " ".join(str(x) for x in (r.get("retrieved_title"), r.get("summary"),
                                             (r.get("content") or "")[:SNIPPET_CHARS]) if x)
            items.append({"title": str(r["title"]), "source": r.get("source") or "web", "text": text,
                          "via": "Firecrawl" if r.get("content_retrieved_by") == "Firecrawl" else None})
        return items

    @staticmethod
    def _news_items(news):
        items = []
        for n in (news if isinstance(news, list) else []):
            if isinstance(n, dict) and n.get("title"):
                items.append({"title": str(n["title"]), "source": n.get("source") or "news",
                              "text": f"{n['title']} {n.get('summary') or ''}", "via": None})
        return items
