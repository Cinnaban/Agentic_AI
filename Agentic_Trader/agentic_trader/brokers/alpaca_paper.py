"""Alpaca *paper* account: local ledger plus mirrored orders to paper-api.alpaca.markets."""
from __future__ import annotations

import requests

from .paper import Fill, PaperBroker

PAPER_URL = "https://paper-api.alpaca.markets/v2/orders"  # hard-coded paper endpoint, never live


class AlpacaPaperBroker(PaperBroker):
    name = "alpaca_paper"

    def __init__(self, key: str, secret: str, **kw):
        if not key or not secret:
            raise RuntimeError("ALPACA_API_KEY / ALPACA_API_SECRET are not set")
        super().__init__(**kw)
        self.headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}

    def _mirror(self, fill: Fill) -> None:
        r = requests.post(PAPER_URL, headers=self.headers, timeout=15, json={
            "symbol": fill.symbol, "qty": str(fill.qty), "side": fill.side,
            "type": "market", "time_in_force": "day"})
        if r.status_code >= 300:
            print(f"[alpaca_paper] order rejected: {r.status_code} {r.text[:200]}")
