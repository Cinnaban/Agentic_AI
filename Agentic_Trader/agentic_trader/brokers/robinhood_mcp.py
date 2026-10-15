"""Placeholder for a Robinhood MCP bridge.

Robinhood has no official retail trading API; community MCP servers wrap unofficial endpoints.
This stays disabled until paper trading is proven. To wire it up later:
  1. Run the MCP server of your choice and set ROBINHOOD_MCP_COMMAND in .env.
  2. Implement `_mirror` here by calling the MCP `place_order` tool (via the `mcp` client SDK).
  3. Lift the paper-only guard in config.Settings deliberately and add a human-approval gate.
"""
from __future__ import annotations

from .paper import Fill, PaperBroker


class RobinhoodMCPBroker(PaperBroker):
    name = "robinhood_mcp"

    def __init__(self, command: str, **kw):
        raise NotImplementedError("Robinhood MCP execution is intentionally disabled; use paper/alpaca_paper.")
