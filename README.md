# Agentic AI / Stock Agent

A local-first agentic assistant centered on a Mac Mini, with a separate Gaming PC providing quantitative stock analysis. The project combines grounded financial research, generic public-web research, current web/news retrieval, conversational context, Telegram and Discord messaging, custom comparison analysis, and scheduled ETF reporting.

## Current Project Status

Phase 1 established the core orchestration, grounding, financial-analysis, messaging, and automation layers. The current build also includes a substantial Phase 2 conversational and multi-company research layer.

Validated or implemented capabilities include:

- Company/entity detection and request routing through Hermes
- Public-security analysis through a separate Gaming PC Quant service
- Sequential multi-company Quant requests, one security at a time
- Multi-company Research and Risk evidence collection
- Question-aware company comparisons
- Conversation context keyed by source, channel, and user
- Comparison follow-up resolution using remembered company scope
- Custom financial formula design plus deterministic evaluation
- SEC company facts and filing metadata
- FRED macroeconomic context
- Deterministic signal reconciliation
- Risk analysis and quality validation
- General-response handling for ordinary non-company questions
- Current-topic detection through `FreshnessDetector`
- DDGS current news discovery
- Public web discovery for generic/private-company research
- Local Firecrawl page extraction and Markdown enrichment
- Generic research planning across multiple targeted search queries
- Dynamic generic-research depth: `summary`, `standard`, and `deep`
- Pending conversation actions for deeper-research / summarized-version follow-ups
- Telegram messaging integration
- Discord Questions/Updates channel separation
- Daily ETF spreadsheet update and Discord Updates publishing
- macOS `launchd` automation

Single-company financial routing has been validated with approved responses and quality confidence of 95 in integration testing. Multi-company Quant, Research, and Risk coverage has also been exercised for comparison workflows.

## High-Level Architecture

```text
                           User
                            |
                +-----------+-----------+
                |                       |
            Telegram                  Discord
                |                       |
                +-----------+-----------+
                            |
                      MessageRouter
                            |
                          Hermes
                            |
      +---------------------+----------------------+
      |                     |                      |
   General              Generic / Current       Financial
   Question               Public Research        Question
      |                     |                      |
GeneralResponse      Freshness / Research       Company Detection
   Agent                  Planning                  |
                            |               public ticker available?
                            |                  /             \
                            |                yes             no
                            |                 |               |
                            |          Financial WorkPackage  Generic Research
                            |                 |
                            |        +--------+---------+
                            |        |        |         |
                            |      Quant     SEC/FRED  Research/Risk
                            |        |        |         |
                            |        +--------+---------+
                            |                 |
                            |      Comparison / Formula Layer
                            |                 |
                            +-----------------+
                                      |
                                Mac Mini synthesis
                                      |
                                  User response
```

## Systems

### Mac Mini

The Mac Mini is the primary orchestrator. It hosts or runs:

- Hermes orchestration
- Ollama model access
- Telegram integration
- Discord integration
- SEC and FRED providers
- DDGS web/news discovery
- Generic research planning
- Conversation context and follow-up state
- Comparison planning and synthesis
- Custom financial-formula design/evaluation orchestration
- Docker Desktop
- Self-hosted Firecrawl
- ETF update automation
- `launchd` scheduled and resident jobs

### Gaming PC

The Gaming PC handles quantitative analysis for public-company/security requests.

For multi-company work, the Mac Mini keeps one logical Hermes job but sends Quant requests sequentially, one security at a time. The Mac Mini then aggregates the returned evidence for per-company research, risk analysis, comparison, and final synthesis.

The Gaming PC does not own conversational logic or final response synthesis.

## Request Routing

### General Knowledge

Example:

```text
Explain compound interest
```

Route:

```text
Hermes
 -> GeneralResponseAgent
 -> response
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
 -> DDGS news discovery
 -> recency filter
 -> Firecrawl enrichment
 -> CurrentTopicAgent
 -> response
```

Current/latest/recent questions remain strict: if sufficiently recent evidence cannot be retrieved, the system should not represent stale model memory as current information.

### Generic / Private-Company Research

Examples:

```text
What is Yrefy?
What does Yrefy do?
Who are Yrefy's competitors?
Does Yrefy appear to have meaningful potential relative to competitors?
```

If an entity is identified as private or cannot be mapped safely to a public-market ticker, Hermes does not send the request to the Gaming PC financial pipeline.

Route:

```text
Hermes
 -> CompanyDetectionAgent
 -> no usable public ticker
 -> GenericResearchPlanner
 -> 1..5 targeted public-web queries
 -> PublicWebBackend
 -> URL deduplication
 -> GenericEvidenceProvider
 -> Firecrawl selected pages
 -> GenericEvidenceAgent
 -> brief qualified response
```

Generic research is intended for descriptive, competitive, qualitative, and best-effort public-information questions. Precise financial claims still require stronger evidence.

### Dynamic Generic Research Depth

Generic research supports three evidence depths:

```text
summary
 -> light discovery
 -> up to 2 Firecrawl page enrichments

standard
 -> normal planned research
 -> up to 6 Firecrawl page enrichments

deep
 -> broader planned research
 -> up to configured max page enrichments
```

The planner can choose the depth from the question context, and explicit user wording can request a deeper or summarized treatment.

After a generic research response, Hermes can maintain a pending conversational action such as:

```text
Would you like a deeper research?
```

or:

```text
Would you like a summarized version?
```

A follow-up such as `Yes`, `No`, `Go deeper`, or `Summarize that` is interpreted against the pending action rather than treated as an unrelated standalone query.

`ConversationContext` stores:

- recent messages
- active financial entities
- last intent/request
- pending action
- last generic research question, depth, plan, and evidence

### Public Company Analysis

Example:

```text
Analyze Nvidia
```

Route:

```text
Hermes
 -> CompanyDetectionAgent
 -> public ticker
 -> Gaming PC Quant
 -> SEC / FRED / Market Context
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

### Portfolio Evaluation

Portfolio holdings with percentage weights are classified individually using
Yahoo Finance quote/fund metadata and a small curated fallback for common ETF
tickers (including SCHD) before quant evaluation. Classified stocks and ETFs
are sent through their respective analysis paths; unresolved instruments are
identified as unclassified and are not silently treated as stocks. Portfolio
summaries report the stock/ETF mix, stated allocation totals, stock sector
classifications, separate ETF sector exposures, holding-level coverage, and
ETF fund profile data when available. Each portfolio response includes an
allocation bar chart by holding, colored by instrument type. ETF holdings are
not described with company operating or valuation metrics, and allocations
whose supplied weights do not total 100% are charted as stated rather than
normalized.
Supply holdings one per line, for example:

```text
NVDA 60%
SOXX 40%
```

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

Route combines financial evidence with the live/current retrieval layer:

```text
Hermes
 -> company detection
 -> FreshnessDetector
 -> Gaming PC Quant
 -> SEC / FRED
 -> DDGS current discovery
 -> recency filter
 -> Firecrawl
 -> Research / Risk / Quality
 -> response
```

### Multi-Company Comparison

Example:

```text
Compare Nvidia, Intel and AMD
```

Hermes preserves all detected companies in one logical WorkPackage.

```text
Hermes
 -> CompanyDetectionAgent
 -> NVDA + INTC + AMD
 -> ComparisonRequestPlanner
 -> AgentExecutor
      -> Quant AMD
      -> Quant NVDA
      -> Quant INTC
      -> Research per company
      -> Risk per company
 -> ComparisonAgent
 -> one comparative response
```

The Gaming PC Quant calls are sequential rather than one large multi-security remote batch.

### Question-Aware Comparisons

`ComparisonRequestPlanner` evaluates the user's actual question before evidence collection. It identifies requested dimensions such as:

- growth
- profitability
- financial strength
- valuation
- momentum
- risk

The plan can selectively indicate whether the comparison needs Quant, Research, Risk, or live information.

Examples:

```text
Which has the strongest profitability?
 -> profitability-focused comparison

Which has the strongest balance sheet?
 -> financial-strength-focused comparison

Compare growth, profitability and risk.
 -> multi-dimensional comparison
```

The final comparison prompt is instructed to answer the user's question first rather than always producing a fixed full-company template.

## Conversation Context

Conversation context is shared through Hermes rather than implemented separately in Telegram and Discord.

The conversation key is based on:

```text
source + channel_id + user_id
```

This allows the same user/session to carry scope across follow-up questions.

Example:

```text
Turn 1:
Compare Nvidia, Intel and AMD

Turn 2:
Which has the strongest balance sheet?
```

The second turn can recover `NVDA`, `INTC`, and `AMD` from conversation context while refreshing the relevant evidence for the new question.

Conversation memory is used to remember *what the user is talking about*, not as authoritative storage for current financial values.

## Custom Financial Formula Layer

For suitable financial-analysis comparisons, Hermes can create a transparent custom analytical framework for the specific question.

The formula architecture separates design from execution:

```text
Question
 -> ComparisonRequestPlanner
 -> company evidence
 -> FormulaMetricExtractor
 -> FinancialFormulaDesigner
 -> validated formula specification
 -> deterministic FormulaEvaluator
 -> scores / ranking
 -> ComparisonAgent synthesis
```

### Formula Opportunity

The comparison planner can classify formula use as:

```text
none
helpful
central
```

Examples:

```text
Which has the strongest profitability?
 -> none

Compare growth, profitability and risk.
 -> helpful

Which company is strongest overall?
 -> central
```

### Formula Safety Rules

- The language model designs the analytical framework but does not execute arbitrary code.
- Only metrics supplied by the evidence pipeline and allowed by the metric extractor may be used.
- Formula components include metric, weight, direction, and rationale.
- Deterministic application code performs normalization, weighting, scoring, and ranking.
- The response explains how the formula was created, why the selected metrics matter, why the formula is useful, and important limitations.
- A custom formula is an additional analytical lens, not an industry-standard model or investment guarantee.
- If formula generation or evaluation fails, the ordinary comparison remains available.

## Evidence Hierarchy

The project separates evidence by source and purpose.

| Source | Purpose |
|---|---|
| SEC | Company-reported financial facts and filing metadata |
| FRED | Macroeconomic observations |
| Gaming PC | Quantitative/model-derived financial analysis |
| Yahoo Finance ETF metadata | ETF quote type, fund profile, fees, assets, holdings, and sector weights |
| DDGS | Current web/news discovery |
| Firecrawl | Retrieval and extraction of selected web pages |
| Public web search | Discovery of candidate public webpages |
| DDGS news | Current/recent news discovery |
| Direct organization pages | First-party descriptions of organization products/services |
| Independent reporting/reference sources | External context for competition, scale, reputation and market position |
| Model knowledge | Background context only, not authoritative current evidence |

Search engines are discovery mechanisms. Firecrawl is a retrieval mechanism. Neither replaces the original publisher or webpage as the evidence source.

### Generic Evidence Standards

For ordinary descriptive generic questions, direct organization pages and reputable public references can support best-effort responses.

For competition, market position, scale, reputation, or growth potential, independent sources should receive greater weight than organization promotional claims.

Search-result titles/snippets may support discovery-level observations, but precise financial, legal, regulatory, valuation, market-share, revenue, employee-count, or other quantitative claims require stronger underlying evidence.

If relevant public evidence exists but does not support a precise numerical conclusion, the system should provide a qualified qualitative answer and state what could not be verified.

Research-backed responses include an evidence note with the UTC retrieval time, contributing publishers, and supplied publication dates where available. Financial analyses also identify available and unavailable evidence sources. Retrieval time indicates when this system gathered the evidence; it does not mean the underlying data itself is current. If live evidence cannot verify a current-information request, the response explicitly says so rather than falling back to model memory.

General factual answers search for the named subject's official website and
Wikipedia article first, retrieve a matching Wikipedia article directly when
available, and then use distinct public publishers for corroboration.
Irrelevant subject matches and social-platform results are excluded from
ordinary factual answers; Reddit/X evidence is retrieved only for explicit
community-discussion questions. Answers stay anchored to the user's question,
distinguish retrieved pages from search snippets, cite supplied source IDs,
and include direct source links so claims can be checked.
For direct "what/who/tell me about" questions, the bot builds a concise
summary from complete sentences copied from retrieved pages, including
notable games, projects, and achievements when the page explicitly names
them. Each point cites its source; the bot does not infer or invent missing
details. If it has only search snippets or incomplete page text, it says
which details it could not verify.

## Firecrawl

Firecrawl is self-hosted locally through Docker Desktop on the Mac Mini.

Current local configuration:

```text
FIRECRAWL_BASE_URL=http://localhost:3002
```

Two main retrieval patterns are used:

```text
Current question
 -> DDGS news discovery
 -> recency filter
 -> Firecrawl
 -> CurrentTopicAgent
```

and:

```text
Generic/private-company research
 -> GenericResearchPlanner
 -> public web discovery
 -> Firecrawl selected URLs
 -> GenericEvidenceAgent
```

Firecrawl health is checked before enrichment. The original webpage/publisher remains the evidence source.

## Messaging

### Telegram

Telegram is the higher-priority interactive transport.

Configured environment variable:

```text
TELEGRAM_BOT_TOKEN=
```

The listener:

1. receives a message,
2. normalizes it through `TelegramAdapter`,
3. routes it through `MessageRouter`,
4. processes it through Hermes,
5. formats/chunks the result,
6. replies to the originating Telegram chat.

Do not run a manual Telegram polling instance while the managed LaunchAgent instance is active; Telegram permits only one `getUpdates` consumer for the same bot token.

### Discord

Discord uses separate Questions and Updates channels:

```text
DISCORD_QUESTIONS_CHANNEL_ID=
DISCORD_UPDATES_CHANNEL_ID=
```

**Questions** routes interactive requests through Hermes.

**Updates** is reserved for scheduled/automated reports such as the ETF update.

The routing layer assigns:

```text
Telegram priority = 0
Discord priority  = 10
```

Lower numbers indicate higher routing priority.

No financial, formula, generic-research, or comparison logic should live in either transport. Both transports delegate those decisions to Hermes.

## Automated Bot Runtime

The Mac Mini can run Telegram and Discord through `launchd` LaunchAgents. Production bot launchers should:

- use the project root as the working directory,
- use the intended virtual-environment Python,
- expose the project through `PYTHONPATH`,
- use unbuffered Python output for readable runtime logs,
- run only one Telegram polling instance.

Useful production checks include:

```bash
launchctl list | grep bunnyhouse
```

and:

```bash
ps aux \
| grep -E 'telegram_bot|discord_bot' \
| grep -v grep
```

## Runtime Storage

Hermes job runtime state should use locally writable project storage rather than depending on an external `/Volumes/...` path for live requests.

Conceptual structure:

```text
runtime/hermes/
├── incoming/
├── processing/
├── completed/
├── failed/
├── archive/
├── temp/
└── cache/
```

This avoids managed background-process permission problems on external volumes.
The local cache stores successful quant results (24 hours), financial context
(12 hours), exact portfolio snapshots (12 hours), and available ETF fund
profiles (30 days). Requests marked current/latest bypass quant and financial
context caches. Cache lifetimes are capped at 90 days, and expired records are
removed at startup and when accessed. Portfolio cache files remain local,
under `runtime/hermes/cache/`, are excluded from Git, and are created with
owner-only directory permissions. Expired entries are swept at startup and
at least every 24 hours while the cache is in use. Volatile news, social, and
live-market evidence is not retained in reusable financial-context cache
entries.

## Daily ETF Update

`workers/etf_update.py` maintains the asset spreadsheet and publishes a
mixed stock/ETF market update to the Discord Updates channel.

The scheduled flow is:

```text
launchd
 -> run_etf_update.sh
 -> load .env
 -> Google Sheet refresh
 -> ticker classification (stock / ETF)
 -> yfinance metrics and latest quarterly statements
 -> ticker-specific news restricted to the last 48 hours
 -> Hermes summary
 -> appended unweighted ETF fund metrics and coverage
 -> Discord Updates
```

Each row is classified using Yahoo Finance quote type, with the existing
curated ETF registry as a fallback. Stock insights include market cap, cash
flow, EPS, EBITDA, liquidity and profitability ratios, growth indicators,
sector/industry, three-month price return, and the latest available quarterly
income, cash-flow, and balance-sheet values. ETF insights instead emphasize
fund assets, expense and distribution yields, beta, performance, sector
exposures, and top holdings; issuer-style EPS, EBITDA, operating cash flow,
and current ratio are not applicable to a fund.

Ticker-specific news is included only when it has a parseable publication
time within the prior 48 hours; undated stories are omitted. Same-industry
stocks in the sheet can be compared as a partial portfolio peer cohort, but
that cohort is not represented as an industry-wide benchmark. Portfolio
weights are not read from the sheet, so any aggregate metrics remain
unweighted. EPS and dividend-yield changes in the sheet summary are marked
green for increases and red for decreases.

The job is scheduled on the Mac Mini through `launchd` for:

```text
06:30 local Mac time, daily
```

Launcher:

```text
~/Agentic_AI/run_etf_update.sh
```

LaunchAgent:

```text
~/Library/LaunchAgents/com.bunnyhouse.stockagent.etfupdate.plist
```

## Environment Configuration

Real secrets and machine-specific values belong in `.env`. Do not commit `.env` or credential/service-account JSON files.

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

Non-secret application settings such as model names, Ollama endpoints, local runtime/logging paths, and system prompts can remain in application configuration.

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
credentials.json

# Python
__pycache__/
*.py[cod]
.venv/
venv/

# Logs and runtime state
logs/
runtime/
*.log

# macOS
.DS_Store

# Editors / tests
.vscode/
.idea/
.pytest_cache/
.coverage
```

Avoid ignoring every JSON file if the repository contains non-secret JSON fixtures that should remain versioned.

## Local Services

```text
Mac Mini
|
+-- Ollama
|    `-- local LLM generation
|
+-- Firecrawl / Docker
|    `-- webpage retrieval / Markdown extraction
|
+-- Agentic_AI
|    +-- Hermes
|    +-- ConversationContext
|    +-- Comparison / Formula planning
|    +-- Generic research planning
|    +-- Telegram
|    +-- Discord
|    +-- SEC / FRED
|    +-- DDGS / Public web discovery
|    `-- ETF scheduler
|
`-- LAN connection to Gaming PC
     `-- Quant / compute API
```

## Key Tests

The checks below are grouped by feature. Some integration scripts require configured external services; use the CI/offline commands above for a repeatable local baseline.

### Core / Regression

```bash
.venv/bin/python tests/test_stock_agent_smoke.py
.venv/bin/python tests/test_process_request.py
.venv/bin/python tests/test_general_request.py
.venv/bin/python tests/test_amzn_route_trace.py
```

### Company / Comparison

```bash
.venv/bin/python tests/test_message_router.py
.venv/bin/python tests/test_response_formatter.py
.venv/bin/python tests/test_messaging_pipeline.py
.venv/bin/python tests/test_telegram_bot.py
.venv/bin/python tests/test_discord_bot.py
.venv/bin/python tests/test_multi_company_detection.py
.venv/bin/python tests/test_multi_company_executor.py
.venv/bin/python tests/test_multi_company_research.py
.venv/bin/python tests/test_multi_company_risk.py
.venv/bin/python tests/test_comparison_first_turn_trace.py
.venv/bin/python tests/test_conversation_context.py
.venv/bin/python tests/test_followup_resolver.py
.venv/bin/python tests/test_comparison_followup_routing.py
.venv/bin/python tests/test_conversational_comparison.py
.venv/bin/python tests/test_comparison_request_planner.py
.venv/bin/python tests/test_question_aware_comparison.py
```

### Financial Formula

```bash
python tests/test_financial_formula_designer.py
python tests/test_formula_evaluator.py
python tests/test_formula_metric_extractor.py
python tests/test_custom_financial_formula_pipeline.py
```

### Generic / Private-Company Research

```bash
python tests/test_generic_web_backend.py
python tests/test_generic_research_planner.py
python tests/test_generic_research_pipeline.py
python tests/test_generic_research_answer.py
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

### Messaging

```bash
python tests/test_message_router.py
python tests/test_response_formatter.py
python tests/test_messaging_pipeline.py
python tests/test_telegram_bot.py
python tests/test_discord_bot.py
```

### ETF Automation

```bash
.venv/bin/python tests/test_etf_update_config.py
```

## Running Telegram

For manual debugging only, make sure the managed Telegram LaunchAgent is stopped first, then run from the project root:

```bash
cd ~/Agentic_AI
python -m integrations.messaging.telegram_bot
```

## Running Discord Questions

```bash
cd ~/Agentic_AI
python -m integrations.messaging.discord_bot
```

## Firecrawl Operations

Firecrawl infrastructure lives outside the Agentic_AI repository, for example under a dedicated Firecrawl directory on the Mac Mini.

Typical checks from the Firecrawl repository directory include:

```bash
docker compose ps
docker compose logs --tail=100 api
```

Agentic_AI validates the service through its Firecrawl health/scrape tests.

## Grounding Principles

- Never present general model memory as verified current information.
- Current claims require supplied recent/timestamped evidence.
- SEC is preferred for company-reported financial facts.
- FRED is preferred for macroeconomic observations.
- Gaming PC outputs are explicitly model-derived quantitative evidence.
- Search engines discover material but are not the publishers of claims.
- Firecrawl retrieves pages but is not the publisher.
- General factual responses prioritize a discovered official homepage,
  retrieve it through Firecrawl, and label any interpretation as based on
  that organization's own public-facing content. Retrieved claims remain
  source-cited; unsupported current-project claims are not inferred.
- The original publisher/page remains the web evidence source.
- Private or unresolved companies must not be assigned invented public tickers.
- No usable public ticker means no Gaming PC financial-model request.
- Generic research can use best-effort public evidence, but precise financial claims remain strict.
- Conversation memory stores scope and conversational state, not authoritative current financial values.
- Custom financial formulas must be transparent, restricted to supplied metrics, and deterministically evaluated.
- Transport integrations should contain no finance/search/research logic; Telegram and Discord should route messages into Hermes.

## Current Engineering Focus

The project has moved beyond the original Phase 1 routing architecture. Current engineering priorities are:

1. Stabilize dynamic generic-research depth and pending conversational actions.
2. Reuse deep generic evidence when the user asks only for a summarized version.
3. Persist conversation context if cross-restart continuity becomes necessary.
4. Add provider/service health monitoring and request-duration metrics.
5. Continue source-quality weighting and duplicate-result suppression.
6. Maintain always-on Telegram/Discord runtime reliability.
7. Upgrade the Python runtime to remove the current Python 3.9 / LibreSSL compatibility warning.
8. Incrementally harden comparison/formula quality scoring without weakening the proven single-company path.

## Project State

Stock Agent is now a local-first, multi-route assistant with distinct handling for general knowledge, strict current-information requests, generic/private-company public research, public-company financial analysis, and multi-company comparisons.

Hermes remains the central orchestration boundary. The Mac Mini decides what the user is asking, what evidence is required, whether a request belongs in the financial pipeline, how much generic public research is appropriate, and how the final answer should be synthesized. The Gaming PC remains a quantitative compute provider rather than a conversational or final-response engine.
