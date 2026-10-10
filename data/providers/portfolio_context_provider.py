from configs.config import Config
from data.market_context_provider import (
    MarketContextProvider
)


class PortfolioContextProvider:

    def __init__(self):
        self.market_context_provider = (
            MarketContextProvider()
        )

    def _brief_snapshot(
        self,
        ticker,
        weight,
        context
    ):
        if not isinstance(
            context,
            dict
        ):
            context = {}
            
        company_data = (
            context.get(
                "company",
                {}
            )
        )

        if not isinstance(
            company_data,
            dict
        ):
            company_data = {}
            

        source_status = context.get(
            "source_status",
            {}
        )

        if not isinstance(
            source_status,
            dict
        ):
            source_status = {}

        social_summary = context.get(
            "social_summary",
            {}
        )

        if not isinstance(
            social_summary,
            dict
        ):
            social_summary = {}

        market_snapshot = (
            context.get(
                "market_snapshot"
            )
            or context.get(
                "market_data"
            )
            or context.get(
                "financial_data"
            )
            or {}
        )

        if not isinstance(
            market_snapshot,
            dict
        ):
            market_snapshot = {}


        financial_summary = {
            "price":
                market_snapshot.get(
                    "price"
                ),
            "sector":
                market_snapshot.get(
                    "sector"
                ),
            "market_cap":
                market_snapshot.get(
                    "market_cap"
                ),
            "trailing_pe":
                market_snapshot.get(
                    "trailing_pe"
                ),
            "forward_pe":
                market_snapshot.get(
                    "forward_pe"
                ),
            "dividend_yield":
                market_snapshot.get(
                    "dividend_yield"
                ),
            "beta":
                market_snapshot.get(
                    "beta"
                ),
            "valuation_rating":
                market_snapshot.get(
                    "valuation_rating"
                ),
            "growth_rating":
                market_snapshot.get(
                    "growth_rating"
                ),
            "profitability_rating":
                market_snapshot.get(
                    "profitability_rating"
                ),
            "financial_strength_rating":
                market_snapshot.get(
                    "financial_strength_rating"
                ),
            "stability_rating":
                market_snapshot.get(
                    "stability_rating"
                ),
            "momentum_rating":
                market_snapshot.get(
                    "momentum_rating"
                )
        }
        
        available_financial_fields = [
            key
            for key, value
            in financial_summary.items()
            if value is not None
        ]

        missing_financial_fields = [
            key
            for key, value
            in financial_summary.items()
            if value is None
        ]
        
        financial_availability = {
            "available_fields":
                available_financial_fields,
            "missing_fields":
                missing_financial_fields
        }
        
        return {
            "ticker":
                ticker,
            "company_name":(
                company_data.get(
                    "company_name"
                )
                or company_data.get(
                    "name"
                )
                or ticker
            ),
            "weight":
                weight,
            "source_status":
                source_status,
            "financial_summary": {
                "price":
                    market_snapshot.get(
                        "price"
                    ),

                "sector":
                    market_snapshot.get(
                        "sector"
                    ),

                "market_cap":
                    market_snapshot.get(
                        "market_cap"
                    ),

                "trailing_pe":
                    market_snapshot.get(
                        "trailing_pe"
                    ),

                "forward_pe":
                    market_snapshot.get(
                        "forward_pe"
                    ),

                "dividend_yield":
                    market_snapshot.get(
                        "dividend_yield"
                    ),

                "beta":
                    market_snapshot.get(
                        "beta"
                    ),

                "valuation_rating":
                    market_snapshot.get(
                        "valuation_rating"
                    ),

                "growth_rating":
                    market_snapshot.get(
                        "growth_rating"
                    ),

                "profitability_rating":
                    market_snapshot.get(
                        "profitability_rating"
                    ),

                "financial_strength_rating":
                    market_snapshot.get(
                        "financial_strength_rating"
                    ),

                "stability_rating":
                    market_snapshot.get(
                        "stability_rating"
                    ),

                "momentum_rating":
                    market_snapshot.get(
                        "momentum_rating"
                    )
            },
            "social": {
                "status":
                    social_summary.get(
                        "status",
                        "unavailable"
                    ),
                "discussion_volume":
                    social_summary.get(
                        "discussion_volume"
                    ),
                "platforms":
                    social_summary.get(
                        "platforms",
                        []
                    ),
                "discussion_themes":
                    social_summary.get(
                        "discussion_themes",
                        []
                    )[:5]
            }
        }

    def get_context(
        self,
        holdings,
        quant_data_by_ticker=None
    ):
        
        if not isinstance(
            quant_data_by_ticker,
            dict
        ):
            quant_data_by_ticker = {}
        
        if not isinstance(
            holdings,
            list
        ):
            return {
                "status": "unavailable",
                "holdings": []
            }

        max_holdings = int(
            getattr(
                Config,
                "PORTFOLIO_CONTEXT_MAX_HOLDINGS",
                10
            )
        )
        was_truncated = (
            len(holdings)
            > max_holdings
        )

        snapshots = []

        for holding in holdings[
            :max_holdings
        ]:
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
            ).strip().upper()

            if not ticker:
                continue

            weight = holding.get(
                "weight"
            )

            quant_data = (
                quant_data_by_ticker.get(
                    ticker
                )
            )

            try:
                context = (
                    self.market_context_provider
                    .get_context(
                        company={
                            "name":
                                ticker,
                            "ticker":
                                ticker,
                            "entity_type":
                                "security"
                        },
                        quant_data=quant_data,
                        original_message=(
                            "Brief portfolio financial "
                            f"context for {ticker}"
                        ),
                        requires_live_data=False
                    )
                )
                
            except Exception as error:
                snapshots.append(
                    {
                        "ticker":
                            ticker,
                        "weight":
                            weight,
                        "status":
                            "failed",
                        "error":
                            str(error)
                    }
                )
                continue

            snapshots.append(
                self._brief_snapshot(
                    ticker=ticker,
                    weight=weight,
                    context=context
                )
            )

        financial_snapshots_available = sum(
            1
            for snapshot in snapshots
            if (
                isinstance(
                    snapshot,
                    dict
                )
                and snapshot.get(
                    "financial_availability",
                    {}
                ).get(
                    "status"
                ) == "available"
            )
        )
        
        return {
            "status":
                "available"
                if snapshots
                else "unavailable",

            "holding_count":
                len(holdings),

            "researched_count":
                len(snapshots),

            "context_limited":
                was_truncated,

            "holdings":
                snapshots,
                
            "financial_coverage": {
                "available_count":
                    financial_snapshots_available,
                "researched_count":
                    len(snapshots)
            },
        }