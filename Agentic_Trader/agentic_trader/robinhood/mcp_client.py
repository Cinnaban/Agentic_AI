"""Minimal read-only MCP (streamable HTTP) client for Robinhood. Order-like tools are refused."""
from __future__ import annotations

import json
import re

import requests

from . import oauth

# Strict allow-list: only public market data / research tools. Account, position, order, watchlist,
# alert, scan-write and option-exercise tools are NOT callable from this client.
SAFE_TOOLS = frozenset({
    "search", "get_equity_quotes", "get_equity_historicals", "get_equity_technical_indicators",
    "get_equity_fundamentals", "get_equity_analyst_ratings", "get_equity_price_book", "get_equity_tradability",
    "get_index_quotes", "get_index_historicals", "get_indexes", "get_earnings_calendar", "get_earnings_results",
    "get_financials", "get_sec_filing_index", "get_sec_filing", "get_sec_filing_facts", "get_sec_filing_facts_catalog",
    "get_option_chains", "get_option_quotes", "get_option_historicals", "get_crypto_quotes", "get_currency_pairs",
})
# Account tools: reachable ONLY through RobinhoodMCP.call_account (used by the Telegram Robinhood handler).
# No options, crypto, margin, transfer, watchlist, alert, scan or exercise tools.
ACCOUNT_READ_TOOLS = frozenset({
    "get_accounts", "get_portfolio", "get_equity_positions", "get_equity_orders",
    "get_trade_approval_setting", "get_trade_approvals",
})
ACCOUNT_ORDER_TOOLS = frozenset({"review_equity_order", "place_equity_order"})
BLOCKED = re.compile(r"order|trade|buy|sell|cancel|place|submit|transfer|withdraw|deposit|execute", re.I)


class ReadOnlyViolation(RuntimeError):
    pass


class RobinhoodMCP:
    def __init__(self, url: str = oauth.MCP_URL, allow: set[str] | None = None):
        self.url, self.allow = url, allow or set()
        self.session_id: str | None = None
        self._id = 0

    def _post(self, method: str, params: dict | None = None, notify: bool = False):
        body = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notify:
            self._id += 1
            body["id"] = self._id
        headers = {"Authorization": f"Bearer {oauth.access_token()}", "Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream"}
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        r = requests.post(self.url, json=body, headers=headers, timeout=30)
        if r.status_code >= 300:
            raise RuntimeError(f"MCP {method} -> {r.status_code}: {r.text[:300]}")
        r.encoding = "utf-8"
        self.session_id = r.headers.get("Mcp-Session-Id", self.session_id)
        if notify or not r.text.strip():
            return None
        if "text/event-stream" in r.headers.get("Content-Type", ""):
            for line in r.text.splitlines():
                if line.startswith("data:"):
                    msg = json.loads(line[5:])
                    if msg.get("id") == body["id"]:
                        return self._result(msg)
            raise RuntimeError("No response in SSE stream")
        return self._result(r.json())

    @staticmethod
    def _result(msg: dict):
        if "error" in msg:
            raise RuntimeError(f"MCP error: {msg['error']}")
        return msg.get("result")

    def initialize(self) -> dict:
        res = self._post("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                        "clientInfo": {"name": "agentic-trader", "version": "0.1"}})
        self._post("notifications/initialized", notify=True)
        return res

    def list_tools(self) -> list[dict]:
        return self._post("tools/list")["tools"]

    def call(self, name: str, arguments: dict | None = None):
        if name not in SAFE_TOOLS:
            raise ReadOnlyViolation(f"Tool '{name}' is not in SAFE_TOOLS (market data only)")
        if name not in self.allow:
            raise ReadOnlyViolation(f"Tool '{name}' is not in the allow-list")
        if BLOCKED.search(name):
            raise ReadOnlyViolation(f"Tool '{name}' looks like a trading/account-changing tool; refused")
        return self._post("tools/call", {"name": name, "arguments": arguments or {}})

    def call_account(self, name: str, arguments: dict | None = None):
        """Account/order tools for the Telegram Robinhood handler only; everything else is refused."""
        if name not in ACCOUNT_READ_TOOLS and name not in ACCOUNT_ORDER_TOOLS:
            raise ReadOnlyViolation(f"Tool '{name}' is not an allowed account tool")
        return self._post("tools/call", {"name": name, "arguments": arguments or {}})
