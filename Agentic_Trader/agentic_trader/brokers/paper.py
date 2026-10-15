"""Local paper broker with a per-sleeve ledger ('etf' vs 'day') persisted to JSON."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from ..config import STATE_DIR


@dataclass
class Fill:
    ts: str
    sleeve: str
    symbol: str
    side: str
    qty: float
    price: float
    reason: str = ""

    @property
    def notional(self) -> float:
        return self.qty * self.price


class PaperBroker:
    name = "paper"
    SLIPPAGE_BPS = 2.0

    def __init__(self, starting_cash: float = 100_000.0, state_file: Path | None = None, persist: bool = True):
        self.state_file = state_file or STATE_DIR / "paper_account.json"
        self.persist = persist
        self.cash = starting_cash
        self.positions: dict[str, dict[str, dict]] = {"etf": {}, "day": {}}  # sleeve -> sym -> {qty, avg}
        self.fills: list[Fill] = []
        self.realized: dict[str, float] = {"etf": 0.0, "day": 0.0}
        if persist and self.state_file.exists():
            self._load()

    # ---- state ----
    def _load(self) -> None:
        d = json.loads(self.state_file.read_text())
        self.cash, self.positions, self.realized = d["cash"], d["positions"], d["realized"]
        self.fills = [Fill(**f) for f in d["fills"]]

    def save(self) -> None:
        if not self.persist:
            return
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps({
            "cash": self.cash, "positions": self.positions, "realized": self.realized,
            "fills": [asdict(f) for f in self.fills]}, indent=1))

    # ---- queries ----
    def qty(self, sleeve: str, symbol: str) -> float:
        return self.positions[sleeve].get(symbol, {}).get("qty", 0.0)

    def sleeve_value(self, sleeve: str, prices: dict[str, float]) -> float:
        return sum(p["qty"] * prices.get(s, p["avg"]) for s, p in self.positions[sleeve].items())

    def equity(self, prices: dict[str, float]) -> float:
        return self.cash + sum(self.sleeve_value(sl, prices) for sl in self.positions)

    # ---- trading ----
    def submit_order(self, sleeve: str, symbol: str, side: str, qty: float, price: float, ts: str, reason: str = "") -> Fill | None:
        if qty <= 0:
            return None
        slip = price * self.SLIPPAGE_BPS / 1e4
        px = price + slip if side == "buy" else price - slip
        pos = self.positions[sleeve].setdefault(symbol, {"qty": 0.0, "avg": 0.0})
        if side == "buy":
            qty = min(qty, self.cash / px)  # never go negative on cash (no margin)
            if qty <= 0:
                return None
            pos["avg"] = (pos["avg"] * pos["qty"] + px * qty) / (pos["qty"] + qty)
            pos["qty"] += qty
            self.cash -= qty * px
        else:
            qty = min(qty, pos["qty"])  # long-only: no shorting
            if qty <= 0:
                return None
            self.realized[sleeve] += (px - pos["avg"]) * qty
            pos["qty"] -= qty
            self.cash += qty * px
            if pos["qty"] < 1e-9:
                del self.positions[sleeve][symbol]
        fill = Fill(ts, sleeve, symbol, side, qty, px, reason)
        self.fills.append(fill)
        self._mirror(fill)
        self.save()
        return fill

    def _mirror(self, fill: Fill) -> None:
        """Hook for brokers that also route the order to an external paper venue."""
