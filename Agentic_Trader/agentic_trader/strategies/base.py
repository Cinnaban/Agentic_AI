from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Signal:
    symbol: str
    action: str  # buy | sell | hold
    reason: str
    weight: float = 0.0  # target share of total equity for buys
    score: float = 0.0  # model-predicted forward return, if available
