import json

from agents.ollama_client import (
    OllamaClient
)
from configs.config import Config


class PortfolioEvaluationAgent:

    def __init__(self):
        self.ollama = OllamaClient()

    @staticmethod
    def _build_portfolio_overview(holdings):
        if not isinstance(holdings, list) or not holdings:
            return ""

        counts = {
            "stock": 0,
            "etf": 0,
            "unresolved": 0
        }
        weights = {
            "stock": 0.0,
            "etf": 0.0,
            "unresolved": 0.0
        }
        stock_sector_weights = {}
        has_weight = False

        for holding in holdings:
            if not isinstance(holding, dict):
                continue
            entity_type = holding.get("entity_type", "unresolved")
            if entity_type not in counts:
                entity_type = "unresolved"
            counts[entity_type] += 1

            weight = holding.get("weight")
            if isinstance(weight, (int, float)) and not isinstance(
                weight,
                bool
            ):
                weights[entity_type] += weight
                has_weight = True
                sector = holding.get("sector")
                if entity_type == "stock" and isinstance(sector, str):
                    sector = sector.strip()
                    if sector:
                        stock_sector_weights[sector] = (
                            stock_sector_weights.get(sector, 0.0) + weight
                        )

        lines = [
            "Portfolio Composition",
            (
                f"- Holding mix: {counts['stock']} "
                f"{'stock' if counts['stock'] == 1 else 'stocks'}, "
                f"{counts['etf']} "
                f"{'ETF' if counts['etf'] == 1 else 'ETFs'}, "
                f"{counts['unresolved']} unclassified."
            )
        ]
        if has_weight:
            total_weight = sum(weights.values())
            lines.append(
                "- Stated allocation: "
                f"stocks {weights['stock']:.2f}%, "
                f"ETFs {weights['etf']:.2f}%, "
                f"unclassified {weights['unresolved']:.2f}% "
                f"(total {total_weight:.2f}%)."
            )
            if abs(total_weight - 100.0) > 0.01:
                lines.append(
                    "- Listed weights do not total 100%; "
                    "allocation percentages are not normalized."
                )
        else:
            lines.append(
                "- Allocation weights were not supplied, so "
                "portfolio-wide allocation percentages cannot be "
                "calculated."
            )
        if counts["unresolved"]:
            lines.append(
                "- Unclassified holdings are excluded from stock/ETF "
                "comparisons until their instrument type can be verified."
            )
        if stock_sector_weights:
            sector_summary = ", ".join(
                f"{sector} {weight:.2f}%"
                for sector, weight in sorted(
                    stock_sector_weights.items(),
                    key=lambda item: item[1],
                    reverse=True
                )
            )
            lines.append(
                "- Stock sector classification by stated portfolio weight: "
                + sector_summary
                + "."
            )
        elif counts["stock"]:
            lines.append(
                "- Stock sector classification is unavailable from the "
                "retrieved instrument metadata."
            )

        etf_sector_summaries = []
        for holding in holdings:
            if (
                not isinstance(holding, dict)
                or holding.get("entity_type") != "etf"
            ):
                continue
            fund_data = holding.get("etf_context", {})
            if not isinstance(fund_data, dict):
                continue
            sector_weightings = fund_data.get("sector_weightings", {})
            if not isinstance(sector_weightings, dict) or not sector_weightings:
                continue
            sector_parts = []
            for sector, value in sorted(
                sector_weightings.items(),
                key=lambda item: (
                    item[1] if isinstance(item[1], (int, float)) else -1
                ),
                reverse=True
            )[:4]:
                if isinstance(value, (int, float)):
                    sector_parts.append(f"{sector} {value * 100:.1f}%")
                elif value not in (None, ""):
                    sector_parts.append(f"{sector} {value}")
            if sector_parts:
                ticker = str(holding.get("ticker", "")).upper()
                etf_sector_summaries.append(
                    f"{ticker}: " + ", ".join(sector_parts)
                )
        if etf_sector_summaries:
            lines.append(
                "- ETF reported sector exposures (per fund; not added to "
                "portfolio stock-sector weights): "
                + "; ".join(etf_sector_summaries)
                + "."
            )
        elif counts["etf"]:
            lines.append(
                "- ETF sector exposures are unavailable from the retrieved "
                "fund profiles."
            )
        return "\n".join(lines)

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
            entity_type = holding.get(
                "entity_type",
                "unresolved"
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
            heading += (
                " (ETF)"
                if entity_type == "etf"
                else " (Stock)"
                if entity_type == "stock"
                else " (Type unverified)"
            )

            if weight is not None:
                heading += (
                    f" — Weight: {weight}%"
                )

            lines.append(
                heading
            )

            if holding.get("status") == "failed":
                lines.append(
                    "  Market-context retrieval failed for this holding."
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
            if entity_type == "etf":
                financial_labels = {
                    "price": "Price",
                    "dividend_yield": "Distribution Yield",
                    "beta": "Beta"
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

            if entity_type == "etf":
                etf_context = holding.get("etf_context", {})
                if not isinstance(etf_context, dict):
                    etf_context = {}
                fund_overview = etf_context.get("fund_overview", {})
                asset_classes = etf_context.get("asset_classes", {})
                sector_weightings = etf_context.get(
                    "sector_weightings",
                    {}
                )
                top_holdings = etf_context.get("top_holdings", [])
                profile_items = []
                if isinstance(asset_classes, dict):
                    profile_items.extend(
                        str(name)
                        for name, value in asset_classes.items()
                        if value not in (None, "", 0, 0.0)
                    )
                if isinstance(sector_weightings, dict):
                    sectors = []
                    for sector, weight in sector_weightings.items():
                        if not isinstance(weight, (int, float)):
                            continue
                        sectors.append(f"{sector} {weight * 100:.1f}%")
                    if sectors:
                        profile_items.append(
                            "sector exposures: " + ", ".join(sectors[:4])
                        )
                if isinstance(fund_overview, dict):
                    for key in ("category", "legalType", "family"):
                        value = fund_overview.get(key)
                        if value:
                            profile_items.append(f"{key}: {value}")
                if isinstance(top_holdings, list):
                    names = []
                    for item in top_holdings[:3]:
                        if not isinstance(item, dict):
                            continue
                        name = item.get("holdingName") or item.get("symbol")
                        if name:
                            names.append(str(name))
                    if names:
                        profile_items.append(
                            "reported top holdings: " + ", ".join(names)
                        )
                if profile_items:
                    lines.append(
                        "  ETF profile (Yahoo Finance): "
                        + "; ".join(profile_items[:4])
                    )

            classification_status = holding.get(
                "classification_status"
            )
            if classification_status == "not_evaluated_limit":
                lines.append(
                    "  Instrument classification skipped at the "
                    "configured holding limit."
                )
            elif classification_status in {"unavailable", "unresolved"}:
                lines.append(
                    "  Instrument type could not be verified."
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
            "Market-context coverage: "
            f"{researched_count} of "
            f"{holding_count} holdings."
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

        if not any(
            isinstance(holding, dict)
            and str(holding.get("ticker", "")).strip()
            for holding in holdings
        ):
            return {
                "status": "completed",
                "response": (
                    "I couldn't identify portfolio holdings. Please provide "
                    "one ticker and its portfolio weight per line, for "
                    "example: NVDA 60%."
                )
            }

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
- the split between stock and ETF exposure
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

Treat stocks and ETFs as different instruments.
Do not treat an ETF as an operating company or apply
company-level profitability, valuation, or growth
conclusions to the fund itself. ETF profile and
underlying holdings may only be described when those
fields are explicitly present in the supplied data.
Do not infer diversification merely from holding
multiple ETFs; overlapping exposure must be supported
by the supplied holdings or sector data.

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

Do not create a ticker table or repeat holding-level
metrics; the coverage section is included separately.

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

        portfolio_overview = self._build_portfolio_overview(
            holdings
        )
        if portfolio_overview:
            response_sections.append(portfolio_overview)

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