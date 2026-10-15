# Agentic_Trader

Paper-trading agentic stock bot with two sleeves:

| Sleeve | Goal | Logic |
|---|---|---|
| **ETF core** (`strategies/etf_core.py`) | long-term growth | strategic weights (VTI/VXUS/QQQ/BND/VNQ), 200-day SMA trend filter rotates weak risk assets into BND, monthly rebalance with a 2% drift band |
| **Day trader** (`strategies/day_trader.py`) | daily profit / hedge | EMA 9/21 cross + VWAP + RSI filter, ATR stop, flatten at 15:55 ET, 2% daily loss halt, SPY-down → inverse ETF (`SH`) hedge |

## Layout
```
agentic_trader/
  config.py        settings (.env: project, then repo root)
  data/            mock (default), yfinance, alpaca providers
  brokers/         paper (local ledger), alpaca_paper (mirrors to Alpaca paper), robinhood_mcp (disabled stub)
  indicators.py    SMA/EMA/RSI/MACD/Bollinger/ATR/VWAP
  compute.py       NumPy/CuPy backend: MA-crossover grid sweep + ridge regression (GPU on the gaming PC)
  features.py      regression features
  improve.py       improvement loop
  engine.py        tick loop, risk, scheduling, Discord reporting
  notify/discord.py, reporting.py
```

## Quick start
```bash
cd Agentic_Trader
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python -m agentic_trader simulate            # replay a mock session (posts to Discord if token is set)
python -m agentic_trader simulate --shock -0.02   # inject a SPY drop to exercise hedge + Discord alerts
python -m agentic_trader improve [--dry-run]
python -m agentic_trader discord-test
python -m agentic_trader status
pytest
```
Mock sessions are tagged `🧪 [MOCK DATA]` in Discord. With no `DISCORD_BOT_TOKEN`, messages go to `state/discord_outbox.log`.

## Discord
- `DISCORD_REALTIMETRADER_CHANNEL_ID`: half-hour day-trader summary (moves, trades, open positions, P&L).
- `DISCORD_UPDATES_CHANNEL_ID`: end-of-market-close daily summary.
Uses the same `DISCORD_BOT_TOKEN` as the root project (bot needs Send Messages in both channels).

## Going beyond mock data
Set in `.env`: `TRADER_DATA_PROVIDER=yfinance` (free, delayed) or `alpaca` (+ `ALPACA_API_KEY/SECRET`, free IEX feed);
`TRADER_BROKER=alpaca_paper` mirrors orders to an Alpaca paper account. Then `python -m agentic_trader run` for the wall-clock loop
(run under launchd/cron like the other repo jobs). Scraped/archived data can be added as another `DataProvider`.

## Robinhood MCP (read-only market data + research)
`python -m agentic_trader rh-login --manual` (once), then `rh-tools`, `rh-research SPY NVDA`.
- Tokens are stored in `Agentic_Trader/.env` (gitignored); refresh is file-locked so the bots and trader can share them.
- `robinhood/mcp_client.py` only calls a fixed market-data allow-list (`SAFE_TOOLS`): quotes, bars, indicators, fundamentals,
  analyst ratings, earnings, SEC filings, search. Orders, positions, portfolio, balances, watchlists and alerts are refused.
  Portfolio values are never read; only your own paper-ledger percentages appear in reports.
- `TRADER_DATA_PROVIDER=robinhood` feeds real-time bars/quotes to the paper trader. It also skips new day-trade entries for
  symbols reporting earnings today and adds analyst consensus to the daily Discord summary.
- The root project's `data/providers/live/robinhood_backend.py` exposes the same data to Discord/Telegram live-market research.
- Keep trade approvals ON and options/margin OFF on the Robinhood MCP account; the OAuth token can technically do more than our client allows.

## Improvement loop (`improve`)
1. Walk-forward ridge regression (70/30 chronological split) predicts 10-bar forward return from momentum/RSI/MACD/Bollinger/volume/VWAP features.
2. The model is promoted only if out-of-sample IC ≥ 0.02 and hit-rate ≥ 51%; the day trader then vetoes entries with negative predicted return.
3. A vectorized SMA crossover sweep (GPU via CuPy if installed) nudges `fast`/`slow` at most 3 periods per run.
4. Every run is logged to `state/improvement_log.jsonl`. Run it nightly after close.

GPU: `pip install cupy-cuda12x` on the gaming PC; `TRADER_USE_GPU=0` forces CPU. The Mac can run the loop while the PC runs `improve` on a shared state dir.

## Safety / Robinhood MCP
`TRADING_MODE` must be `paper` (anything else raises). `robinhood_mcp` is a disabled stub: Robinhood has no official retail API, so
wire a community MCP server only after paper results are proven, with an explicit human-approval step. Mock results are random walks and say nothing about edge.

## Live quant, gaming PC push, shared cache

- `python -m agentic_trader rh-quant NVDA AAPL` – live-quote quant metrics (RSI, MACD hist, Bollinger/VWAP z, ATR%, realized vol,
  momentum, Sharpe-like, spread, mean-reversion half-life, variance ratio, beta/corr vs SPY, composite signal) plus a
  walk-forward ridge scorecard (OOS IC, hit rate, R², RMSE, MAE, calibration slope, RMSE vs naive). Metrics are pushed to the
  gaming PC `/compute` worker (root `GAMING_PC_*` config) when `/health` is online; local compute is always returned.
  Note: on macOS the Python used must have Local Network permission (the bot's `~/.venv` works; a bare Homebrew venv may get "No route to host").
- Robinhood market data is cached on disk through the root `shared_storage` (namespaces `robinhood_market`, short TTL, and
  `robinhood_stale`, 24h last-known-good fallback if the MCP call fails). Market data only – never accounts or portfolio values.
- The root bot's `RobinhoodBackend` now detects tickers/company names in free text and adds the quant line to live answers.
  Restart the bot (`launchctl kickstart -k gui/$(id -u)/com.bunnyhouse.stockagent.discord`) to load it.
