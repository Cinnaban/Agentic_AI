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
from orchestrator.freshness_detector import (FreshnessDetector)

class AgentExecutor:

    def __init__(self):
        self.research_agent = ResearchAgent()
        self.sentiment_agent = SentimentAgent()
        self.quant_agent = QuantAgent()
        self.risk_agent = RiskAgent()
        self.signal_reconciliation_agent = (SignalReconciliationAgent())
        self.market_context_provider = (MarketContextProvider())
        self.freshness_detector = (FreshnessDetector())
        
    def _execute_multi_company(
        self,
        work_package
    ):

        company_results = {}
        
        comparison_plan = getattr(
            work_package,
            "comparison_plan",
            {}
        )


        if not isinstance(
            comparison_plan,
            dict
        ):

            comparison_plan = {}


        needs_quant = comparison_plan.get(
            "needs_quant",
            True
        )


        needs_research = comparison_plan.get(
            "needs_research",
            True
        )


        needs_risk = comparison_plan.get(
            "needs_risk",
            True
        )


        needs_live = comparison_plan.get(
            "needs_live",
            False
        )
        if comparison_plan:

            requires_live_data = (
                needs_live
            )


        else:

            requires_live_data = (
                self.freshness_detector
                .requires_live_data(
                    work_package.original_message
                )
            )

        quant_result = None


        if (
            work_package.required_agents.get(
                "quant"
            )
            and needs_quant
        ):

            quant_result = (
                self.quant_agent.analyze(
                    work_package
                )
            )


        quant_by_ticker = {}


        if isinstance(
            quant_result,
            dict
        ):

            for item in quant_result.get(
                "results",
                []
            ):

                if not isinstance(
                    item,
                    dict
                ):

                    continue


                company = item.get(
                    "company",
                    {}
                )


                if not isinstance(
                    company,
                    dict
                ):

                    continue


                ticker = company.get(
                    "ticker"
                )


                if not isinstance(
                    ticker,
                    str
                ):

                    continue


                ticker = (
                    ticker
                    .strip()
                    .upper()
                )


                if not ticker:

                    continue


                quant_by_ticker[
                    ticker
                ] = item


        for company in work_package.companies:

            if not isinstance(
                company,
                dict
            ):

                continue


            ticker = company.get(
                "ticker"
            )


            if not isinstance(
                ticker,
                str
            ):

                continue


            ticker = (
                ticker
                .strip()
                .upper()
            )


            if not ticker:

                continue


            company_quant = (
                quant_by_ticker.get(
                    ticker
                )
            )
            
            print()
            print(
                "MULTI-COMPANY RESEARCH:",
                ticker
            )
            
            market_context = (
                self.market_context_provider
                .get_context(
                    company=company,
                    quant_data=company_quant,
                    original_message=(
                        work_package
                        .original_message
                    ),
                    requires_live_data=(
                        requires_live_data
                    )
                )
            )

            research_result = None  

            if (
                work_package.required_agents.get(
                    "research",
                    False
                )
                and needs_research
            ):

                research_result = (
                    self.research_agent
                    .analyze(
                        company=company,
                        market_context=(
                            market_context
                        )
                    )
                )
            
                reconciliation_result = None    


            if (
                work_package.required_agents.get(
                    "quant",
                    False
                )
                and company_quant
            ):

                reconciliation_result = (
                    self.signal_reconciliation_agent
                    .analyze(
                        company_quant
                    )
                )


                if (
                    isinstance(
                        reconciliation_result,
                        dict
                    )
                    and reconciliation_result.get(
                        "status"
                    ) == "failed"
                ):

                    reconciliation_result = None


            risk_result = None


            if (
                work_package.required_agents.get(
                    "risk",
                    False
                )
                and needs_risk
            ):

                print(
                    "MULTI-COMPANY RISK:",
                    ticker
                )


                risk_result = (
                    self.risk_agent
                    .analyze(
                        company=company,
                        quant_data=company_quant,
                        reconciliation_data=(
                            reconciliation_result
                        )
                    )
                )


                print(
                    "MULTI-COMPANY RISK COMPLETE:",
                    ticker
                )

                risk_result = (
                    self.risk_agent
                    .analyze(
                        company=company,
                        quant_data=company_quant,
                        reconciliation_data=(
                            reconciliation_result
                        )
                    )
                )
           
            if market_context is None:

                market_context = (
                    self.market_context_provider
                    .get_context(
                        company=company,
                        original_message=(
                            work_package
                            .original_message
                        ),
                        requires_live_data=(
                            requires_live_data
                        )
                    )
                )
            
            

            company_results[
                ticker
            ] = {
                "company":
                    company,

                "quant":
                    company_quant,

                "research":
                    research_result,

                "sentiment":
                    None,
                    
                "signal_reconciliation":
                    reconciliation_result,

                "risk":
                    risk_result
            }


        print()
        print("=" * 60)
        print("MULTI-COMPANY EXECUTOR RESULT")
        print("=" * 60)

        print(
            "Quant tickers:",
            list(
                quant_by_ticker.keys()
            )
        )

        print(
            "Company result tickers:",
            list(
                company_results.keys()
            )
        )

        print("=" * 60)


        return {
            "company_results":
                company_results,

            "quant":
                quant_result,

            "comparison_plan":
                comparison_plan
        }
    
    def execute(
        self,
        work_package
    ):
        if (
            isinstance(
                work_package.companies,
                list
            )
            and len(
                work_package.companies
            ) > 1
        ):

            return (
                self._execute_multi_company(
                    work_package
                )
            )

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
        
        requires_live_data = (
            self.freshness_detector
            .requires_live_data(
                work_package.original_message
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
                    ),

                    original_message=(
                        work_package.original_message
                    ),

                    requires_live_data=(
                        requires_live_data
                    )
                )
            )
            
            if market_context is None:
                market_context = (
                    self.market_context_provider.get_context(
                        company=company,

                        original_message=(
                            work_package.original_message
                        ),

                        requires_live_data=(
                            requires_live_data
                        )
                    )
                )
        else:
            market_context = (
                self.market_context_provider.get_context(
                    company
                )
            )
        if company.get("entity_type") == "etf":
            if not isinstance(market_context, dict):
                market_context = {}
            etf_context = company.get("etf_context")
            if not isinstance(etf_context, dict):
                etf_context = {
                    "status": "unavailable",
                    "source": "Yahoo Finance",
                    "error": (
                        "ETF fund data was not supplied "
                        "during instrument classification."
                    )
                }
            market_context["etf_fund_data"] = etf_context
            source_status = market_context.get("source_status")
            if not isinstance(source_status, dict):
                source_status = {}
                market_context["source_status"] = source_status
            source_status["etf_fund_data"] = etf_context.get(
                "status",
                "unavailable"
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

        # Preserve source evidence for downstream
        # challenger and quality-review stages.
        results["market_context"] = (
            market_context
        )

        return results
