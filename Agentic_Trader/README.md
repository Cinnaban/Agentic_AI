# Agentic_Trader

A paper-trading agentic stock desk. An **orchestrator** sets goals, budgets and risk dials for three teams, which trade a simulated $5,000 account on live Robinhood market data (read-only). No real orders are ever placed (`ROBINHOOD_LIVE_ORDERS=false`, enforced by tests).

| Team | Goal | Logic |
|---|---|---|
| **Growth** (`desk.py`, `growth_members.py`, `factor_tilt.py`) | long-term growth, beat the S&P 500 | ETF core (VOO/QQQ/SCHD/VXUS) with trend filter, dual-momentum members, S43-style factor tilt, one action per day, volatility hedge in `SH` |
| **Day team** (`day_agents.py`, `day_strategy.py`) | daily profit | one agent per strategy: ORB, PULLBACK, MOMENTUM, REVERSION (RETEST, SWEEP, FVG, GAPGO exist but are OFF after losing in replay); ATR stops, risk-based size, auto-pause on weak profit factor, flat by 15:50 ET |
| **Options team** (`options_agents.py`, `paper_options.py`) | premium income | yield, defensive and vol-premium puts, put credit spreads, covered calls. May lose its whole budget, but every structure is defined-risk: no naked contracts |

**Orchestrator** (`desk.py`): regime and drawdown rules, daily/weekly goal tracking, the **historian briefing** and a **weekly capital review** that resizes each team's share of the account by its return on the budget it was given (10%-150% of base, hard ceilings growth 70% / options 70% / day 40%).

**Historian** (`historian.py`): summarizes yesterday, the last week and the last 90 days for each team and hands the briefing to the orchestrator, which passes each team its own slice when trades are reviewed and placed.

**Quant gate** (`quant_suite.py`, `quant_gate.py`): before trades, RSI/MACD, Z-score, RVOL, realized vol, GARCH, RMSE, hit rate, IC, log loss/AUC (purged walk-forward splits) and Sharpe/Sortino/max drawdown/profit factor score and can veto candidates. It runs on the Gaming PC when online and falls back to local compute. **Signal research** (`signal_research.py`) ranks 21 indicators and their pairs on a time-split holdout to weight candidates.

**Reporting:** half-hour summaries to `DISCORD_REALTIMETRADER_CHANNEL_ID`, daily summary at the close to `DISCORD_UPDATES_CHANNEL_ID` (P/L net of fees, trades, holdings, per-team and per-strategy results, options scan, desk briefing, goals). A local **Grafana** dashboard (`grafana/`) charts equity vs the S&P, holdings, team budgets, per-team results, the desk briefing, options, ranking and quant metrics.

**Data sources:** Robinhood MCP (market data only), Yahoo Finance, Alpha Vantage (quota-guarded), SEC, FRED, Kaggle/World Bank and news/earnings signals. The root analysis bot also uses an optional Google Programmable Search fallback for quarterly financial records (`GOOGLE_SEARCH_API_KEY`, `GOOGLE_SEARCH_ENGINE_ID`).

> Paper results are simulated: fills use bid/ask and modelled fees, not real liquidity, and the newer strategies have little closed-trade history. Nothing here is financial advice.

## Layout
```
agentic_trader/
  paper_live.py       live paper trader loop, account, summaries (service entry point)
  desk.py             orchestrator, growth team, mandates, weekly capital review
  historian.py        daily/weekly/historical team briefings
  day_agents.py / day_strategy.py   day team agents and strategy triggers
  options_agents.py / paper_options.py   options sub-manager, agents, ledger and risk guard
  quant_suite.py / quant_gate.py / quant_worker.py   pre-trade quant metrics and veto (Gaming PC or local)
  signal_research.py  indicator and pair ranking
  market_signals.py / growth_members.py / factor_tilt.py   news, earnings, dual momentum, factor tilt
  market_apis/        Alpha Vantage, Kaggle, World Bank clients
  robinhood/          read-only MCP client (allow-listed tools)
  grafana_export.py   state -> SQLite for the Grafana dashboard
  tables.py, notify/  monospace tables and Discord delivery
grafana/              dashboard and provisioning
tests/                offline test suite
```

## Quick start
```bash
cd Agentic_Trader
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env                        # then fill in keys
python -m agentic_trader rh-login --manual  # once, Robinhood MCP OAuth (market data only)
python -m agentic_trader paper-live --once  # one cycle; --status, --reset
python -m agentic_trader discord-test
pytest
```
Production runs `paper-live` as a loop under launchd (`com.bunnyhouse.stockagent.papertrader`, script `run_paper_trader.sh`). With no `DISCORD_BOT_TOKEN`, messages go to `state/discord_outbox.log`.

## Paper account
- Start cash $5,000 (`PAPER_START_CASH`; changing it archives the old account and restarts). Day-trade rule: a margin account with equity >= $2,000 has no limit (2026); below that the legacy 3-per-5-days limit applies (`PAPER_ACCOUNT_TYPE`, `PAPER_PDT_FREE_MIN_EQUITY`). State is stored in shared_storage (namespace `paper_trader`) with a mirror in `state/paper_live.json`.
- Data comes only from the read-only Robinhood MCP path. The module never touches account or order tools (enforced by a test).
- Fees modelled: SEC fee + FINRA TAF on sells (min $0.01), buys at ask / sells at bid. All P/L is net of these.
- Not modelled: slippage beyond the spread, real liquidity, taxes.
- Telegram `/paper` shows the stored paper account.

## Discord
- `DISCORD_REALTIMETRADER_CHANNEL_ID`: every 30 min (10:00-15:30 ET) summary of moves, trades, open positions and P&L.
- `DISCORD_UPDATES_CHANNEL_ID`: daily summary after the close: P/L net of fees, holdings, per-team and per-strategy results, top gains and losses, options scan, desk briefing, goals.
Uses the same `DISCORD_BOT_TOKEN` as the root project (the bot needs Send Messages in both channels).

## Robinhood MCP (read-only market data and research)
`python -m agentic_trader rh-tools`, `rh-research SPY NVDA`, `rh-quant NVDA AAPL`.
- Tokens are stored in `Agentic_Trader/.env` (gitignored); refresh is file-locked so the bots and trader can share them.
- `robinhood/mcp_client.py` only calls a fixed market-data allow-list (`SAFE_TOOLS`): quotes, bars, indicators, fundamentals, analyst ratings, earnings, SEC filings, search. Orders, positions, portfolio, balances, watchlists and alerts are refused. Portfolio values are never read.
- The paper trader skips new day entries for symbols reporting earnings today and adds analyst consensus to the daily summary.
- Market data is cached through the root `shared_storage` (`robinhood_market` short TTL, `robinhood_stale` 24h last-known-good fallback). The root bots reuse it (`data/providers/live/robinhood_backend.py`) for live-market answers.
- Keep trade approvals ON and options/margin OFF on the Robinhood MCP account; the OAuth token can technically do more than our client allows.
- `rh-quant` pushes live-quote metrics to the Gaming PC `/compute` worker (root `GAMING_PC_*` config) when `/health` is online; local compute is always returned. On macOS the Python used needs Local Network permission.

## Safety
`TRADING_MODE` must be `paper` (anything else raises). The paper trader reads market data only; account, order and portfolio tools are refused by an allow-list. Only Telegram can reach Robinhood account tools, and orders there need an explicit confirm code and `ROBINHOOD_LIVE_ORDERS=true`. Options are limited to defined-risk structures (`UnlimitedRiskRefused`).

## Telegram: Robinhood portfolio and approved orders
Only Telegram can reach Robinhood account tools (Discord is market-data only). Commands: `/myid`, `/portfolio`, `/buy SYM $amt|qty [@ limit]`, `/sell SYM qty`, `/confirm CODE`, `/review [SYMBOLS]`.
- Access requires your Telegram user ID in root `.env` `TELEGRAM_ROBINHOOD_USER_IDS`.
- Orders: MCP account only, equities only, no margin/options, per-order and daily caps, one-time 120s confirm code, placed only if `ROBINHOOD_LIVE_ORDERS=true` and the app's trade approval is ON.
- Audit log: `state/rh_orders_audit.jsonl`.

## Agent teams
The orchestrator sets goals, budgets and risk dials; it never trades. Trades are tagged with the owning agent (`strat`) and each agent's results appear in the summaries.
- **Growth team**: ETF core in while above MA50, sized by factor tilt; Antonacci dual momentum (12-month rank plus absolute momentum against the fed funds rate) and Faber's 200-day trend. A MA50 break only sells when confirmed (member bearish or price 3% below the MA50). One action per day. Stops 3x daily vol, clamped to 5-9% (`PAPER_GROWTH_STOP_*`). The volatility hedge (VIX + SPY 20d vol: calm 0%, normal 5%, elevated 10%, stressed 20% in `SH`, +5% if SPY < MA50) is not stopped.
- **Day team** (`day_agents.py`): one independent agent per strategy, chosen with `PAPER_DAY_STRATEGIES`. ORB (opening-range breakout), PULLBACK (VWAP/EMA pullback), MOMENTUM (day-high breakout), REVERSION (oversold bounce, VWAP target). Each has an ATR stop, a ~2R target, break-even at 1R, a trailing stop and risk-based size; flat at 15:50 ET. Each agent has its own entry cap, loss limit and one open position; the desk adds team caps, the SPY filter and shared exits (tunables `PAPER_DAY_*`, see `.env.example`). RETEST, SWEEP, FVG and GAPGO are OFF because they lost money in a 30-day 5-minute replay. An agent with a profit factor below `PAPER_DAY_AUTOPAUSE_PF` (0.6) over at least `PAPER_DAY_AUTOPAUSE_MIN_TRADES` (8) closed trades in 10 days stands down (`PAPER_DAY_AUTOPAUSE=0` disables). Names reporting earnings today are skipped (`PAPER_DAY_SKIP_EARNINGS`).
- **Factor tilt** (`factor_tilt.py`): ranks the day symbols on equal-weighted price/liquidity predictors (6-1 momentum, 52-week-high proximity, 1-month reversal, max-return penalty, volatility, illiquidity), adapted from the S43 kit. It adds `PAPER_DAY_TILT_WEIGHT` x tilt to a setup's rank and skips names under `PAPER_DAY_MIN_DOLLAR_VOLUME`; it never creates or vetoes an entry by itself.
- **Options team** (`options_agents.py`): the sub-manager owns the risk guard, marks/exits and the candidate scan; agents sell cash-secured puts (yield, defensive, vol-premium), put credit spreads and covered calls using real Robinhood option quotes. It may lose its entire budget (default 50% of the account, `PAPER_OPTION_PCT`, up to 10 positions, no volatility or drawdown scale-down). It skips names with earnings in the window, illiquid contracts and falling stocks (judged relative to SPY), takes profit at 75% and settles/assigns at expiry. `PAPER_OPTIONS=0` disables it.
- **Limited loss only (hard rule):** `paper_options.py` accepts only cash-secured puts, covered calls and put credit spreads (`ALLOWED_KINDS`); anything else raises `UnlimitedRiskRefused`. Puts need strike x 100 cash reserved, calls need 100 unencumbered shares at or above cost, spreads are secured by their width. A per-cycle risk guard force-closes any short option that is not covered or secured. Option placement tools are not callable by the data client.
- **Weekly capital review** (`Orchestrator.weekly_review`): every 7 days each active team's budget is resized by its trailing-week return on the budget it was given (realized plus open). A team that lost its whole budget is cut by 50%; gains raise it by up to 30%. Budgets stay within 10%-150% of the configured base and under the hard ceilings. History is in `state["alloc"]` and the Grafana "Team budget" panels.
- **Goals:** day +2-5%, week +8-12% (`PAPER_DAILY_TARGET_*`, `PAPER_WEEKLY_TARGET_*`). They are measured and shown in every summary, but the desk never adds risk to chase them.

## Historian briefing
`historian.py` is deterministic (no LLM). Every planning cycle the orchestrator asks it for a briefing built from the closed trades in the paper ledger:
- **Per team** (growth, day, options): yesterday (last prior day with closed trades), the last 7 days, and the last 90 days: closed trades, net P&L, win rate, profit factor, best and worst symbol. A team with fewer than 5 closed trades is flagged "history is thin".
- **Market**: SPY's move yesterday and over the week, from recorded closes.
- **Avoid / favored**: over the last `PAPER_BRIEF_DAYS` (30) days, a symbol (or a `STRATEGY|SYMBOL` pair) with at least `PAPER_BRIEF_MIN_TRADES` (3) closed trades is **avoided** when its net is below -0.2% of equity and its win rate is at most 34%, and **favored** when net is positive and win rate is at least 60%.
- **How teams use it**: the day team skips avoided setups ("setup skipped by briefing") and adds `PAPER_BRIEF_WEIGHT` (0.15) to favored candidates' scores; the options team skips avoided names ("weak recent results (briefing)") and boosts favored ones; the growth team skips ETF buys in avoided names. The briefing never blocks protective exits.
- **Where it shows**: the daily Discord summary ("Desk briefing") and the Grafana "Desk briefing" table. `PAPER_BRIEFING=0` turns it off.

Treat these signals as hints: they come from small samples and are noisy.

## Pre-trade quant suite
Before day, options and long entries, `quant_gate.py` runs `quant_suite.py` on recent bars: RSI/MACD, Z-score, RVOL, realized vol, GARCH(1,1), plus purged walk-forward (never random) out-of-sample RMSE, hit rate, IC, log loss, AUC, and Sharpe/Sortino/Max DD/Profit Factor. The verdict can veto a new entry or scale its size; a weak edge (~53% hit rate) is still sized, not discarded. It fails open, never blocks protective sells, and results land in `state/quant_suite.json`.

Compute runs on the Gaming PC if its worker answers (`python -m agentic_trader.quant_worker`, port 8011, CuPy used if installed); otherwise it runs locally. `PAPER_QUANT_GATE=false` disables it.

**Signal research** (`python -m agentic_trader.signal_research`) ranks 21 indicators and every pair by 5-day excess return versus SPY. The first 60% of the history ranks them; the last 40% (after a purge gap) confirms. "Confirmed" candidates get weight up to 1, "provisional" 0.25, everything else 0. The weights add a bonus (`PAPER_SIGNAL_RANK_WEIGHT`) to day and options candidate ordering and refresh weekly (`PAPER_SIGNAL_RANK=0` disables). Current result: no combination beat the single indicators on the holdout.

## News and earnings
`market_signals.py`: Alpha Vantage `NEWS_SENTIMENT` (one batched call per group per 2h) and the fed funds rate. A name with at least 3 relevant articles averaging <= -0.25 is "bearish": no new day entry, put sale or ETF buy. It stays under the shared daily quota (10 calls reserved for the chat bots) and fails open. `PAPER_NEWS_SIGNAL=0` turns it off.

## Market data APIs
- `market_apis/alpha_vantage.py`: cached, budget-guarded client (quote, FX, economic series, movers). Free tier is 25 requests/day; premium-only endpoints are detected and skipped. The Robinhood real-time quote stays authoritative for price.
- `market_apis/kaggle.py`: public dataset search/metadata/download into `<shared_storage>/market_datasets/kaggle/`, capped by `KAGGLE_MAX_DOWNLOAD_MB`.
- `market_apis/world_bank.py`: World Bank Open Data (no key) for country economic and demographic indicators.

## Tables
Portfolio, stock and ETF evaluations (Discord, Telegram, `/review`, `/portfolio`) render as monospace tables (`tables.py`). Pasted portfolios may include a trailing sector column (`Ticker Weight Sector`). Telegram sends tables as `<pre>` blocks; long replies split between tables, never inside one.

## Grafana dashboard (local)
`grafana_export.py` rebuilds `state/trader_history.db` (SQLite, read-only view of `state/paper_live.json`) every 60 seconds via the `com.bunnyhouse.trader-grafana-export` launch agent. Grafana (Homebrew, `brew services start grafana`) provisions the `Trader History` datasource and the `Paper Trader` dashboard from `grafana/`. Open http://localhost:3000/d/paper-trader (anonymous viewer, bound to 127.0.0.1). It requires the `frser-sqlite-datasource` plugin (`grafana cli --homepath /opt/homebrew/opt/grafana/share/grafana plugins install frser-sqlite-datasource`) and symlinks of `grafana/provisioning/*/trader.yaml` into `/opt/homebrew/etc/grafana/provisioning/`.

Panels cover equity vs the S&P, holdings, risk and quant tables, team budgets, per-team and per-strategy results (closes, win rate, net, average win/loss, profit factor, cumulative and daily P&L, top 10 gains and losses), options positions and the desk briefing. Trades before the strategy team existed show as `LEGACY (pre-team)`.
