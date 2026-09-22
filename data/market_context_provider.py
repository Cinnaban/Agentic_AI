import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from data.news_provider import (
    NewsProvider
)
from data.providers.sec_provider import (
    SECProvider
)
from data.providers.sec_fact_builder import(
    SECFactBuilder
)
from data.providers.macro_provider import (
    MacroProvider
)
from data.providers.macro_fact_builder import (
    MacroFactBuilder
)
from data.providers.live_market_providers import (
    LiveMarketProvider
)
class MarketContextProvider:
    
    def __init__(self):
        self.news_provider = (
            NewsProvider()
        )
        self.sec_provider = (
            SECProvider()
        )
        self.sec_fact_builder = (
            SECFactBuilder()
        )
        self.macro_provider = (
            MacroProvider()
        )
        self.macro_fact_builder = (
            MacroFactBuilder()
        )
        self.live_market_provider = (
            LiveMarketProvider()
        )

    def _build_financial_context(
        self,
        analysis
    ):
        if not isinstance(
            analysis,
            dict
        ):
            return {}
        context = {
        "ticker":
            analysis.get("ticker"),

        "company_name":
            analysis.get("company_name"),

        "price":
            analysis.get("price"),

        "market_cap":
            analysis.get("market_cap"),

        "sector":
            analysis.get("sector"),

        "trailing_pe":
            analysis.get("trailing_pe"),

        "forward_pe":
            analysis.get("forward_pe"),

        "dividend_yield":
            analysis.get("dividend_yield"),

        "beta":
            analysis.get("beta"),

        "valuation_rating":
            analysis.get("valuation_rating"),

        "growth_rating":
            analysis.get("growth_rating"),

        "profitability_rating":
            analysis.get(
                "profitability_rating"
            ),

        "financial_strength_rating":
            analysis.get(
                "financial_strength_rating"
            ),

        "stability_rating":
            analysis.get(
                "stability_rating"
            ),

        "forecast_rating":
            analysis.get(
                "forecast_rating"
            ),

        "forecast_consensus":
            analysis.get(
                "forecast_consensus"
            ),

        "momentum_rating":
            analysis.get(
                "momentum_rating"
            ),

        "recommendation":
            analysis.get(
                "recommendation"
            ),

        "analysis_timestamp":
            analysis.get(
                "analysis_timestamp"
            )
    }   
        
        return {
            key: value
            for key, value
            in context.items()
            if value is not None
        }
            
    def get_context(
        self,
        company,
        quant_data=None,
        original_message=None,
        requires_live_data=False
    ):
        
# Variables
        financial_data = {}
        live_market_context = {
            "available":
                False,

            "query":
                original_message,

            "company":
                company,

            "results":
                [],

            "sources":
                []
        }
        if (
            requires_live_data
            and isinstance(
                original_message,
                str
            )
        ):

            live_market_context = (
                self.live_market_provider
                .get_context(
                    company=company,
                    query=original_message
                )
            )
        has_live_market_context = bool(
            isinstance(
                live_market_context,
                dict
            )
            and live_market_context.get(
                "available"
            )
            and live_market_context.get(
                "results"
            )
        )   
        sec_filings = []
        sec_facts = {}
        sec_fact_values = {}
        has_sec_facts = False

        macro = (
            self.macro_provider.get_context()
        )
        macro_facts = (
            self.macro_fact_builder.build(
                macro
            )
        )
        has_macro = bool(
            isinstance(
                macro_facts,
                dict
            )
            and any(
                macro_facts.values()
            )
        )
        news = (
            self.news_provider.get_news(
                company
            )
        )
        sec_filings = (
            self.sec_provider
            .normalize_recent_filings(
                company=company,
                limit=5
            )
        )
        raw_sec_facts = (
            self.sec_provider
            .get_company_facts(
                company
            )
        )

        sec_facts = (
            self.sec_fact_builder.build(
                raw_sec_facts
            )
        )

        sec_fact_values = (
            sec_facts.get(
                "facts",
                {}
            )
        )

        has_sec_facts = bool(
            sec_fact_values
        )
        
        if isinstance(
            quant_data,
            dict
        ):
            quant_results = quant_data.get(
                "results",
                []
            )
            if (
                isinstance(
                    quant_results,
                    list
                )
                and quant_results
            ):
                first_result = (
                    quant_results[0]
                )
                if isinstance(
                    first_result,
                    dict
                ):
                    analysis = first_result.get(
                        "analysis",
                        {}
                    )
                    if isinstance(
                        analysis,
                        dict
                    ):
                        financial_data = (
                            self._build_financial_context(
                                analysis
                            )
                        )
 
        return {
            "company": 
                company,
            "financial_data": 
                financial_data,
            "sec_facts":
                sec_facts,
            "sec_filings": 
                sec_filings,
            "macro":
                macro,
            "macro_facts":
                macro_facts,
            "live_market_context":
                live_market_context,
            "news": 
                news,
            "sentiment_sources": [],
            "source_status": {
                "financial_data": (
                        "available"
                        if financial_data
                        else "unavailable"
                    ),
                "sec_facts": (
                    "available"
                    if has_sec_facts
                    else "unavailable"
                ),
                "sec_filings": (
                    "available"
                    if sec_filings
                    else "unavailable"
                ),
                "macro": (
                    "available"
                    if has_macro
                    else "unavailable"
                ),
                "live_market_context": (
                    "available"
                    if has_live_market_context
                    else "unavailable"
                ),
                "news": (
                    "available"
                    if news
                    else "unavailable"
                ),
                "sentiment_sources": "unavailable",
                "source_metadata": {
                    "financial_data": [],
                    "news": [],
                    "filings": [],
                    "macro": [],
                    "live_market_context": []
                }
            }
        }