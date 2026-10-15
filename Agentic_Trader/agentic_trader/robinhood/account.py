"""Robinhood account access for the Telegram handler ONLY (never imported by Discord or the market-data path).

Reads are scoped by ROBINHOOD_ANALYSIS_ACCOUNTS ("agentic" = the MCP account only, default; "all" = every account,
read-only). Orders can only ever target the single agentic_allowed account, resolved from get_accounts at call time.
"""
from __future__ import annotations

import json
import os
import threading

from .mcp_client import RobinhoodMCP

_lock = threading.Lock()
_client: RobinhoodMCP | None = None


def _call(name: str, args: dict | None = None) -> dict:
    global _client
    with _lock:
        for attempt in (0, 1):
            try:
                if _client is None:
                    _client = RobinhoodMCP()
                    _client.initialize()
                res = _client.call_account(name, args or {})
                break
            except RuntimeError:
                _client = None
                if attempt:
                    raise
    text = res["content"][0].get("text", "")
    if res.get("isError"):
        raise RuntimeError(f"{name}: {text[:300]}")
    return json.loads(text)


def accounts() -> list[dict]:
    return _call("get_accounts")["data"]["accounts"]


def agentic_account() -> dict:
    found = [a for a in accounts() if a.get("agentic_allowed") and a.get("state") == "active"]
    if len(found) != 1:
        raise RuntimeError(f"Expected exactly one agentic account, found {len(found)}")
    return found[0]


def analysis_accounts() -> list[dict]:
    if os.getenv("ROBINHOOD_ANALYSIS_ACCOUNTS", "agentic").strip().lower() == "all":
        return [a for a in accounts() if a.get("state") == "active"]
    return [agentic_account()]


def label(acct: dict) -> str:
    return acct.get("nickname") or acct.get("brokerage_account_type") or "account"


def portfolio(acct_no: str) -> dict:
    return _call("get_portfolio", {"account_number": acct_no})["data"]


def positions(acct_no: str) -> list[dict]:
    out, cursor = [], None
    for _ in range(10):
        args = {"account_number": acct_no, **({"cursor": cursor} if cursor else {})}
        data = _call("get_equity_positions", args)["data"]
        out += data.get("positions", [])
        cursor = data.get("next")
        if not cursor:
            break
    return out


def open_orders(acct_no: str) -> list[dict]:
    return _call("get_equity_orders", {"account_number": acct_no}).get("data", {}).get("orders", [])


def approval_required(acct_no: str) -> bool:
    return bool(_call("get_trade_approval_setting", {"account_number": acct_no})["data"]["setting"]["human_must_approve_trades"])


def review_order(args: dict) -> dict:
    return _call("review_equity_order", args)["data"]


def place_order(args: dict) -> dict:
    return _call("place_equity_order", args)

