import sys
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))
    
from agents.ollama_client import OllamaClient
from configs.config import Config


class SentimentAgent:

    def __init__(self):

        self.ollama = OllamaClient()

    def analyze(
        self,
        company,
        market_context=None
    ):
        if market_context is None:
            market_context = {
                "financial_data": {},
                "sec_facts": {},
                "sec_filings": [],
                "macro_facts": {},
                "news": [],
                "sentiment_sources": [],
                "source_status": {}
            }

        source_status = market_context.get(
            "source_status",
            {}
        )

        news_available = (
            source_status.get(
                "news"
            ) == "available"
        )

        sentiment_available = (
            source_status.get(
                "sentiment_sources"
            ) == "available"
        )

        if (
            not news_available
            and not sentiment_available
        ):

            return {
                "status":
                    "unavailable",

                "verified_sentiment":
                    "unavailable",

                "bullish_factors":
                    [],

                "bearish_factors":
                    [],

                "summary": (
                    "Verified current investor sentiment "
                    "is unavailable because current news "
                    "and sentiment sources are unavailable."
                )
            }

        sentiment_context = {
            "company":
                company,

            "news":
                market_context.get(
                    "news",
                    []
                ),

            "sentiment_sources":
                market_context.get(
                    "sentiment_sources",
                    []
                ),

            "source_status": {
                "news":
                    source_status.get(
                        "news"
                    ),

                "sentiment_sources":
                    source_status.get(
                        "sentiment_sources"
                    )
            }
        }
        
        prompt = f"""
                        
        Provide market sentiment analysis for:
        {company}

        Sentiment Evidence:

        {json.dumps(
            sentiment_context,
            indent=2
        )}

        Include:

        - Bullish factors
        - Bearish factors
        - Investor sentiment

        EVIDENCE RULES:

        - Sentiment Evidence is the only evidence source for this task.

        - Do not use general model knowledge as current sentiment evidence.

        - Do not invent news, surveys, index performance, analyst views,
        social-media activity, investor positioning, or market statistics.

        - News articles may be analyzed only when supplied in news.

        - Sentiment metrics may be analyzed only when supplied in
        sentiment_sources.

        - Do not infer investor sentiment from SEC facts, financial ratios,
        quantitative model outputs, FRED macroeconomic data, or general
        company knowledge.

        - Clearly distinguish evidence from interpretation.

        - If the supplied evidence is insufficient to determine sentiment,
        explicitly state that sentiment remains uncertain.

        GROUNDING RULES:

        - Current sentiment must be based on supplied Market Context.

        - Do not invent recent news.

        - Do not describe historical acquisitions, earnings, shortages,
        regulatory events, or market conditions as current unless they
        appear in Market Context.

        - If news is unavailable, do not claim to know current news
        sentiment.

        - If sentiment_sources are unavailable, explicitly state that
        verified current sentiment sources are unavailable.

        - General qualitative observations may still be provided, but
        they must be labeled as general context rather than current
        verified sentiment.

"""

        response = self.ollama.generate(
            prompt,
            model=Config.SENTIMENT_MODEL
        )

        return response["response"]