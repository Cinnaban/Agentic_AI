from __future__ import annotations

from ..config import Settings
from .base import DataProvider


def build_provider(s: Settings, symbols: list[str]) -> DataProvider:
    if s.data_provider == "mock":
        from .mock import MockProvider
        return MockProvider(symbols)
    if s.data_provider == "yfinance":
        from .yfinance_provider import YFinanceProvider
        return YFinanceProvider()
    if s.data_provider == "alpaca":
        from .alpaca_provider import AlpacaProvider
        return AlpacaProvider(s.alpaca_key, s.alpaca_secret)
    if s.data_provider == "robinhood":
        from .robinhood_provider import RobinhoodProvider
        return RobinhoodProvider()
    raise ValueError(f"Unknown data provider: {s.data_provider}")
