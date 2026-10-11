# Agentic AI / Stock Agent

A local-first agentic assistant running primarily on a Mac Mini, with a separate Gaming PC used for quantitative stock analysis. The project combines grounded financial research, current web/news retrieval, Telegram and Discord messaging, and scheduled ETF reporting.

## Phase 1 Status

Phase 1 is complete and establishes the core orchestration, grounding, live-data, messaging, and automation layers.

Validated capabilities include:

- Company detection and request routing through Hermes
- Gaming PC quantitative analysis for company/stock requests
- SEC company facts and filing metadata
- FRED macroeconomic context
- Deterministic signal reconciliation
- Risk analysis and quality validation
- General-response handling for non-company questions
- Current-topic detection through `FreshnessDetector`
- DuckDuckGo News discovery through DDGS
- Local Firecrawl page extraction and Markdown enrichment
- Recency filtering before Firecrawl enrichment
- Telegram messaging integration
- Discord messaging adapter and Questions/Updates channel separation
- Daily ETF spreadsheet update and Discord Updates publishing
- macOS `launchd` automation for the ETF job

A current-company integration test has completed successfully with an approved response and quality confidence of 95. The messaging pipeline has also validated Telegram priority `0` and Discord priority `10` in the routing layer.

## High-Level Architecture

```text
                         User
                          |
              +-----------+-----------+
              |                       |
          Telegram                  Discord
      interactive input        Questions channel
              |                       |
              +-----------+-----------+
                          |
                    MessageRouter
                          |
                        Hermes
                          |
        +-----------------+-----------------+
        |                 |                 |
    General          Current Topic      Company
    Question             Question        Question
        |                   |               |
 GeneralResponse       DDGS discovery    Gaming PC Quant
     Agent                 |               |
                           v               +-- SEC
                       Recency Filter      +-- FRED
                           |               +-- Market Context
                           v               |
                    Local Firecrawl        |
                           |               |
                           +-------+-------+
                                   |
                              Research / Summary
                                   |
                          Risk / Quality Validation
                                   |
                               User Response
```

Current company questions combine the company-analysis pipeline with the live retrieval layer:

```text
Current company question
        |
        +-- Gaming PC Quant
        +-- SEC
        +-- FRED
        +-- DDGS
              |
         Recency filter
              |
         Firecrawl
              |
        Research / Risk / Quality
```

## Systems

### Mac Mini

The Mac Mini is the primary orchestrator. It hosts or runs:

- Hermes orchestration
- Ollama model access
- Telegram integration
- Discord integration
- SEC and FRED providers
- DDGS topic/news discovery
- Docker Desktop
- Self-hosted Firecrawl
- ETF update automation
- `launchd` scheduled jobs

### Gaming PC

The Gaming PC handles the quantitative analysis workload used for company/stock requests.

The Mac Mini remains responsible for orchestration, grounding, reconciliation, risk evaluation, quality review, and message delivery.

## Request Routing

### General Knowledge

Example:

```text
Explain compound interest
```

Route:

```text
Hermes -> GeneralResponseAgent -> response
```

### Current General Topic

Examples:

```text
What's new with Pokemon?
What's recent in Data Science?
Latest Magic: The Gathering news
```

Route:

```text
Hermes
 -> FreshnessDetector
 -> DDGS
 -> recency filter
 -> Firecrawl enrichment
 -> CurrentTopicAgent
 -> response
```

### Company Analysis

Example:

```text
Analyze Nvidia
```

Route:

```text
Hermes
 -> company detection
 -> Gaming PC Quant
 -> SEC
 -> FRED
 -> Research
 -> deterministic signal reconciliation
 -> Risk
 -> Quality
 -> response
```

### Single ETF Evaluation

Example:

```text
Evaluate SOXX
```

An explicit ETF request is kept separate from portfolio evaluation. The
orchestrator resolves an instrument type from the user's explicit wording or
Yahoo Finance quote metadata, preserves `entity_type: "etf"` in the Gaming PC
compute payload, and retrieves fund-level evidence such as expense ratio, net
assets, top holdings, asset classes, and sector weights. ETF research and risk
prompts focus on fund exposures and do not treat the ETF as an operating
company; issuer-level SEC financial statements are marked not applicable.

If type metadata cannot be resolved, the request remains a security evaluation
and the classification uncertainty is retained rather than silently claiming
the ticker is an equity or ETF. ETF fund evidence can also be unavailable; that
limitation is surfaced in the response.

The Gaming PC service implementation is maintained separately from this
repository. The Mac-side request now includes the ETF type and fund evidence,
but ETF-specific remote quant calculations require the Gaming PC service to
consume those fields; validate that service contract before relying on remote
ETF model outputs.

### Quant Performance Chart

After a completed stock or ETF quant evaluation, Hermes attaches a chart of
trailing one-year total return using Yahoo Finance adjusted daily prices.
Stocks are compared with the S&P 500 (`SPY`) and an equal-weighted average of
at least three Yahoo Finance equities verified to share the stock's reported
industry. ETFs are compared with the S&P 500 only. If the industry peer group
cannot be verified or there is not enough price history, the chart reports
that limitation rather than substituting a sector index or unverified peers.
The image is delivered after the written evaluation in Telegram and Discord.

### Current Company Analysis

Example:

```text
What's the latest with Nvidia?
```

Route:

```text
Hermes
 -> company detection
 -> FreshnessDetector
 -> Gaming PC Quant
 -> SEC
 -> FRED
 -> DDGS
 -> recency filter
 -> Firecrawl
 -> Research
 -> Risk
 -> Quality
 -> response
```

## Evidence Hierarchy

The project intentionally separates evidence by source and purpose.

| Source | Purpose |
|---|---|
| SEC | Company-reported financial facts and filing metadata |
| FRED | Macroeconomic observations |
| Gaming PC | Quantitative/model-derived financial analysis |
| Yahoo Finance ETF metadata | ETF quote type, fund profile, fees, assets, holdings, and sector weights |
| DDGS | Current web/news discovery |
| Firecrawl | Retrieval and extraction of selected web pages |
| Model knowledge | Background context only, not authoritative current evidence |

Firecrawl is a retrieval mechanism, not the publisher. The original article publisher remains the evidence source.

For current/latest/recent questions, retrieved results are filtered by publication date before Firecrawl enrichment. If sufficiently recent evidence cannot be retrieved, the system should fail closed rather than substituting stale model memory as current information.

Research-backed responses include an evidence note with the UTC retrieval time, contributing publishers, and supplied publication dates where available. Financial analyses also identify available and unavailable evidence sources. Retrieval time indicates when this system gathered the evidence; it does not mean the underlying data itself is current. If live evidence cannot verify a current-information request, the response explicitly says so rather than falling back to model memory.

General factual answers search for the named subject's official website and
Wikipedia article first, retrieve a matching Wikipedia article directly when
available, and then use distinct public publishers for corroboration.
Irrelevant subject matches and social-platform results are excluded from
ordinary factual answers; Reddit/X evidence is retrieved only for explicit
community-discussion questions. Answers stay anchored to the user's question,
distinguish retrieved pages from search snippets, cite supplied source IDs,
and include direct source links so claims can be checked.
For direct "what/who/tell me about" questions, the bot presents short
attributed excerpts from retrieved pages instead of asking a language model to
rewrite factual details. If it has only search snippets and no readable page
text, it declines to assert a summary.

## Firecrawl

Firecrawl is self-hosted locally through Docker Desktop on the Mac Mini.

Current local configuration:

```text
FIRECRAWL_BASE_URL=http://localhost:3002
```

The project uses Firecrawl for page extraction after DDGS has discovered candidate URLs.

```text
DDGS -> recent URLs -> Firecrawl -> Markdown/page content -> Hermes
```

Firecrawl health is checked through the local service before enrichment. Individual page content is capped before it is passed further into the reasoning pipeline.

## Messaging

### Telegram

Telegram is the higher-priority interactive transport.

Configured environment variable:

```text
TELEGRAM_BOT_TOKEN=
```

The Telegram listener:

1. receives a message,
2. normalizes it through `TelegramAdapter`,
3. routes it through `MessageRouter`,
4. processes it through Hermes,
5. formats/chunks the result,
6. replies to the originating Telegram chat.

### Discord

Discord uses two separate channels:

```text
DISCORD_QUESTIONS_CHANNEL_ID=
DISCORD_UPDATES_CHANNEL_ID=
```

**Questions** is for interactive Hermes requests.

**Updates** is reserved for scheduled automated reports, including the ETF update.

The routing layer assigns:

```text
Telegram priority = 0
Discord priority  = 10
```

Lower values represent higher priority. Phase 2 can enforce this policy through a shared processing queue when simultaneous requests are waiting.

## Daily ETF Update

`workers/etf_update.py` maintains the ETF/asset spreadsheet and publishes an automated market update to the Discord Updates channel.

The scheduled flow is:

```text
launchd
 -> run_etf_update.sh
 -> load .env
 -> Google Sheet refresh
 -> yfinance maintenance data
 -> DDGS current headlines
 -> Hermes summary
 -> Discord Updates
```

The job is scheduled on the Mac Mini through `launchd` for:

```text
06:30 local Mac time, daily
```

The launcher is:

```text
~/Agentic_AI/run_etf_update.sh
```

The LaunchAgent is:

```text
~/Library/LaunchAgents/com.bunnyhouse.stockagent.etfupdate.plist
```

Firecrawl enrichment can be added to the scheduled ETF evidence path by enriching a small number of recent DDGS URLs before the Hermes summary is generated.

## Environment Configuration

Real secrets and machine-specific values belong in `.env`. Do not commit `.env` or credential JSON files.

Example `.env.example` structure:

```text
# Financial / regulatory data
FRED_API_KEY=
SEC_USER_AGENT=

# Telegram
TELEGRAM_BOT_TOKEN=

# Discord
DISCORD_BOT_TOKEN=
DISCORD_QUESTIONS_CHANNEL_ID=
DISCORD_UPDATES_CHANNEL_ID=

# Google Sheets
GOOGLE_CREDENTIALS_FILE=
GOOGLE_SHEET_NAME=
GOOGLE_ASSET_TAB=

# Local Firecrawl
FIRECRAWL_BASE_URL=
```

Non-secret application settings such as model names, Ollama endpoints, logging paths, and system prompts can remain in `configs/config.py` as appropriate.

## Clean Setup

The supported Python version is 3.11. From a fresh clone:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` locally; never commit it. The variables are optional unless the matching integration is enabled:

- **Telegram:** `TELEGRAM_BOT_TOKEN`
- **Discord questions bot:** `DISCORD_BOT_TOKEN` and `DISCORD_QUESTIONS_CHANNEL_ID`
- **ETF spreadsheet job:** `DISCORD_BOT_TOKEN`, `DISCORD_UPDATES_CHANNEL_ID`, `GOOGLE_CREDENTIALS_FILE`, `GOOGLE_SHEET_NAME`, and `GOOGLE_ASSET_TAB`
- **SEC requests:** `SEC_USER_AGENT` should identify the application and provide a contact email.
- **Optional evidence providers:** `FRED_API_KEY`, Inoreader feed URLs, and `FIRECRAWL_BASE_URL`

The credential file path in `GOOGLE_CREDENTIALS_FILE` must point to a locally provisioned Google service-account JSON file. The Ollama service and, for quantitative analysis, the Gaming PC worker must also be reachable using the endpoints configured in `configs/config.py`.

Run a bot from the repository root after loading the environment:

```bash
set -a
source .env
set +a
.venv/bin/python -m integrations.messaging.telegram_bot
```

Use `integrations.messaging.discord_bot` in place of the Telegram module to start the Discord bot. Stop either foreground process with `Ctrl-C`. The ETF job can be run manually with `.venv/bin/python workers/etf_update.py` after loading `.env`; it exits when the update completes. For a persistent macOS service, install the LaunchAgent in the user's `~/Library/LaunchAgents` and configure its program arguments and log paths for the local clone. The machine-specific scripts and LaunchAgent used by the current Mac Mini are intentionally not included as portable deployment files.

## CI and Offline Tests

The GitHub Actions workflow compiles application modules and runs a selected deterministic test set on Python 3.11. It does not contact Ollama, SEC/FRED, Discord/Telegram, Google Sheets, Firecrawl, or the Gaming PC. Run the same checks locally:

```bash
.venv/bin/python -m compileall -q agents configs data financial_engine integrations job_queue memory orchestrator security shared_storage utils workers
.venv/bin/python -m unittest discover -s tests -p 'test_evidence_provenance.py'
.venv/bin/python -m unittest discover -s tests -p 'test_stock_evaluation_routing.py'
.venv/bin/python -m unittest discover -s tests -p 'test_etf_evaluation.py'
.venv/bin/python -m unittest discover -s tests -p 'test_performance_chart.py'
.venv/bin/python -m unittest discover -s tests -p 'test_generic_factual_sources.py'
.venv/bin/python -m unittest discover -s tests -p 'test_quant_priority.py'
.venv/bin/python tests/test_freshness_detector.py
.venv/bin/python tests/test_followup_resolver.py
.venv/bin/python tests/test_message_router.py
.venv/bin/python tests/test_queue_coordinator.py
.venv/bin/python tests/test_response_formatter.py
```

Tests that require live providers or local services should be run separately after those dependencies have been configured.

## Recommended `.gitignore`

At minimum:

```gitignore
# Secrets
.env
.env.*
!.env.example

# Credential files
*.json

# Python
__pycache__/
*.py[cod]
.venv/
venv/

# Logs and generated runtime data
logs/
*.log

# macOS
.DS_Store

# Editors / tests
.vscode/
.idea/
.pytest_cache/
.coverage
```

If the repository contains non-secret JSON fixtures that must be tracked, replace the broad `*.json` rule with a rule targeting only the service-account credential file/path.

## Local Services

Current service roles are conceptually:

```text
Mac Mini
|
+-- Ollama
|    `-- local LLM generation
|
+-- Firecrawl / Docker
|    `-- current-page extraction
|
+-- Agentic_AI
|    +-- Hermes
|    +-- Telegram
|    +-- Discord
|    +-- SEC/FRED
|    +-- DDGS
|    `-- ETF scheduler
|
`-- network connection to Gaming PC
     `-- Quant / compute
```

## Key Tests

The checks below are grouped by feature. Some integration scripts require configured external services; use the CI/offline commands above for a repeatable local baseline.

### Core / Regression

```bash
.venv/bin/python tests/test_stock_agent_smoke.py
.venv/bin/python tests/test_process_request.py
.venv/bin/python tests/test_general_request.py
```

### Messaging

```bash
.venv/bin/python tests/test_message_router.py
.venv/bin/python tests/test_response_formatter.py
.venv/bin/python tests/test_messaging_pipeline.py
.venv/bin/python tests/test_telegram_bot.py
.venv/bin/python tests/test_discord_bot.py
```

### Current Information

```bash
.venv/bin/python tests/test_freshness_detector.py
.venv/bin/python tests/test_public_topic_news_backend.py
.venv/bin/python tests/test_live_market_provider_contract.py
.venv/bin/python tests/test_live_market_enrichment.py
.venv/bin/python tests/test_current_general_topic.py
.venv/bin/python tests/test_current_company_research.py
```

### Firecrawl

```bash
.venv/bin/python tests/test_firecrawl_health.py
.venv/bin/python tests/test_firecrawl_scrape.py
.venv/bin/python tests/test_ddgs_firecrawl_pipeline.py
```

### ETF Automation

```bash
.venv/bin/python tests/test_etf_update_config.py
```

Manual launchd validation:

```bash
launchctl kickstart -k \
  gui/$(id -u)/com.bunnyhouse.stockagent.etfupdate
```

## Running Telegram

With the environment loaded:

```bash
python -m integrations.messaging.telegram_bot
```

## Running Discord Questions

With the environment loaded:

```bash
python -m integrations.messaging.discord_bot
```

## Firecrawl Operations

Firecrawl infrastructure lives outside the Agentic_AI repository, for example under a dedicated Firecrawl directory on the Mac Mini.

Typical operational checks from the Firecrawl repository directory include:

```bash
docker compose ps
docker compose logs --tail=100 api
```

Agentic_AI validates the local service through its Firecrawl health/scrape tests.

## Phase 2 Backlog

Recommended Phase 2 work:

1. Shared Telegram-first priority queue for simultaneous interactive requests
2. Automatic service lifecycle for Telegram, Discord, and Firecrawl after Mac Mini restart/login
3. Enrich the 06:30 ETF report with a limited number of Firecrawl article extractions
4. Improve source diversity and duplicate-story suppression
5. Add conversation/follow-up context across Telegram and Discord
6. Add provider/service health monitoring and request-duration metrics
7. Tighten operational logging and alerting
8. Upgrade the Python runtime to remove current Python 3.9 / LibreSSL compatibility warnings

## Grounding Principles

This project follows several strict design rules:

- Never present general model memory as verified current information.
- Current claims require supplied timestamped evidence.
- SEC is preferred for supplied company-reported financial facts.
- FRED is preferred for supplied macroeconomic observations.
- Gaming PC outputs are explicitly model-derived quantitative evidence.
- DDGS discovers current material but is not the publisher.
- Firecrawl retrieves content but is not the publisher.
- The original publisher remains the web evidence source.
- If current evidence is unavailable, say so instead of inventing current events.
- Transport integrations should not contain finance, search, or analysis logic. Telegram and Discord should route messages into Hermes.

## Project State

Phase 1 establishes a local-first assistant capable of combining grounded financial analysis with best-effort current web retrieval while keeping the messaging, data, reasoning, and automation layers separated.

The next engineering phase should focus on reliability, always-on operation, shared priority orchestration, and incremental quality improvements rather than introducing new core routing architectures.
