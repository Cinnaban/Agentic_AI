# Agentic_Trader

A paper-trading agentic stock desk. An **orchestrator** sets goals, budgets and risk dials for three teams, which trade a simulated $5,000 account on live Robinhood market data (read-only). No real orders are ever placed (`ROBINHOOD_LIVE_ORDERS=false`, enforced by tests).

| Team | Goal | Logic |
|---|---|---|
| **Growth** (`desk.py`, `growth_members.py`, `factor_tilt.py`) | long-term growth, beat the S&P 500 | ETF core (VOO/QQQ/SCHD/VXUS) with trend filter, dual-momentum members, S43-style factor tilt, one action per day, volatility hedge in `SH` |
| **Day team** (`day_agents.py`, `day_strategy.py`) | daily profit | one agent per strategy: ORB, PULLBACK, MOMENTUM, REVERSION (RETEST, SWEEP, FVG, GAPGO exist but are OFF after losing in replay); ATR stops, risk-based size, auto-pause on weak profit factor, flat by 15:50 ET |
| **Options team** (`options_agents.py`, `paper_options.py`) | premium income | yield, defensive and vol-premium puts, put credit spreads, covered calls. May lose its whole budget, but every structure is defined-risk: no naked contracts |

**Orchestrator** (`desk.py`): regime and drawdown rules, daily/weekly goal tracking, and a **weekly capital review** that resizes each team's share of the account by its return on the budget it was given (10%-150% of base, hard ceilings growth 70% / options 70% / day 40%).

**Quant gate** (`quant_suite.py`, `quant_gate.py`): before trades, RSI/MACD, Z-score, RVOL, realized vol, GARCH, RMSE, hit rate, IC, log loss/AUC (purged walk-forward splits) and Sharpe/Sortino/max drawdown/profit factor score and can veto candidates. It runs on the Gaming PC when online and falls back to local compute. **Signal research** (`signal_research.py`) ranks 21 indicators and their pairs on a time-split holdout to weight candidates.

**Reporting:** half-hour summaries to `DISCORD_REALTIMETRADER_CHANNEL_ID`, daily summary at the close to `DISCORD_UPDATES_CHANNEL_ID` (P/L net of fees, trades, holdings, per-team and per-strategy results, options scan, goals). A local **Grafana** dashboard (`grafana/`) charts equity vs the S&P, holdings, team budgets, per-team results, options, ranking and quant metrics.

**Data sources:** Robinhood MCP (market data only), Yahoo Finance, Alpha Vantage (quota-guarded), SEC, FRED, Kaggle/World Bank and news/earnings signals. The root analysis bot also uses an optional Google Programmable Search fallback for quarterly financial records (`GOOGLE_SEARCH_API_KEY`, `GOOGLE_SEARCH_ENGINE_ID`).

> Paper results are simulated: fills use bid/ask and modelled fees, not real liquidity, and the new strategies have little closed-trade history. Nothing here is financial advice. The sections below are the detailed reference.

## Layout
```
agentic_trader/
  paper_live.py       live paper trader loop, account, summaries (service entry point)
  desk.py             orchestrator, growth team, mandates, weekly capital review
  day_agents.py / day_strategy.py   day team agents and strategy triggers
  options_agents.py / paper_options.py   options sub-manager, agents, ledger and risk guard
  quant_suite.py / quant_gate.py / quant_worker.py   pre-trade quant metrics and veto (Gaming PC or local)
  signal_research.py  indicator and pair ranking
  market_apis/        Alpha Vantage, Kaggle, World Bank clients
  robinhood/          read-only MCP client (allow-listed tools)
  grafana_export.py   state -> SQLite for the Grafana dashboard
  config.py, engine.py, strategies/, data/, brokers/, improve.py   original mock/simulate framework
grafana/              dashboard and provisioning
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

## Safety
`TRADING_MODE` must be `paper` (anything else raises). The paper trader reads market data only; account, order and portfolio tools are refused by an allow-list. Only Telegram can reach Robinhood account tools, and orders there need an explicit confirm code and `ROBINHOOD_LIVE_ORDERS=true`. Options are limited to defined-risk structures (`UnlimitedRiskRefused`). Mock results are random walks and say nothing about edge.

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
- **Limited-loss only (hard rule):** `paper_options.py` accepts only cash-secured puts, covered calls and put credit spreads (`ALLOWED_KINDS`); anything else raises
  `UnlimitedRiskRefused`. Each position's worst case is computed and shown in summaries, and a per-cycle risk guard force-closes any short
  option that is not fully covered/secured. Option placement tools (`place_option_order`, exercise) are not callable by the data client.

## Grafana dashboard (local)

`agentic_trader/grafana_export.py` rebuilds `state/trader_history.db` (SQLite, read-only view of
`state/paper_live.json`) every 60 seconds via the `com.bunnyhouse.trader-grafana-export` launch agent.
Grafana (Homebrew, `brew services start grafana`) provisions the `Trader History` datasource and the
`Paper Trader` dashboard from `grafana/`. Open http://localhost:3000/d/paper-trader (anonymous viewer,
bound to 127.0.0.1). Requires the `frser-sqlite-datasource` plugin
(`grafana cli --homepath /opt/homebrew/opt/grafana/share/grafana plugins install frser-sqlite-datasource`)
and symlinks of `grafana/provisioning/*/trader.yaml` into `/opt/homebrew/etc/grafana/provisioning/`.

## One trade per day (growth and day agents)
The growth (long) agent and the day agent each get exactly **one trade per day**, taken early in the open (entry window 9:35-10:30 ET).
Candidates are ranked on prediction (quant signal + regression IC + 5-day outlook), market sentiment (analyst mix, target upside),
financial evaluation (P/E, size, dividend) and market trend (MA20/MA50, slope) - see `single_trade.py`. If nothing qualifies, no trade that day.
- Day agent: buys the single best-ranked name (`PAPER_SINGLE_MIN_SCORE`, RSI < 75), holds it, and closes it at 15:50 ET. No intraday stop/target
  unless `PAPER_DAY_INTRADAY_EXITS=1`.
- Growth agent: its one action is the top-priority of: trend-break sell > urgent hedge change > best ETF buy > hedge adjust > over-weight trim
  (`PAPER_GROWTH_MIN_SCORE`). It builds target weights one ETF per day.
- Options agent: unchanged, trades through the day (cash-secured puts / covered calls only).

## Stop losses and weekly goal
- Day agent: stop = 1.5x the stock's daily volatility from cost, clamped to 1.5-3.5%. Growth agent (ETFs): 3x daily vol, clamped to 5-9%
  (`PAPER_DAY_STOP_*`, `PAPER_GROWTH_STOP_*`). The stop is stored on the position at entry and checked every cycle; stop exits are protective
  and do not count against the one-entry-per-day limit (no re-entry the same day). The hedge (SH) and option-assigned shares are not stopped.
- Weekly goal is now ~10% (band 8-12%); it is measured and reported, and the desk banks gains above the top of the band. It never raises risk caps to chase it.

## Day trader (multiple intraday trades)
Uses 5-minute bars: VWAP, EMA9/21, RSI, ATR, opening range and relative volume. Setups: opening-range breakout and VWAP/EMA pullback, only when SPY is not weak. Every entry has an ATR-based stop, a ~2R target, break-even at 1R and a trailing stop; it also exits on trend failure or stall, and flattens at 15:50. Size is risk-based (0.5% of equity per trade). Limits: 8 entries/day, 2 open, 1.5% daily loss halt, 30 min re-entry cooldown. Tunables: `PAPER_DAY_*` (see `.env.example`). Growth stays at 1 trade/day; goals are measured, not chased.

## Agent teams
The orchestrator sets goals, budgets and risk dials; it never trades. Three teams report to it (growth, day and options); the day team and options sub-manager are described here:
- **Day team** (`day_agents.py`): one independent agent per strategy — ORB (opening-range breakout), PULLBACK (VWAP/EMA pullback), MOMENTUM (day-high breakout), REVERSION (oversold bounce, VWAP target). Same day budget (split into equal slices), same rules (ATR stop on every entry, risk-based size, break-even/trail, flat at 15:50). Each agent has its own entry cap, loss limit and one open position; the desk adds team caps, the SPY filter and shared exits. Choose agents with `PAPER_DAY_STRATEGIES`. Four more structure strategies exist but are OFF by default because they lost money in a 30-day 5-minute replay: RETEST (break-and-retest), SWEEP (liquidity sweep reclaim), FVG (fair-value-gap fill), GAPGO (gap-and-go; `PAPER_DAY_GAP_MIN`). A day agent with a profit factor below `PAPER_DAY_AUTOPAUSE_PF` (0.6) over at least `PAPER_DAY_AUTOPAUSE_MIN_TRADES` (8) closed trades in 10 days stands down (`PAPER_DAY_AUTOPAUSE=0` disables).
- **Options sub-manager** (`options_agents.py`): owns the risk guard, marks/exits and the capital split, and runs yield puts, defensive puts, vol-premium puts (VRP: only when implied vol is at least 1.15x realized, 10-25 delta), put credit spreads (short put plus a bought lower-strike put; secured by the full width, cash-settled, loss capped at width minus credit) and covered calls. Only cash-secured puts, covered calls and put credit spreads can be opened, so nothing can have unlimited loss; `naked_violations()` and `enforce()` close anything that is not capped. Long calls, straddles and 0DTE are not built.
- **Weekly capital review** (`Orchestrator.weekly_review`): every 7 days each active team's budget is resized by its trailing-week return on the budget it was given (realized plus open): a team that lost its whole budget is cut by 50%, gains raise it by up to 30%. Budgets stay within 10%-150% of the configured base and under a hard ceiling (growth 70%, options 70%, day 40%). History is in `state["alloc"]` and the Grafana "Team budget" panels.
- **Options risk**: the options team may lose its entire budget (default 50% of the account, up to 10 positions, no volatility or drawdown scale-down), but every structure is defined-risk (cash-secured puts, covered calls, put credit spreads). Naked contracts stay disabled.
- **Signal research** (`signal_research.py`, `python -m agentic_trader.signal_research`): ranks 21 indicators and every pair of them by 5-day excess return versus SPY. The first 60% of the history ranks them; the last 40% (after a purge gap) confirms. "confirmed" candidates get weight up to 1, "provisional" (positive but weak on the holdout) 0.25, everything else 0. The weights add a bonus (`PAPER_SIGNAL_RANK_WEIGHT`) to day and options candidate ordering and refresh weekly (`PAPER_SIGNAL_RANK=0` disables). Result so far: no combination beat the single indicators on the holdout, and the top train-ranked combinations did worse out of sample, the signature of overfitting.
Trades are tagged with the owning agent (`strat`) and each agent's results appear in the summaries.

## Market data APIs (Alpha Vantage, Kaggle)
- `agentic_trader/market_apis/alpha_vantage.py`: cached, budget-guarded client (quote, FX, economic series, movers). Free tier is 25 requests/day; premium-only endpoints (OVERVIEW, NEWS_SENTIMENT) are detected and skipped. The root bots add it to replies for economic, forex, stock/ETF and market queries (`data/providers/live/alpha_vantage_backend.py`); the Robinhood real-time quote stays authoritative for price.
- `agentic_trader/market_apis/kaggle.py`: public dataset search/metadata/download (no credentials needed) into `<shared_storage>/market_datasets/kaggle/`, capped by `KAGGLE_MAX_DOWNLOAD_MB`.
- `agentic_trader/market_apis/world_bank.py`: World Bank Open Data (no key) for country economic, demographic and governance indicators (GDP, inflation, unemployment, population, debt, trade, political stability, corruption). The root bots add it (`data/providers/live/world_bank_backend.py`) when a country or global scope is paired with an economic, demographic, political or market topic.

## Pre-trade quant suite

Before day, options and long entries, `quant_gate.py` runs `quant_suite.py` on recent bars:
RSI/MACD, Z-score, RVOL, realized vol, GARCH(1,1), plus purged walk-forward (never random)
out-of-sample RMSE, hit rate, IC, log loss, AUC, and Sharpe/Sortino/Max DD/Profit Factor.
The verdict can veto a new entry or scale its size; a weak edge (~53% hit rate) is still sized, not discarded.
It fails open, never blocks protective sells, and results land in `state/quant_suite.json`.

Compute runs on the Gaming PC if its worker answers (`python -m agentic_trader.quant_worker`, port 8011,
CuPy used if installed); otherwise it runs locally. Set `PAPER_QUANT_GATE=false` to disable.
The Grafana dashboard shows current holdings (donut and table), risk stats and the quant table, plus a Day trading section:
KPI cards, a table of the team against each strategy (closes, win rate, net, average win/loss, best, worst, profit factor),
cumulative P&L for the team and each strategy, daily P&L stacked by strategy, and the top 10 gains and losses.
Trades before the strategy team existed show as `LEGACY (pre-team)`.
The Discord daily summary carries the same view: a "Day team performance" block with the team and each strategy (closed trades, win rate, net, average win/loss, profit factor) for today and the strategy-team era, plus the top gains and losses.

## News, earnings and growth members

- `market_signals.py`: Alpha Vantage `NEWS_SENTIMENT` (one batched call per group per 2h; growth, day and options each
  refresh their own symbols) and the fed funds rate. A name with at least 3 relevant articles averaging <= -0.25 is
  "bearish": no new day entry, put sale or ETF buy. It stays under the shared daily quota (a reserve of 10 calls is left
  for the chat bots) and fails open. `PAPER_NEWS_SIGNAL=0` turns it off (the test suite does).
- Day team skips symbols that report earnings today (`PAPER_DAY_SKIP_EARNINGS`).
- `growth_members.py`: Antonacci dual momentum (12-month rank plus absolute momentum against the fed funds rate) and
  Faber's 200-day trend. A MA50 break only sells when it is confirmed (member bearish or price 3% below the MA50).
- Backtests on ~5 years of daily bars found no classic day-trading rule (Williams breakout, gaps, NR7, inside day, IBS, RSI2)
  that beat the baseline, so none were added to the day team.

## Day team factor tilt

`factor_tilt.py` ranks the day symbols against each other on equal-weighted price/liquidity predictors
(6-1 momentum, 52-week-high proximity, 1-month reversal, max-return "lottery" penalty, volatility, illiquidity),
adapted from the S43 kit. It adds `PAPER_DAY_TILT_WEIGHT` x tilt to a setup's rank and skips names under
`PAPER_DAY_MIN_DOLLAR_VOLUME`. It never creates or vetoes an entry by itself.
