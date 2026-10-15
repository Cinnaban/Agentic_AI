import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from data.providers.live.robinhood_backend import RobinhoodBackend


class FakeResearch:
    @staticmethod
    def snapshot(symbols):
        return {symbols[0]: {
            "quote": {"price": 100.0, "change_pct": 0.01, "session": "regular", "as_of": None},
            "consensus": "80% Buy / 20% Hold / 0% Sell (10 analysts)", "next_earnings": "2026-10-20",
            "ratings": {}, "upside_to_target": 0.1}}

    @staticmethod
    def describe(sym, snap):
        return f"{sym} ${snap['quote']['price']}"


def make_backend():
    backend = RobinhoodBackend()
    backend._research = FakeResearch
    return backend


def test_returns_live_quote_result_for_ticker():
    results = make_backend().search({"ticker": "xyz"}, "price now")
    assert results[0]["source_type"] == "live_market"
    assert results[0]["data"]["symbol"] == "XYZ"
    assert results[0]["published_at"] and results[0]["summary"] == "XYZ $100.0"


def test_ignores_requests_without_ticker():
    backend = make_backend()
    assert backend.search({"name": "No Ticker"}, "q") == []
    assert backend.search("not a dict", "q") == []


def test_no_portfolio_or_account_fields_in_result():
    blob = str(make_backend().search({"ticker": "XYZ"}, "q")).lower()
    for word in ("portfolio", "buying_power", "equity_value", "positions", "account"):
        assert word not in blob
