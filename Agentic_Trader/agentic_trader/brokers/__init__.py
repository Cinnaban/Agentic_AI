from __future__ import annotations

from ..config import Settings
from .paper import Fill, PaperBroker


def build_broker(s: Settings, persist: bool = True) -> PaperBroker:
    if s.broker == "paper":
        return PaperBroker(s.starting_cash, persist=persist)
    if s.broker == "alpaca_paper":
        from .alpaca_paper import AlpacaPaperBroker
        return AlpacaPaperBroker(s.alpaca_key, s.alpaca_secret, starting_cash=s.starting_cash, persist=persist)
    if s.broker == "robinhood_mcp":
        from .robinhood_mcp import RobinhoodMCPBroker
        return RobinhoodMCPBroker(s.robinhood_mcp_command)
    raise ValueError(f"Unknown broker: {s.broker}")
