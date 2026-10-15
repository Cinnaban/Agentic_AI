"""Monospace tables shared by Discord and Telegram replies.

Tables are emitted inside ``` fences: Discord renders them natively; the Telegram sender converts fences to <pre>.
"""
from __future__ import annotations

import html
import re

FENCE = "```"
_FENCED = re.compile(r"```(?:[a-z]*\n)?(.*?)```", re.S)


def table(headers, rows, aligns=None, title=None):
    """Fixed-width table. aligns: string of 'l'/'r' per column (default: first left, rest right)."""
    rows = [["" if c is None else str(c) for c in r] for r in rows]
    n = len(headers)
    aligns = aligns or "l" + "r" * (n - 1)
    widths = [max(len(str(h)), *(len(r[i]) for r in rows)) if rows else len(str(h)) for i, h in enumerate(headers)]

    def line(cells):
        return " ".join(c.ljust(w) if a == "l" else c.rjust(w) for c, w, a in zip(cells, widths, aligns)).rstrip()

    out = [line([str(h) for h in headers]), " ".join("-" * w for w in widths)] + [line(r) for r in rows]
    body = f"{FENCE}\n" + "\n".join(out) + f"\n{FENCE}"
    return (f"{title}\n" if title else "") + body


def kv_table(pairs, title=None, headers=("Metric", "Value")):
    return table(list(headers), [[k, v] for k, v in pairs if v is not None], aligns="ll", title=title)


def split_message(text, max_length):
    """Split on blank lines, never inside a ``` fence; hard-cut only a single oversized block."""
    blocks, cur, in_fence = [], [], False
    for ln in text.split("\n"):
        cur.append(ln)
        if ln.strip().startswith(FENCE):
            in_fence = not in_fence
        if not in_fence and not ln.strip():
            blocks.append("\n".join(cur))
            cur = []
    if cur:
        blocks.append("\n".join(cur))
    parts, buf = [], ""
    for b in blocks:
        if len(b) > max_length:
            if buf.strip():
                parts.append(buf.strip())
                buf = ""
            fenced = b.strip().startswith(FENCE)
            lines, chunk = b.strip().split("\n"), ""
            head = lines[0] if fenced else ""
            for ln in lines[1:] if fenced else lines:
                if len(chunk) + len(ln) + 12 > max_length and chunk:
                    parts.append((chunk + (FENCE if fenced else "")).strip())
                    chunk = (head + "\n") if fenced else ""
                chunk += ln[:max_length - 12] + "\n"
            if chunk.strip():
                parts.append(chunk.strip())
            continue
        if len(buf) + len(b) + 1 > max_length and buf.strip():
            parts.append(buf.strip())
            buf = ""
        buf += b + "\n"
    if buf.strip():
        parts.append(buf.strip())
    return parts


def to_telegram_html(text):
    """Escape everything, turn ``` fences into <pre> blocks."""
    out, pos = [], 0
    for m in _FENCED.finditer(text):
        out.append(html.escape(text[pos:m.start()]))
        out.append("<pre>" + html.escape(m.group(1).strip("\n")) + "</pre>")
        pos = m.end()
    out.append(html.escape(text[pos:]))
    return "".join(out)


def holdings_tables(holdings, top=30):
    """Portfolio composition tables from parsed holdings [{ticker, weight, entity_type, sector}]."""
    if not any(isinstance(h, dict) and h.get("ticker") for h in holdings):
        return ""
    rows = []
    for h in sorted((h for h in holdings if isinstance(h, dict)), key=lambda h: -(h.get("weight") or 0))[:top]:
        w = h.get("weight")
        rows.append([h.get("ticker", ""), f"{w:.1f}%" if isinstance(w, (int, float)) else "n/a",
                     {"stock": "Stock", "etf": "ETF"}.get(h.get("entity_type"), "?"),
                     str(h.get("sector") or "-")[:22]])
    out = [table(["Ticker", "Weight", "Type", "Sector"], rows, aligns="lrll", title="Holdings")]
    by = {}
    for h in holdings:
        if isinstance(h, dict) and isinstance(h.get("weight"), (int, float)):
            k = h.get("sector") or ("ETF" if h.get("entity_type") == "etf" else "Unclassified")
            by[k] = by.get(k, 0.0) + h["weight"]
    if by:
        tot = sum(by.values())
        out.append(table(["Sector", "Weight", "Names"],
                         [[k[:24], f"{v:.1f}%", sum(1 for h in holdings if (h.get("sector") or ("ETF" if h.get("entity_type") == "etf" else "Unclassified")) == k)]
                          for k, v in sorted(by.items(), key=lambda kv: -kv[1])], aligns="lrr",
                         title=f"By sector (total {tot:.1f}%)"))
    return "\n\n".join(out)
