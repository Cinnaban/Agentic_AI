import json

from agents.ollama_client import (
    OllamaClient
)
from configs.config import Config


class PortfolioEvaluationAgent:

    def __init__(self):
        self.ollama = OllamaClient()

    def _build_holding_coverage(
        self,
        portfolio_context
    ):
        if not isinstance(
            portfolio_context,
            dict
        ):
            return ""

        researched_holdings = (
            portfolio_context.get(
                "holdings",
                []
            )
        )

        if not isinstance(
            researched_holdings,
            list
        ):
            return ""

        if not researched_holdings:
            return ""

        lines = [
            "Holding Coverage"
        ]

        for holding in researched_holdings:
            if not isinstance(
                holding,
                dict
            ):
                continue

            ticker = str(
                holding.get(
                    "ticker",
                    ""
                )
                or ""
            ).strip().upper()

            if not ticker:
                continue

            company_name = str(
                holding.get(
                    "company_name",
                    ""
                )
                or ""
            ).strip()

            weight = holding.get(
                "weight"
            )

            financial_summary = (
                holding.get(
                    "financial_summary",
                    {}
                )
            )

            if not isinstance(
                financial_summary,
                dict
            ):
                financial_summary = {}

            social = holding.get(
                "social",
                {}
            )

            if not isinstance(
                social,
                dict
            ):
                social = {}

            identity = ticker

            if (
                company_name
                and company_name.upper()
                != ticker
            ):
                identity = (
                    f"{company_name} ({ticker})"
                )

            heading = f"- {identity}"

            if weight is not None:
                heading += (
                    f" — Weight: {weight}%"
                )

            lines.append(
                heading
            )

            financial_labels = {
                "price":
                    "Price",
                "sector":
                    "Sector",
                "market_cap":
                    "Market Cap",
                "trailing_pe":
                    "Trailing P/E",
                "forward_pe":
                    "Forward P/E",
                "dividend_yield":
                    "Dividend Yield",
                "beta":
                    "Beta",
                "valuation_rating":
                    "Valuation",
                "growth_rating":
                    "Growth",
                "profitability_rating":
                    "Profitability",
                "financial_strength_rating":
                    "Financial Strength",
                "stability_rating":
                    "Stability",
                "momentum_rating":
                    "Momentum"
            }

            financial_items = []

            for key, label in (
                financial_labels.items()
            ):
                value = financial_summary.get(
                    key
                )

                if value in {
                    None,
                    "",
                    "unavailable"
                }:
                    continue

                financial_items.append(
                    f"{label}: {value}"
                )

            if financial_items:
                lines.append(
                    "  "
                    + " | ".join(
                        financial_items
                    )
                )
            else:
                lines.append(
                    "  Brief financial metrics "
                    "were unavailable."
                )

            social_status = social.get(
                "status",
                "unavailable"
            )

            social_themes = social.get(
                "discussion_themes",
                []
            )

            if not isinstance(
                social_themes,
                list
            ):
                social_themes = []

            clean_themes = [
                str(theme)
                for theme in social_themes
                if theme
            ][:3]

            if clean_themes:
                lines.append(
                    "  Social themes: "
                    + ", ".join(
                        clean_themes
                    )
                )
            elif social_status in {
                "available",
                "limited"
            }:
                lines.append(
                    "  Social evidence was retrieved, "
                    "but no reliable themes were found."
                )
            else:
                lines.append(
                    "  Social evidence was unavailable."
                )

        holding_count = portfolio_context.get(
            "holding_count",
            len(researched_holdings)
        )

        researched_count = (
            portfolio_context.get(
                "researched_count",
                len(researched_holdings)
            )
        )

        lines.append("")
        lines.append(
            "Coverage: "
            f"{researched_count} of "
            f"{holding_count} holdings researched."
        )

        if portfolio_context.get(
            "context_limited",
            False
        ):
            lines.append(
                "Research context was limited by "
                "the configured holding maximum."
            )

        return "\n".join(
            lines
        )

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

PORTFOLIO NARRATIVE:

A complete deterministic holding-by-holding
coverage section will be added separately.

Do not create a ticker table and do not repeat
the entire holding list.

Use the supplied holding-level context to
produce portfolio-wide observations about:

- concentration
- weight distribution
- sector concentration
- valuation patterns
- growth versus value characteristics
- financial-strength patterns
- diversification
- social signals
- potential selection methodology
- material evidence limitations

Mention individual holdings only when they
materially support a portfolio-wide conclusion.

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

        holding_coverage = (
            self._build_holding_coverage(
                portfolio_context
            )
        )

        response_sections = []

        if holding_coverage:
            response_sections.append(
                holding_coverage
            )

        if model_response:
            response_sections.append(
                model_response
            )

        final_response = "\n\n".join(
            response_sections
        )

        result = {
            "status":
                "completed",
            "response":
                final_response
        }

        if Config.DEBUG:
            result[
                "portfolio_context"
            ] = portfolio_context

        return result