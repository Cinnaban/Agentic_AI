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
        context,
        holding
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

        entity_type = holding.get("entity_type", "unresolved")
        etf_context = holding.get("etf_context", {})
        if not isinstance(etf_context, dict):
            etf_context = {}

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
        if entity_type == "etf":
            financial_summary = {
                key: financial_summary[key]
                for key in (
                    "price",
                    "dividend_yield",
                    "beta"
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
            "status":
                "available"
                if available_financial_fields
                else "unavailable",
            "available_fields":
                available_financial_fields,
            "missing_fields":
                missing_financial_fields
        }
        
        return {
            "ticker":
                ticker,
            "entity_type":
                entity_type,
            "classification_status":
                holding.get(
                    "classification_status",
                    "unavailable"
                ),
            "classification_error":
                holding.get("classification_error"),
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
                key: financial_summary.get(key)
                for key in financial_summary
            },
            "financial_availability":
                financial_availability,
            "etf_context": {
                key: etf_context.get(key)
                for key in (
                    "fund_overview",
                    "asset_classes",
                    "sector_weightings",
                    "top_holdings",
                    "status"
                )
                if etf_context.get(key) not in (None, [], {})
            } if entity_type == "etf" else {},
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
            entity_type = holding.get("entity_type", "unresolved")
            if entity_type not in {"stock", "etf"}:
                snapshots.append({
                    "ticker": ticker,
                    "weight": weight,
                    "entity_type": "unresolved",
                    "classification_status": holding.get(
                        "classification_status",
                        "unavailable"
                    ),
                    "classification_error": holding.get(
                        "classification_error"
                    ),
                    "financial_summary": {},
                    "financial_availability": {
                        "status": "unavailable",
                        "available_fields": [],
                        "missing_fields": []
                    },
                    "social": {"status": "unavailable"}
                })
                continue

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
                                entity_type,
                            "etf_context":
                                holding.get("etf_context")
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
                        "entity_type":
                            entity_type,
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
                    context=context,
                    holding=holding
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
        market_context_count = sum(
            1
            for snapshot in snapshots
            if (
                snapshot.get("entity_type") in {"stock", "etf"}
                and snapshot.get("status") != "failed"
            )
        )
        
        return {
            "status":
                "available"
                if market_context_count
                else "unavailable",

            "holding_count":
                len(holdings),

            "researched_count":
                market_context_count,

            "context_limited":
                was_truncated,

            "holdings":
                snapshots,
                
            "financial_coverage": {
                "available_count":
                    financial_snapshots_available,
                "researched_count":
                    market_context_count
            },
        }