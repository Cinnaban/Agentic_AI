"""Settings loaded from environment / .env files (project .env, then repo-root .env)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "state"


def load_env_files() -> None:
    """Load KEY=VALUE lines without overriding variables already in the environment."""
    for path in (PROJECT_ROOT / ".env", PROJECT_ROOT.parent / ".env"):
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _csv(name: str, default: str) -> list[str]:
    return [s.strip().upper() for s in os.getenv(name, default).split(",") if s.strip()]


@dataclass
class Settings:
    # Safety: only "paper" is permitted until live trading is deliberately implemented.
    trading_mode: str = "paper"
    data_provider: str = "mock"  # mock | yfinance | alpaca
    broker: str = "paper"  # paper | alpaca_paper | robinhood_mcp (not enabled)
    starting_cash: float = 100_000.0
    etf_allocation_pct: float = 0.70  # share of equity governed by the ETF strategy
    etf_universe: dict[str, float] = field(default_factory=lambda: {
        "VTI": 0.40, "VXUS": 0.15, "QQQ": 0.15, "BND": 0.20, "VNQ": 0.10})
    day_symbols: list[str] = field(default_factory=lambda: ["SPY", "QQQ", "AAPL", "NVDA"])
    hedge_symbol: str = "SH"  # inverse S&P ETF used as a long-only hedge
    max_position_pct: float = 0.10  # per day-trade position, share of total equity
    max_daily_loss_pct: float = 0.02  # day-trader halts after this drawdown
    summary_interval_min: int = 30
    discord_token: str = ""
    discord_realtime_channel: str = ""
    discord_updates_channel: str = ""
    alpaca_key: str = ""
    alpaca_secret: str = ""
    robinhood_mcp_command: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        load_env_files()
        g = os.getenv
        s = cls(
            trading_mode=g("TRADING_MODE", "paper").lower(),
            data_provider=g("TRADER_DATA_PROVIDER", "mock").lower(),
            broker=g("TRADER_BROKER", "paper").lower(),
            starting_cash=float(g("TRADER_STARTING_CASH", "100000")),
            discord_token=g("DISCORD_BOT_TOKEN", ""),
            discord_realtime_channel=g("DISCORD_REALTIMETRADER_CHANNEL_ID", ""),
            discord_updates_channel=g("DISCORD_UPDATES_CHANNEL_ID", ""),
            alpaca_key=g("ALPACA_API_KEY", ""),
            alpaca_secret=g("ALPACA_API_SECRET", ""),
            robinhood_mcp_command=g("ROBINHOOD_MCP_COMMAND", ""),
        )
        s.day_symbols = _csv("TRADER_DAY_SYMBOLS", ",".join(s.day_symbols))
        if s.trading_mode != "paper":
            raise RuntimeError("Only TRADING_MODE=paper is supported; live trading is intentionally disabled.")
        return s
