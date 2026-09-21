# Stock Agent

Local agentic equity research and market-analysis system.

## Data Sources

- Gaming PC quantitative analysis
- SEC company facts
- SEC filing metadata
- FRED macroeconomic data
- Optional public RSS news

## Agents

- Research
- Sentiment
- Quant
- Risk
- Quality

## Grounding

Research uses:
- SEC-reported financial facts
- quantitative analysis
- FRED macroeconomic facts

Sentiment uses verified news/sentiment evidence when available.
When those sources are unavailable, verified sentiment is reported
as unavailable rather than inferred.

## Environment

Required:

FRED_API_KEY
SEC_USER_AGENT

Copy:

.env.example

to:

.env

and populate the local values.

## News

Live RSS is optional.

Production configuration:

data/news_feeds.py

Default MVP configuration:

NEWS_FEEDS = []

## Testing

Core release tests:

python test_sec_health.py
python test_macro_provider.py
python test_signal_reconciliation.py
python test_grounded_sentiment.py
python test_grounded_risk.py
python test_quality_context.py
python test_stock_agent_smoke.py
python test_process_request.py