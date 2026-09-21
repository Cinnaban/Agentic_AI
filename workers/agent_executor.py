import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from agents.research_agent import ResearchAgent
from agents.sentiment_agent import SentimentAgent
from agents.risk_agent import RiskAgent
from agents.quant_agent import QuantAgent
from agents.signal_reconciliation_agent import SignalReconciliationAgent
from data.market_context_provider import (MarketContextProvider)

class AgentExecutor:

    def __init__(self):
        self.research_agent = ResearchAgent()
        self.sentiment_agent = SentimentAgent()
        self.quant_agent = QuantAgent()
        self.risk_agent = RiskAgent()
        self.signal_reconciliation_agent = (SignalReconciliationAgent())
        self.market_context_provider = (MarketContextProvider())
        
    def execute(
        self,
        work_package
    ):

        results = {}

        required_agents = (
            work_package.required_agents
        )
        if not isinstance(
            required_agents,
            dict
        ):
            return {
                "error": "Invalid required_agents configuration",
                "status": "failed"
            }
        
        company = ( 
            work_package.companies[0]
        )
        market_context = (
            self.market_context_provider.get_context(
                company
            )
        )
# QUANT 
        if required_agents.get(
            "quant",
            False
        ):
            results["quant"] = (
                self.quant_agent.analyze(
                    work_package
                )
            )
            
            market_context = (
                self.market_context_provider.get_context(
                    company=company,
                    quant_data=results.get(
                        "quant"
                    )
                )
            )
            if market_context is None:

                market_context = (
                    self.market_context_provider.get_context(
                        company=company
                    )
                )
# RESEARCH
        if required_agents.get(
            "research",
            False
        ):
            results["research"] = (
                self.research_agent.analyze(
                    company=company,
                    market_context=(market_context)
                )
            )
# SENTIMENT
        if required_agents.get(
            "sentiment",
            False
        ):
            results["sentiment"] = (
                self.sentiment_agent.analyze(
                    company=company,
                    market_context=(market_context)
                )
            )
       
        if (
            required_agents.get(
                "quant",
                False
            )
            and results.get("quant")
        ):
            results["signal_reconciliation"] = (
                self.signal_reconciliation_agent.analyze(
                    results["quant"]
                )
            )
# RISK
        if required_agents.get(
            "risk",
            False
        ):

            quant_data = results.get(
                "quant"
            )

            reconciliation_data = results.get(
                "signal_reconciliation"
            )
            if (
                isinstance(
                    reconciliation_data,
                    dict
                )
                and reconciliation_data.get(
                    "status"
                ) == "failed"
            ):

                reconciliation_data = None

            results["risk"] = (
                self.risk_agent.analyze(
                    company=company,
                    quant_data=quant_data,
                    reconciliation_data=(
                        reconciliation_data
                    )
                )
            )

        return results
