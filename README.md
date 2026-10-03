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
| Gaming PC | Model-derived quantitative financial analysis |
| Public web search | Discovery of candidate public webpages |
| DDGS news | Current/recent news discovery |
| Firecrawl | Retrieval and extraction of selected webpages |
| Direct organization pages | First-party descriptions of organization products/services |
| Independent reporting/reference sources | External context for competition, scale, reputation and market position |
| Model knowledge | Background context only; not authoritative current evidence |

Search engines are discovery mechanisms. Firecrawl is a retrieval mechanism. Neither replaces the original publisher or webpage as the evidence source.

### Generic Evidence Standards

For ordinary descriptive generic questions, direct organization pages and reputable public references can support best-effort responses.

For competition, market position, scale, reputation, or growth potential, independent sources should receive greater weight than organization promotional claims.

Search-result titles/snippets may support discovery-level observations, but precise financial, legal, regulatory, valuation, market-share, revenue, employee-count, or other quantitative claims require stronger underlying evidence.

If relevant public evidence exists but does not support a precise numerical conclusion, the system should provide a qualified qualitative answer and state what could not be verified.

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
└── temp/
```

This avoids managed background-process permission problems on external volumes.

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

### Core / Regression

```bash
python tests/test_stock_agent_smoke.py
python tests/test_process_request.py
python tests/test_general_request.py
python tests/test_amzn_route_trace.py
```

### Company / Comparison

```bash
python tests/test_multi_company_detection.py
python tests/test_multi_company_executor.py
python tests/test_multi_company_research.py
python tests/test_multi_company_risk.py
python tests/test_comparison_first_turn_trace.py
python tests/test_conversation_context.py
python tests/test_followup_resolver.py
python tests/test_comparison_followup_routing.py
python tests/test_conversational_comparison.py
python tests/test_comparison_request_planner.py
python tests/test_question_aware_comparison.py
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
python tests/test_freshness_detector.py
python tests/test_public_topic_news_backend_live.py
python tests/test_live_market_provider_contract.py
python tests/test_live_market_enrichment.py
python tests/test_current_general_topic.py
python tests/test_current_company_research.py
```

### Firecrawl

```bash
python tests/test_firecrawl_health.py
python tests/test_firecrawl_scrape.py
python tests/test_ddgs_firecrawl_pipeline.py
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
python tests/test_etf_update_config.py
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
