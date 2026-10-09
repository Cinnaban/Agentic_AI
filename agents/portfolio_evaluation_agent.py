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