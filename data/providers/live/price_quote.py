"""Deterministic answer for price/quote questions: real-time Robinhood quote first, scraped sources below.

No LLM is involved, so a scraped (stale) price can never replace the live quote. Market data only.
"""
import re

PRICE_INTENT = re.compile(
    r"\b(price|quote|quotes|trading|trades|stock at|share price|how is .+ doing|how's .+ doing)\b", re.I
)
EXCLUDE = re.compile(r"\b(forecast|predict|prediction|target|revenue|earnings|why|explain|compare|vs|versus|analy[sz]e)\b", re.I)


def is_price_question(message):
    text = str(message or "")
    return bool(PRICE_INTENT.search(text)) and not EXCLUDE.search(text) and len(text) < 120


def answer(message, provider):
    """Return response text, or None when this isn't a price question or no live quote is available."""
    if not is_price_question(message):
        return None
    backend = next((b for b in provider.backends if getattr(b, "SOURCE", "") == "Robinhood (real-time)"), None)
    research = backend._load() if backend else None
    if research is None:
        return None
    symbol = backend._from_query(message, research)
    if not symbol:
        return None
    context = provider.get_context(company={"name": symbol, "ticker": symbol}, query=str(message))
    results = context.get("results", []) if isinstance(context, dict) else []
    live = next((r for r in results if r.get("authoritative")), None)
    if not live:
        return None
    others = [r for r in results if not r.get("authoritative")][:5]
    lines = [f"Live quote (Robinhood, real-time):", live["summary"]]
    if others:
        lines += ["", "Scrape summary (web sources, may be delayed; the live quote above takes priority):"]
        for r in others:
            snippet = " ".join(str(r.get("summary") or "").split())[:160]
            lines.append(f"- {r.get('source')}: {r.get('title')}" + (f" - {snippet}" if snippet else ""))
        lines.append("")
        lines.append("Sources:")
        lines.append(f"- [Live] Robinhood MCP: {live.get('url')}")
        for i, r in enumerate(others, 1):
            if r.get("url"):
                lines.append(f"- [S{i}] {r.get('source')}: <{r['url']}>")
    return "\n".join(lines)
