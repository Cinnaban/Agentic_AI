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
            "market_snapshot":
                market_snapshot,
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
        holdings
    ):
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

            try:
                context = (
                    self.market_context_provider
                    .get_context(
                        company={
                            "name": ticker,
                            "ticker": ticker,
                            "entity_type":
                                "security"
                        }
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
                snapshots
        }