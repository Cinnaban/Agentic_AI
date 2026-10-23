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

## Telegram: Robinhood portfolio and approved orders
Only Telegram can reach Robinhood account tools (Discord is market-data only). Commands: `/myid`, `/portfolio`, `/buy SYM $amt|qty [@ limit]`, `/sell SYM qty`, `/confirm CODE`.
- Access requires your Telegram user ID in root `.env` `TELEGRAM_ROBINHOOD_USER_IDS`.
- Orders: MCP account only, equities only, no margin/options, per-order and daily caps, one-time 120s confirm code, placed only if `ROBINHOOD_LIVE_ORDERS=true` and the app's trade approval is ON.
- Audit log: `state/rh_orders_audit.jsonl`.
- `/review [SYMBOLS]`: per-holding analysis across all accounts (price, market cap, gain/loss, MA20/50/200, beta, dividend, sentiment, 5-day outlook, ETF top holdings).

## Internal paper trading (live Robinhood data, simulated fills)
`python -m agentic_trader paper-live` (service: `run_paper_trader.sh` via launchd `com.bunnyhouse.stockagent.papertrader`; `--once`, `--status`, `--reset`).
- Start cash $5,000 (`PAPER_START_CASH`; changing it archives the old account and restarts). Day-trade rule: margin account with equity >= $2,000 has no limit (2026); below that the legacy 3-per-5-days limit applies (`PAPER_ACCOUNT_TYPE`, `PAPER_PDT_FREE_MIN_EQUITY`). Account state is stored in shared_storage (namespace `paper_trader`) with a mirror in `state/paper_live.json`.
- Data only comes from the read-only Robinhood MCP path. The module never touches account or order tools (enforced by a test).
- Sleeves: ETF core (VOO/QQQ/SCHD/VXUS, in while above MA50), day trader (live-quote quant signal, inverse-vol sizing, 1.5% stop / 2% target, flat by 15:50 ET, max 3 positions), volatility hedge (VIX + SPY 20d vol -> calm 0%, normal 5%, elevated 10%, stressed 20% in SH; +5% if SPY < MA50; day-trade size scaled down when elevated/stressed).
- Fees modelled: SEC fee + FINRA TAF on sells (min $0.01), buys at ask / sells at bid. All P/L is net of these.
- Discord: every 30 min (10:00-15:30 ET) to `DISCORD_REALTIMETRADER_CHANNEL_ID`, daily summary after the close to `DISCORD_UPDATES_CHANNEL_ID`. Both include P/L net of fees, holdings maintained, holdings let go and portfolio trend.
- Telegram `/paper` shows the stored paper account.
- Not modelled: pattern-day-trader limits (real accounts under $25K are limited to 3 day trades per 5 days), slippage beyond the spread, taxes.

## Tables
Portfolio, stock and ETF evaluations (Discord, Telegram, `/review`, `/portfolio`) render as monospace tables
(`agentic_trader/tables.py`). Pasted portfolios may include a trailing sector column (`Ticker Weight Sector`).
Telegram sends tables as `<pre>` blocks; long replies split between tables, never inside one.

## Goals and options income (paper only)
- **Goals:** day +2-5%, week +5-10% (`PAPER_DAILY_TARGET_MIN/MAX`, `PAPER_WEEKLY_TARGET_MIN/MAX`). They are measured and shown in every summary
  ("below / on / above target") but the bot does not add risk to chase them; once the daily max is reached it stops opening new day trades.
- **Options income sleeve** (`paper_options.py`, `PAPER_OPTIONS=0` disables): sells cash-secured puts and, after assignment, covered calls
  (a "wheel") using real Robinhood option quotes. Never naked: puts need strike x 100 cash reserved, calls need 100 unencumbered income shares
  and a strike at or above cost. The paper account does not short stock, so "covered puts" are implemented as cash-secured puts.
  Skips names with earnings inside the window, illiquid contracts, and falling stocks; takes profit at 75%, stops puts at 3x credit,
  settles/assigns at expiry. Fee estimate `PAPER_OPTION_FEE_PER_CONTRACT`. Live option orders remain impossible (data tools only).
- **Limited-loss only (hard rule):** `paper_options.py` accepts only cash-secured puts and covered calls (`ALLOWED_KINDS`); anything else raises
  `UnlimitedRiskRefused`. Each position's worst case is computed and shown in summaries, and a per-cycle risk guard force-closes any short
  option that is not fully covered/secured. Option placement tools (`place_option_order`, exercise) are not callable by the data client.
