"""Long-term ETF sleeve: strategic weights, 200-day trend filter, drift-band monthly rebalance."""
from __future__ import annotations

import pandas as pd

DEFENSIVE = "BND"


class ETFCoreStrategy:
    name = "etf"

    def __init__(self, universe: dict[str, float], drift_band: float = 0.02, trend_filter: bool = True):
        self.universe = universe
        self.drift_band = drift_band
        self.trend_filter = trend_filter

    def target_weights(self, daily: dict[str, pd.DataFrame]) -> dict[str, float]:
        """Weights sum to 1 within the sleeve. Risk assets below their 200d SMA are halved
        and the freed weight rotates to the defensive ETF."""
        w = dict(self.universe)
        if self.trend_filter:
            for sym, base in self.universe.items():
                if sym == DEFENSIVE or sym not in daily or len(daily[sym]) < 200:
                    continue
                c = daily[sym]["close"]
                if c.iloc[-1] < c.rolling(200).mean().iloc[-1]:
                    w[sym] = base * 0.5
                    w[DEFENSIVE] = w.get(DEFENSIVE, 0.0) + base * 0.5
        total = sum(w.values())
        return {k: v / total for k, v in w.items()}

    def orders(self, targets: dict[str, float], sleeve_equity: float, prices: dict[str, float],
               held_qty: dict[str, float]) -> list[tuple[str, str, float, str]]:
        """Return (symbol, side, qty, reason); sells first so cash is available for buys."""
        sells, buys = [], []
        for sym in set(targets) | set(held_qty):
            px = prices[sym]
            cur = held_qty.get(sym, 0.0) * px / sleeve_equity if sleeve_equity else 0.0
            diff = targets.get(sym, 0.0) - cur
            if abs(diff) < self.drift_band:
                continue
            qty = abs(diff) * sleeve_equity / px
            reason = f"rebalance {cur:.1%} -> {targets.get(sym, 0.0):.1%}"
            (buys if diff > 0 else sells).append((sym, "buy" if diff > 0 else "sell", qty, reason))
        return sells + buys
