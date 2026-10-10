import json

from agents.ollama_client import (
    OllamaClient
)
from configs.config import Config


class PortfolioEvaluationAgent:

    def __init__(self):
        self.ollama = OllamaClient()

    def analyze(
        self,
        message,
        holdings,
        portfolio_context=None
    ):
        if not isinstance(
            holdings,
            list
        ):
            holdings = []

        if not isinstance(
            portfolio_context,
            dict
        ):
            portfolio_context = {}

        prompt = f"""
You are a descriptive portfolio research assistant.

The user supplied a portfolio and asked for an
evaluation or an explanation of how the holdings
may have been selected.

Your task is to describe observable portfolio
characteristics and plausible selection patterns.

Discuss when supported by the supplied information:

- concentration and weight distribution
- recurring business or market themes
- possible sector or industry exposure
- diversification characteristics
- possible factor or investment-style tilts
- recurring market-context signals
- public-discussion themes
- important limitations in the available evidence

Never claim that an inferred selection process is
certain. Clearly label selection explanations as
hypotheses.

Do not provide personalized financial advice.

Do not provide buy, sell, or hold instructions.

Do not provide price targets.

Do not claim that public discussion is verified
financial evidence.

If market or social context is unavailable, state
that limitation rather than inventing information.

If sector information is available,
identify recurring sectors.

If sector information is unavailable,
state that explicitly.

Focus primarily on:
- concentration
- weighting
- diversification
- thematic exposure
- selection hypotheses

PORTFOLIO FUNDAMENTALS:

- Summarize every holding.
- If a holding has financial data:
    include a brief financial snapshot.
- If a holding lacks financial data:
    include a brief missing-data summary.
- Do not ignore holdings simply because
financial metrics are unavailable.
- For every holding, provide a very short
financial snapshot using only supplied data.

Use this format when data exists:

TICKER
- Price:
- Sector:
- Market Cap:
- Trailing P/E:
- Forward P/E:
- Dividend Yield:
- Valuation:
- Growth:
- Financial Strength:
- Momentum:

In a compact coverage table.

Do not show fields whose values are null,
missing, unavailable, or empty.

If some financial fields are missing, add
one short sentence under that holding:

"Additional valuation or operating metrics
were not available in the retrieved snapshot."

Do not repeat a long list of every missing
field unless the absence materially affects
the portfolio conclusion.

After the holding snapshots, discuss:

- concentration
- weight distribution
- sector concentration
- valuation patterns
- growth versus value characteristics
- financial-strength patterns
- diversification
- social signals
- selection hypotheses
- material evidence limitations

Use market and financial evidence before
social discussion when both are available.

Social themes are supplemental evidence only.

Do not infer sector, financial strength,
valuation, growth, or profitability from
ticker identity or social keywords.

USER REQUEST:

{message}

PARSED HOLDINGS:

{json.dumps(
    holdings,
    indent=2
)}

BRIEF MARKET AND SOCIAL CONTEXT:

{json.dumps(
    portfolio_context,
    indent=2
)}
"""

        response = self.ollama.generate(
            prompt,
            model=(
                Config.PORTFOLIO_EVALUATION_MODEL
            )
        )

        if not isinstance(
            response,
            dict
        ):
            return {
                "status": "failed",
                "response": (
                    "Portfolio context could not "
                    "be summarized."
                )
            }

        model_response = str(
            response.get(
                "response",
                ""
            )
            or ""
        ).strip()

        if not model_response:
            return {
                "status": "failed",
                "response": (
                    "Portfolio context could not "
                    "be summarized."
                )
            }

        result = {
            "status": "completed",
            "response": model_response
        }

        if Config.DEBUG:
            result[
                "portfolio_context"
            ] = portfolio_context

        return result