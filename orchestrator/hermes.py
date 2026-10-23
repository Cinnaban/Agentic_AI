import re
import sys
import traceback 

from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from configs.config import Config

from agents.company_detection_agent import (CompanyDetectionAgent)
from agents.research_assignment_agent import (ResearchAssignmentAgent)
from agents.qwen_manager import (QwenManager)
from agents.general_response_agent import (GeneralResponseAgent)
from agents.current_topic_agent import (
    CurrentTopicAgent
)

from orchestrator.freshness_detector import (
    FreshnessDetector
)
from orchestrator.evidence_provenance import (
    EvidenceProvenance
)
from agents.challenger_agent import ChallengerAgent

from data.providers.live_market_providers import (
    LiveMarketProvider
)
from job_queue.job_factory import JobFactory
from workers.agent_executor import AgentExecutor
from orchestrator.result_aggregator import (ResultAggregator)
from orchestrator.final_response_builder import (FinalResponseBuilder)
from orchestrator.quality_context_builder import(QualityContextBuilder)
from security.outbound_gate import (OutboundResponseGate)
from shared_storage.storage_manager import (StorageManager)
from memory.workflow_state import (
    WorkflowState,
    WorkflowStatus
)
from memory.conversation_history_provider import (
    ConversationHistoryProvider
)
from agents.comparison_agent import (
    ComparisonAgent
)
from orchestrator.portfolio_request_parser import (
    PortfolioRequestParser
)
from agents.portfolio_evaluation_agent import (
    PortfolioEvaluationAgent
)
from data.providers.portfolio_context_provider import (
    PortfolioContextProvider
)
from data.providers.etf_fund_provider import ETFFundProvider
from data.providers.performance_chart_provider import (
    PerformanceChartProvider
)
from data.providers.portfolio_allocation_chart_provider import (
    PortfolioAllocationChartProvider
)
from data.providers.portfolio_performance_chart_provider import (
    PortfolioPerformanceChartProvider
)
from orchestrator.comparison_intent import (
    ComparisonIntent
)
from memory.conversation_context import (
    ConversationContext
)
from orchestrator.followup_resolver import (
    FollowUpResolver
)
from orchestrator.comparison_request_planner import (
    ComparisonRequestPlanner
)
from agents.financial_formula_designer import (
    FinancialFormulaDesigner
)
from financial_engine.formula_metric_extractor import (
    FormulaMetricExtractor
)
from financial_engine.formula_evaluator import (
    FormulaEvaluator
)
from agents.generic_evidence_agent import (
    GenericEvidenceAgent
)
from data.providers.generic_evidence_provider import (
    GenericEvidenceProvider
)
from orchestrator.generic_research_planner import (
    GenericResearchPlanner
)
from orchestrator.generic_research_intent import (
    GenericResearchIntent
)
from orchestrator.financial_metric_builder import (
    FinancialMetricBuilder
)

from orchestrator.financial_table_formatter import (
    FinancialTableFormatter
)
from agents.consensus_agent import ConsensusAgent
from orchestrator.quant_comparison_reviewer import (
    QuantComparisonReviewer
)
from orchestrator.quant_evidence_builder import (
    QuantEvidenceBuilder
)
class Hermes:

    def __init__(self):
        self.company_agent = (CompanyDetectionAgent())
        self.assignment_agent = (ResearchAssignmentAgent())
        self.general_response_agent = (GeneralResponseAgent())
        self.job_factory = JobFactory()
        self.executor = AgentExecutor()
        self.aggregator = ResultAggregator()
        self.quality_manager = QwenManager()
        self.response_builder = (FinalResponseBuilder())
        self.outbound_gate = (OutboundResponseGate())
        self.workflow_state = (WorkflowState())
        self.storage_manager = (StorageManager())
        self.quality_context_builder = (QualityContextBuilder())
        self.financial_metric_builder = (
            FinancialMetricBuilder()
        )
        self.conversation_context = (
            ConversationContext()
        )

        self.conversation_history_provider = (
            ConversationHistoryProvider(
                conversation_context=
                    self.conversation_context
            )
        )
        self.portfolio_request_parser = (
            PortfolioRequestParser()
        )
        self.portfolio_evaluation_agent = (
            PortfolioEvaluationAgent()
        )

        self.portfolio_context_provider = (
            PortfolioContextProvider()
        )
        self.etf_fund_provider = ETFFundProvider()
        self.performance_chart_provider = (
            PerformanceChartProvider()
        )
        self.portfolio_allocation_chart_provider = (
            PortfolioAllocationChartProvider()
        )
        self.portfolio_performance_chart_provider = (
            PortfolioPerformanceChartProvider()
        )
        self.financial_table_formatter = (
            FinancialTableFormatter()
        )
        self.freshness_detector = (
            FreshnessDetector()
        )

        self.live_market_provider = (
            LiveMarketProvider()
        )
        self.quant_comparison_reviewer = (
            QuantComparisonReviewer()
        )
        self.consensus_agent = ConsensusAgent()
        self.quant_evidence_builder = (
            QuantEvidenceBuilder(
                web_fn=lambda company: (
                    self.live_market_provider.get_context(
                        company=company,
                        query=(
                            f"{company.get('ticker') or company.get('name')} "
                            "stock news latest"
                        )
                    )
                    if isinstance(company, dict)
                    else {}
                )
            )
        )

        self.current_topic_agent = (
            CurrentTopicAgent()
        )
        
        self.challenger_agent = ChallengerAgent()
        
        self.comparison_request_planner = (
            ComparisonRequestPlanner()
        )
        self.comparison_agent = (
            ComparisonAgent()
        )
        self.financial_formula_designer = (
            FinancialFormulaDesigner()
        )
        self.formula_metric_extractor = (
            FormulaMetricExtractor()
        )
        self.formula_evaluator = (
            FormulaEvaluator()
        )
        self.comparison_intent = (
            ComparisonIntent()
        )
        self.followup_resolver = (
            FollowUpResolver()
        )
        self.generic_evidence_provider = (
            GenericEvidenceProvider()
        )
        self.generic_evidence_agent = (
            GenericEvidenceAgent()
        )
        self.generic_research_planner = (
            GenericResearchPlanner()
        )
        self.generic_research_intent = (
            GenericResearchIntent()
        )
       
    @staticmethod
    def _format_failure_message(error):
        error_detail = str(error)
        if "Gaming PC" in error_detail:
            return (
                "Stock/ETF quantitative analysis could not run. "
                f"{error_detail} Check that the Gaming PC compute "
                "service is online, then retry. No verified result "
                "was produced."
            )
        return (
            "I couldn't complete the requested analysis. "
            "No verified result was produced; please try again later."
        )

        
    def _build_followup_workflow(
            self,
            message,
            followup,
            source="unknown"
        ):

            if not isinstance(
                followup,
                dict
            ):

                return None


            entities = followup.get(
                "entities",
                []
            )


            if not isinstance(
                entities,
                list
            ):

                return None


            if not entities:

                return None


            required_agents = {
                "research":
                    True,

                "sentiment":
                    False,

                "quant":
                    True,

                "risk":
                    True
            }

            return (
               
                self.job_factory
                .create_work_package(
                    companies=entities,
                    required_agents=required_agents,
                    original_message=message,
                    source=source,
                    priority=100
                )
            )
            
        
    def _all_companies_have_public_tickers(
        self,
        company_result
    ):

        if not isinstance(
            company_result,
            dict
        ):

            return False


        companies = company_result.get(
            "companies",
            []
        )


        if not isinstance(
            companies,
            list
        ):

            return False


        if not companies:

            return False


        for company in companies:

            if not isinstance(
                company,
                dict
            ):

                return False


            ticker = company.get(
                "ticker"
            )


            if not isinstance(
                ticker,
                str
            ):

                return False


            ticker = (
                ticker
                .strip()
                .upper()
            )


            if not ticker:

                return False


            entity_type = str(
                company.get(
                    "entity_type",
                    ""
                )
                or ""
            ).strip().lower()


            if entity_type in {
                "private",
                "private_company",
                "non_public"
            }:

                return False


        return True

    def _classify_portfolio_holdings(self, holdings):
        max_holdings = int(getattr(
            Config,
            "PORTFOLIO_CONTEXT_MAX_HOLDINGS",
            50
        ))
        for index, holding in enumerate(holdings):
            if not isinstance(holding, dict):
                continue

            ticker = str(
                holding.get("ticker", "") or ""
            ).strip().upper()
            if not ticker:
                continue
            if index >= max_holdings:
                holding["entity_type"] = "unresolved"
                holding["classification_status"] = (
                    "not_evaluated_limit"
                )
                continue

            try:
                classification = self.etf_fund_provider.resolve(
                    ticker,
                    message=f"Classify portfolio holding {ticker}"
                )
            except Exception as error:
                classification = {
                    "entity_type": "security",
                    "classification_status": "unavailable",
                    "classification_error": str(error)
                }
                print(
                    "PORTFOLIO CLASSIFICATION FAILED:",
                    ticker,
                    error
                )

            if not isinstance(classification, dict):
                classification = {
                    "entity_type": "security",
                    "classification_status": "unavailable"
                }

            entity_type = classification.get("entity_type")
            if entity_type not in {"stock", "etf"}:
                entity_type = "unresolved"

            holding["entity_type"] = entity_type
            holding["classification_status"] = classification.get(
                "classification_status",
                "unavailable"
            )
            if classification.get("classification_error"):
                holding["classification_error"] = classification[
                    "classification_error"
                ]
            for field in ("sector", "industry"):
                if classification.get(field):
                    holding[field] = classification[field]

            etf_context = classification.get("etf_context")
            if entity_type == "etf" and isinstance(etf_context, dict):
                holding["etf_context"] = etf_context

        return holdings

        
    def build_workflow(
        self,
        message
    ):
        portfolio_request = (
            self.portfolio_request_parser
            .parse(
                message
            )
        )

        if portfolio_request.get(
            "is_portfolio_request",
            False
        ):
            return {
                "route":
                    "general_evaluation",
                "evaluation_type":
                    "portfolio",
                "holdings":
                    portfolio_request.get(
                        "holdings",
                        []
                    )
            }

        company_result = (
            self.company_agent.analyze(
                message
            )
        )

        normalized = (
            str(message)
            .lower()
        )

        intent = (
            company_result.get(
                "intent",
                "general_information"
            )
        )

        companies = company_result.get(
            "companies",
            []
        )
        if not isinstance(companies, list):
            companies = []

        is_single_public_security_request = (
            len(companies) == 1
            and isinstance(companies[0], dict)
            and isinstance(companies[0].get("ticker"), str)
            and bool(companies[0]["ticker"].strip())
        )
        explicit_evaluation_terms = (
            "evaluate",
            "evaluation",
            "assess",
            "rate"
        )
        explicit_analysis_terms = (
            "analyze",
            "analyse",
            "analysis",
            "valuation",
            "value",
            "forecast",
            "outlook",
            "risk analysis"
        )
        is_explicit_security_evaluation = (
            is_single_public_security_request
            and any(
                re.search(rf"\b{re.escape(term)}\b", normalized)
                for term in explicit_evaluation_terms
            )
        )
        is_explicit_security_analysis = (
            is_single_public_security_request
            and any(
                re.search(rf"\b{re.escape(term)}\b", normalized)
                for term in explicit_analysis_terms
            )
        )

        if self.comparison_intent.is_comparison(message, companies):
            intent = "comparison"
        elif is_explicit_security_evaluation:
            intent = "evaluation"
        elif is_explicit_security_analysis:
            intent = "analysis"
        
        evaluation_keywords = {
            "evaluate",
            "evaluation",
            "assess",
            "review",
            "critique",
            "reverse engineer",
            "portfolio",
            "allocation",
            "weighting",
            "holdings",
            "positions",
            "chosen",
            "selection"
        }

        is_evaluation_request = any(
            keyword in normalized
            for keyword in evaluation_keywords
        )
        print()
        print("=" * 80)
        print("COMPANY RESULT")
        print(company_result)
        print("=" * 80)
        
        if not company_result.get(
            "is_company_request",
            False
        ):
            return {
                "route":
                    "local_agents"
            }
            
        if intent not in {
                    "analysis",
                    "evaluation",
                    "comparison"
                }:
        
                    return {
                        "route":
                            "company_information",
        
                        "intent":
                            intent,
        
                        "companies":
                            company_result.get(
                                "companies",
                                []
                            )
                    }
            
        if not self._all_companies_have_public_tickers(
            company_result
        ):

            return {
                "route":
                    "local_agents",

                "fallback_reason":
                    "no_public_ticker"
            }

        assignment_result = (
            self.assignment_agent.analyze(
                company_result["companies"],
                message
            )
        )

        if not isinstance(assignment_result, dict):
            assignment_result = {}

        if intent == "comparison":
            for agent_name in ("research", "quant", "sentiment"):
                assignment_result[agent_name] = True

        if (
            is_explicit_security_evaluation
            or is_explicit_security_analysis
        ):
            assignment_result["quant"] = True

        if assignment_result.get("quant"):
            classified_companies = []
            for company in company_result["companies"]:
                company = dict(company)
                classification = self.etf_fund_provider.resolve(
                    company["ticker"],
                    message
                )
                company["entity_type"] = classification.get(
                    "entity_type",
                    "security"
                )
                company["instrument_classification"] = {
                    key: value
                    for key, value in classification.items()
                    if key not in {
                        "entity_type",
                        "etf_context"
                    }
                }
                for field in ("industry", "sector"):
                    if classification.get(field):
                        company[field] = classification[field]
                if classification.get("etf_context") is not None:
                    company["etf_context"] = classification[
                        "etf_context"
                    ]
                classified_companies.append(company)
            company_result["companies"] = classified_companies

            if any(
                company.get("entity_type") == "etf"
                for company in classified_companies
            ):
                assignment_result["research"] = True
                assignment_result["risk"] = True

        work_package = (
            self.job_factory
            .create_work_package(
                companies=company_result[
                    "companies"
                ],
                required_agents=assignment_result,
                original_message=message
            )
        )
        

        return work_package

    def process_request(
        self,
        message,
        source="unknown",
        channel_id=None,
        user_id=None
    ):

        work_package = None


        conversation_key = (
            self.conversation_context
            .make_key(
                source=source,
                channel_id=channel_id,
                user_id=user_id
            )
        )


        conversation_state = (
            self.conversation_context
            .get(
                conversation_key
            )
        )
        
        pending_action = (
            conversation_state.get(
                "pending_action"
            )
        )


        last_generic_research = (
            conversation_state.get(
                "last_generic_research"
            )
        )


        normalized_message = (
            str(
                message
                or ""
            )
            .strip()
            .lower()
        )

        try:
            from data.providers.live.price_quote import (
                answer as live_price_answer
            )
            price_text = live_price_answer(
                message,
                self.live_market_provider
            )
        except Exception:
            price_text = None
        if price_text:
            safe_price = self.outbound_gate.prepare(
                {
                    "status": "completed",
                    "response": price_text
                }
            )
            self.conversation_context.add_message(
                conversation_key,
                "user",
                str(message)
            )
            self.conversation_context.add_message(
                conversation_key,
                "assistant",
                price_text
            )
            return safe_price

        positive_replies = {
            "yes",
            "yeah",
            "yep",
            "sure",
            "please",
            "do it",
            "yes please"
        }


        negative_replies = {
            "no",
            "no thanks",
            "not now",
            "no thank you"
        }


        deep_requests = (
            "deeper research",
            "go deeper",
            "research deeper",
            "research this deeper",
            "more detailed research",
            "full research",
            "deeper analysis"
        )


        summary_requests = (
            "summarize that",
            "summary version",
            "summarized version",
            "give me a summary",
            "shorter version",
            "brief version"
        )


        requested_research_depth = None

        pending_original_message = None

        if (
            isinstance(
                pending_action,
                dict
            )
            and pending_action.get(
                "type"
            ) == "generic_research_depth"
        ):

            if normalized_message in (
                positive_replies
            ):

                requested_research_depth = (
                    pending_action.get(
                        "suggested_depth"
                    )
                )


                pending_original_message = (
                    pending_action.get(
                        "original_message"
                    )
                )


                self.conversation_context.clear_pending_action(
                    conversation_key
                )


            elif normalized_message in (
                negative_replies
            ):

                self.conversation_context.clear_pending_action(
                    conversation_key
                )


                response = {
                    "status":
                        "completed",

                    "response":
                        "Understood."
                }


                return (
                    self.outbound_gate
                    .prepare(
                        response
                    )
                )
            
        if any(
            phrase in normalized_message
            for phrase in deep_requests
        ):

            requested_research_depth = (
                "deep"
            )

            if isinstance(
                last_generic_research,
                dict
            ):

                pending_original_message = (
                    last_generic_research.get(
                        "question"
                    )
                )


        elif any(
            phrase in normalized_message
            for phrase in summary_requests
        ):

            requested_research_depth = (
                "summary"
            )

            if isinstance(
                last_generic_research,
                dict
            ):

                pending_original_message = (
                    last_generic_research.get(
                        "question"
                    )
                )
                
                   
        effective_message = (
            pending_original_message
            or message
        )

        self.conversation_context.add_message(
            conversation_key,
            "user",
            message
        )


        if requested_research_depth:
            followup = None

        else:
            followup = (
                self.followup_resolver
                .resolve(
                    message=message,
                    context=conversation_state
                )
            )
            
            recent_messages = (
                conversation_state.get(
                    "recent_messages",
                    []
                )
            )

            portfolio_followup_phrases = (
                "compare it",
                "compare that",
                "compare against",
                "posted earlier",
                "previous portfolio",
                "last portfolio",
                "earlier portfolio",
                "what i posted earlier"
            )

            portfolio_followup = any(
                phrase in normalized_message
                for phrase in portfolio_followup_phrases
            )

            if (
                followup is None
                and portfolio_followup
            ):
                followup = {
                    "intent":
                        "portfolio_followup",
                    "recent_messages":
                        recent_messages
                }
            print()
            print("=" * 60)
            print("FOLLOWUP DEBUG")
            print("=" * 60)
            print("CONVERSATION STATE:")
            print(conversation_state)

            print()
            print("FOLLOWUP:")
            print(followup)

            print("=" * 60)

            if isinstance(
                last_generic_research,
                dict
            ):

                pending_original_message = (
                    last_generic_research.get(
                        "question"
                    )
                )

        try:

            if followup:

                work_package = (
                    self._build_followup_workflow(
                        message=message,
                        followup=followup,
                        source=source
                    )
                )


                if work_package is None:

                    if (
                        isinstance(
                            followup,
                            dict
                        )
                        and followup.get(
                            "intent"
                        ) == "portfolio_followup"
                    ):
                        recent_portfolio = None

                        for history_message in reversed(
                            recent_messages
                        ):
                            if (
                                history_message.get(
                                    "role"
                                )
                                != "user"
                            ):
                                continue

                            content = str(
                                history_message.get(
                                    "content",
                                    ""
                                )
                            )

                            portfolio_candidate = (
                                self.portfolio_request_parser
                                .parse(
                                    content
                                )
                            )

                            if portfolio_candidate.get(
                                "is_portfolio_request",
                                False
                            ):
                                recent_portfolio = content
                                break

                        if recent_portfolio:
                            effective_message = (
                                "PREVIOUS PORTFOLIO:\n\n"
                                + recent_portfolio
                                + "\n\nCURRENT REQUEST:\n\n"
                                + str(message)
                            )
                            
                        print()
                        print("=" * 60)
                        print("PORTFOLIO FOLLOWUP RESOLVED")
                        print("=" * 60)
                        print(recent_portfolio)
                        print("=" * 60)
                        

                    work_package = (
                        self.build_workflow(
                            effective_message
                        )
                    )


            else:

                history_context = (
                    self.conversation_history_provider
                    .get_context(
                        source=source,
                        channel_id=channel_id,
                        user_id=user_id
                    )
                )
                
                recent_portfolios = (
                    history_context.get(
                        "recent_portfolios",
                        []
                    )
                )

                portfolio_reference_terms = (
                    "earlier",
                    "previous",
                    "last portfolio",
                    "that portfolio",
                    "posted earlier",
                    "compare it"
                )

                should_use_portfolio_context = any(
                    term in normalized_message
                    for term in portfolio_reference_terms
                )

                if (
                    recent_portfolios
                    and should_use_portfolio_context
                ):
                
                    effective_message = (
                        "RECENT PORTFOLIO CONTEXT:\n\n"
                        + recent_portfolios[-1]
                        + "\n\nCURRENT REQUEST:\n\n"
                        + effective_message
                    )

                work_package = (
                    self.build_workflow(
                        effective_message
                    )
                )

            if hasattr(
                work_package,
                "job_id"
            ):

                is_comparison = (
                (
                    followup is not None
                    and followup.get(
                        "intent"
                    ) == "company_comparison"
                )
                or
                (
                    self.comparison_intent
                    .is_comparison(
                        message,
                        work_package.companies
                        )
                    )
                )
                comparison_plan = None

                if is_comparison:

                    comparison_plan = (
                        self.comparison_request_planner
                        .plan(
                            message
                        )
                    )


                context_intent = (
                    "company_comparison"
                    if is_comparison
                    else "company_analysis"
                )


                self.conversation_context.set_active_entities(
                    conversation_key,
                    work_package.companies,
                    intent=context_intent,
                    request=message
                )

            if not hasattr(
                work_package,
                "job_id"
            ):

                requires_live_data = (
                    self.freshness_detector
                    .requires_live_data(
                        effective_message,
                    )
                )
                
                fallback_reason = None
                
                if (
                    isinstance(
                        work_package,
                        dict
                    )
                    and work_package.get(
                        "route"
                    ) == "company_information"
                ):

                    company_names = [
                        company.get(
                            "name",
                            ""
                        )
                        for company in work_package.get(
                            "companies",
                            []
                        )
                    ]

                    company_text = (
                        ", ".join(
                            company_names
                        )
                    )

                    intent = work_package.get(
                        "intent",
                        "general_information"
                    )

                    info_prompt = (
                        f"{message}\n\n"
                        f"(Subject: {company_text})"
                    )

                    research_plan = (
                        self.generic_research_planner
                        .plan(
                            message
                        )
                    )

                    if not isinstance(
                        research_plan,
                        dict
                    ):
                        research_plan = {}

                    search_queries = (
                        research_plan.get(
                            "queries",
                            []
                        )
                    )

                    if not isinstance(
                        search_queries,
                        list
                    ):
                        search_queries = []

                    evidence = (
                        self.generic_evidence_provider
                        .get_context(
                            query=message,
                            search_queries=search_queries,
                            research_plan=research_plan,
                            subject=company_text
                        )
                    )

                    if not isinstance(
                        evidence,
                        dict
                    ):
                        evidence = {
                            "available": False,
                            "results": [],
                            "sources": []
                        }

                    general_result = (
                        self.general_response_agent
                        .analyze(
                            message=info_prompt,
                            evidence=evidence,
                            research_plan=research_plan
                        )
                    )

                    return self.outbound_gate.prepare(
                        general_result
                    )

                if (
                    isinstance(
                        work_package,
                        dict
                    )
                    and work_package.get(
                        "route"
                    ) == "general_evaluation"
                ):
                    holdings = work_package.get(
                        "holdings",
                        []
                    )

                    if not isinstance(
                        holdings,
                        list
                    ):
                        holdings = []
                    else:
                        holdings = self._classify_portfolio_holdings(
                            holdings
                        )

                    minimum_holdings = int(
                        getattr(
                            Config,
                            "PORTFOLIO_CONTEXT_MIN_HOLDINGS",
                            3
                        )
                    )

                    portfolio_context = {}

                    quant_data_by_ticker = {}
                    quant_executions = {}

                    quant_enabled = bool(
                        getattr(
                            Config,
                            "PORTFOLIO_QUANT_ENABLED",
                            True
                        )
                    )

                    quant_minimum = int(
                        getattr(
                            Config,
                            "PORTFOLIO_QUANT_MIN_HOLDINGS",
                            3
                        )
                    )

                    quant_maximum = int(
                        getattr(
                            Config,
                            "PORTFOLIO_QUANT_MAX_HOLDINGS",
                            10
                        )
                    )

                    if (
                        quant_enabled
                        and len(holdings)
                        >= quant_minimum
                    ):
                        for holding in holdings[
                            :quant_maximum
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
                                or ""
                            ).strip().upper()

                            if not ticker:
                                continue

                            entity_type = holding.get("entity_type")
                            if entity_type == "unresolved":
                                continue

                            company = {
                                "name":
                                    ticker,
                                "ticker":
                                    ticker,
                                "entity_type":
                                    entity_type
                            }
                            for field in ("sector", "industry"):
                                if holding.get(field):
                                    company[field] = holding[field]
                            if entity_type == "etf":
                                company["etf_context"] = holding.get(
                                    "etf_context"
                                )

                            quant_work_package = (
                                self.job_factory
                                .create_work_package(
                                    companies=[
                                        company
                                    ],
                                    required_agents={
                                        "research": False,
                                        "sentiment": False,
                                        "quant": True,
                                        "risk": False
                                    },
                                    original_message=(
                                        "Generate a brief quantitative "
                                        f"snapshot for {ticker}"
                                    ),
                                    source="portfolio",
                                    priority=50
                                )
                            )

                            try:
                                quant_execution = (
                                    self.executor.execute(
                                        quant_work_package
                                    )
                                )

                                if not isinstance(
                                    quant_execution,
                                    dict
                                ):
                                    continue

                                quant_result = (
                                    quant_execution.get(
                                        "quant"
                                    )
                                )

                                if isinstance(
                                    quant_result,
                                    dict
                                ):
                                    quant_data_by_ticker[
                                        ticker
                                    ] = quant_result
                                    quant_executions[
                                        ticker
                                    ] = quant_execution

                            except Exception as quant_error:
                                print(
                                    "PORTFOLIO QUANT FAILED:",
                                    ticker,
                                    quant_error
                                )

                    if (
                        Config.PORTFOLIO_EVALUATION_ENABLED
                        and len(holdings)
                        >= minimum_holdings
                    ):
                        portfolio_context = (
                            self.portfolio_context_provider
                            .get_context(
                                holdings=holdings,
                                quant_data_by_ticker=(
                                    quant_data_by_ticker
                                ),
                                original_message=effective_message
                            )
                        )

                    portfolio_result = (
                        self.portfolio_evaluation_agent
                        .analyze(
                            message=effective_message,
                            holdings=holdings,
                            portfolio_context=(
                                portfolio_context
                            )
                        )
                    )

                    try:
                        from orchestrator.table_format import (
                            holdings_tables
                        )
                        holdings_text = holdings_tables(holdings)
                        quant_section, consensus_inputs = (
                            self._build_portfolio_quant_section(
                                quant_executions
                            )
                        )
                        narrative = str(
                            portfolio_result.get("response", "")
                        )
                        summary = self._consensus_summary(
                            effective_message,
                            {
                                "holdings": holdings,
                                "portfolio_context": portfolio_context,
                                "portfolio_evaluation": narrative,
                                **consensus_inputs
                            }
                        )
                        portfolio_result["response"] = "\n\n".join(
                            part for part in (
                                holdings_text,
                                quant_section,
                                summary or narrative
                            ) if part
                        )
                    except Exception as table_error:
                        print(
                            "PORTFOLIO TABLE FAILED:",
                            table_error
                        )
                    allocation_chart = (
                        self.portfolio_allocation_chart_provider
                        .generate(holdings)
                    )
                    if (
                        isinstance(allocation_chart, dict)
                        and allocation_chart.get("status") == "completed"
                        and allocation_chart.get("path")
                    ):
                        portfolio_result["attachments"] = [{
                            "path": allocation_chart["path"],
                            "filename": "portfolio_allocation.png",
                            "caption": allocation_chart.get("caption", "")
                        }]
                        portfolio_result["response"] = (
                            str(portfolio_result.get("response", "")).rstrip()
                            + "\n\nPortfolio allocation chart is attached."
                        )
                    elif isinstance(allocation_chart, dict):
                        portfolio_result["response"] = (
                            str(portfolio_result.get("response", "")).rstrip()
                            + "\n\nPortfolio allocation chart unavailable: "
                            + str(
                                allocation_chart.get(
                                    "error",
                                    "No valid holding weights."
                                )
                            )
                        )

                    self._add_portfolio_performance_charts(
                        portfolio_result,
                        holdings
                    )

                    safe_response = (
                        self.outbound_gate.prepare(
                            portfolio_result
                        )
                    )

                    response_text = (
                        safe_response.get(
                            "response"
                        )
                    )

                    if response_text:
                        self.conversation_context.add_message(
                            conversation_key,
                            "assistant",
                            response_text
                        )

                    return safe_response
                
                if (
                    requires_live_data
                    and self.freshness_detector
                    .is_financial_query(
                        effective_message
                    )
                ):

                    live_context = (
                        self.live_market_provider
                        .get_context(
                            company={},
                            query=effective_message
                        )
                    )


                    current_result = (
                        self.current_topic_agent
                        .analyze(
                            message=effective_message,
                            live_context=live_context
                        )
                    )

                    current_result = (
                        EvidenceProvenance.add_to_result(
                            current_result,
                            live_context,
                            requires_current=True
                        )
                    )

                    safe_response = (
                        self.outbound_gate.prepare(
                            current_result
                        )
                    )

                    response_text = (
                        safe_response.get(
                            "response"
                        )
                    )

                    if response_text:

                        self.conversation_context.add_message(
                            conversation_key,
                            "assistant",
                            response_text
                        )
                        
                    print()
                    print("=" * 80)
                    print("FINAL RESPONSE")
                    print("=" * 80)

                    print(
                        safe_response
                    )

                    print("=" * 80)

                    return safe_response

                should_use_generic_research = (
                    fallback_reason
                    == "no_public_ticker"
                )


                if should_use_generic_research:
                    print()
                    print("=" * 60)
                    print("GENERIC RESEARCH ROUTE SELECTED")
                    print("=" * 60)

                    research_plan = (
                        self.generic_research_planner
                        .plan(
                            message=(
                                effective_message
                            )
                        )
                    )
                    
                    if requested_research_depth:
                        research_plan[
                            "evidence_depth"
                        ] = (
                            requested_research_depth
                        )
                        research_plan[
                            "require_source_retrieval"
                        ] = (
                            requested_research_depth
                            != "summary"
                        )
                    
                    print(
                        "RESEARCH PLAN:",
                        research_plan
                    )


                    search_queries = (
                        research_plan.get(
                            "queries",
                            []
                        )
                    )


                    generic_evidence = (
                        self.generic_evidence_provider
                        .get_context(
                            query=effective_message,

                            search_queries=(
                                search_queries
                            ),

                            research_plan=(
                                research_plan
                            )
                        )
                    )
                    
                    print(
                        "GENERIC EVIDENCE AVAILABLE:",
                        generic_evidence.get(
                            "available"
                        )
                    )

                    print(
                        "GENERIC RESULT COUNT:",
                        len(
                            generic_evidence.get(
                                "results",
                                []
                            )
                        )
                    )

                    generic_result = (
                        self.generic_evidence_agent
                        .analyze(
                            message=effective_message,

                            evidence=(
                                generic_evidence
                            ),

                            research_plan=(
                                research_plan
                            )
                        )
                    )
                    research_depth = (
                        research_plan.get(
                            "evidence_depth",
                            "standard"
                        )
                    )


                    self.conversation_context.set_last_generic_research(
                        conversation_key,

                        {
                            "question":
                                effective_message,

                            "depth":
                                research_depth,

                            "research_plan":
                                research_plan,

                            "evidence":
                                generic_evidence
                        }
                    )

                    response_text = (
                        generic_result.get(
                            "response",
                            ""
                        )
                    )


                    if research_depth == "deep":

                        offer = (
                            "Would you like a "
                            "summarized version?"
                        )

                        suggested_depth = (
                            "summary"
                        )


                    else:

                        offer = (
                            "Would you like a "
                            "deeper research?"
                        )

                        suggested_depth = (
                            "deep"
                        )


                    if response_text:

                        generic_result[
                            "response"
                        ] = (
                            response_text.rstrip()
                            + "\n\n"
                            + offer
                        )
                        
                        self.conversation_context.set_pending_action(
                        conversation_key,

                        {
                            "type":
                                "generic_research_depth",

                            "original_message":
                                effective_message,

                            "current_depth":
                                research_depth,

                            "suggested_depth":
                                suggested_depth
                        }
                    )



                    safe_response = (
                        self.outbound_gate
                        .prepare(
                            generic_result
                        )
                    )


                    response_text = (
                        safe_response.get(
                            "response"
                        )
                    )


                    if response_text:

                        self.conversation_context.add_message(
                            conversation_key,
                            "assistant",
                            response_text
                        )

                    return safe_response

                research_plan = (
                    self.generic_research_planner
                    .plan(
                        effective_message
                    )
                )

                if not isinstance(
                    research_plan,
                    dict
                ):
                    research_plan = {}

                search_queries = (
                    research_plan.get(
                        "queries",
                        []
                    )
                )

                if not isinstance(
                    search_queries,
                    list
                ):
                    search_queries = []

                evidence = (
                    self.generic_evidence_provider
                    .get_context(
                        query=effective_message,
                        search_queries=search_queries,
                        research_plan=research_plan
                    )
                )

                if not isinstance(
                    evidence,
                    dict
                ):
                    evidence = {
                        "available": False,
                        "results": [],
                        "sources": []
                    }

                general_result = (
                    self.general_response_agent
                    .analyze(
                        message=effective_message,
                        evidence=evidence,
                        research_plan=research_plan
                    )
                )

                safe_response = (
                    self.outbound_gate.prepare(
                        general_result
                    )
                )

                response_text = (
                    safe_response.get(
                        "response"
                    )
                )

                if response_text:

                    self.conversation_context.add_message(
                        conversation_key,
                        "assistant",
                        response_text
                    )


                return safe_response

            work_package.source = source

            self.storage_manager.create_job_record(
                job_id=work_package.job_id,
                data={
                    "message":
                        work_package.original_message,

                    "source":
                        work_package.source,

                    "companies":
                        work_package.companies,

                    "required_agents":
                        work_package.required_agents
                }
            )

            self.workflow_state.register_job(
                job_id=work_package.job_id,
                original_message=(
                    work_package.original_message
                )
            )

            self.workflow_state.update_status(
                work_package.job_id,
                WorkflowStatus.PLANNING
            )
            
            self.storage_manager.move_job(
                job_id=work_package.job_id,
                from_status="incoming",
                to_status="processing"
            )
            
            self.workflow_state.update_status(
                work_package.job_id,
                WorkflowStatus.EXECUTING
            )


            if comparison_plan:
                work_package.comparison_plan = (
                    comparison_plan
                )

            print()
            print("=" * 60)
            print("EXECUTING WORK PACKAGE")
            print("=" * 60)

            print(
                "JOB ID:",
                work_package.job_id
            )

            print(
                "COMPANIES:",
                work_package.companies
            )

            print(
                "AGENTS:",
                work_package.required_agents
            )

            execution_results = (
                self.executor.execute(
                    work_package
                )
            )
            if not execution_results:
                raise RuntimeError(
                    "Agent execution returned no results"
                )

            if execution_results.get(
                "status"
            ) == "failed":

                raise RuntimeError(
                    execution_results.get(
                        "error",
                        "Agent execution failed"
                    )
                )
                
            # ==========================================
            # Challenger Review
            # ==========================================

            challenger_result = None

            if (
                Config.ENABLE_CHALLENGER
                and not is_comparison
            ):

                research_result = (
                    execution_results.get(
                        "research"
                    )
                )

                risk_result = (
                    execution_results.get(
                        "risk"
                    )
                )

                should_challenge = (
                    (
                        Config.CHALLENGER_ON_RESEARCH
                        and bool(research_result)
                    )
                    or
                    (
                        Config.CHALLENGER_ON_RISK
                        and bool(risk_result)
                    )
                )

                if should_challenge:

                    try:

                        company = (
                            work_package.companies[0]
                            if work_package.companies
                            else {}
                        )

                        challenger_result = (
                            self.challenger_agent.analyze(
                                company=company,
                                research=research_result,
                                risk=risk_result,
                                quant=(
                                    execution_results.get(
                                        "quant"
                                    )
                                ),
                                signal_reconciliation=(
                                    execution_results.get(
                                        "signal_reconciliation"
                                    )
                                ),
                                market_context=(
                                    execution_results.get(
                                        "market_context"
                                    )
                                )
                            )
                        )

                    except Exception as challenger_error:

                        challenger_result = {
                            "status": "failed",
                            "error": str(
                                challenger_error
                            )
                        }

                    execution_results[
                        "challenger"
                    ] = challenger_result
                
            self.workflow_state.update_status(
                work_package.job_id,
                WorkflowStatus.QUALITY_REVIEW
            )
            if is_comparison:

                company_results = (
                    execution_results.get(
                        "company_results",
                        {}
                    )
                )


                if not isinstance(
                    company_results,
                    dict
                ):

                    company_results = {}


                if not company_results:

                    raise RuntimeError(
                        "Comparison execution "
                        "returned no company results"
                    )


                custom_formula = None


                formula_opportunity = (
                    comparison_plan.get(
                        "formula_opportunity",
                        "none"
                    )
                    if isinstance(
                        comparison_plan,
                        dict
                    )
                    else "none"
                )


                if formula_opportunity in {
                    "helpful",
                    "central"
                }:

                    metric_result = (
                        self.formula_metric_extractor
                        .extract(
                            company_results
                        )
                    )


                    available_metrics = (
                        metric_result.get(
                            "available_metrics",
                            []
                        )
                    )


                    company_metrics = (
                        metric_result.get(
                            "company_metrics",
                            {}
                        )
                    )


                    if (
                        available_metrics
                        and company_metrics
                    ):

                        formula_design = (
                            self.financial_formula_designer
                            .design(
                                message=message,

                                companies=(
                                    work_package.companies
                                ),

                                available_metrics=(
                                    available_metrics
                                )
                            )
                        )


                        if (
                            isinstance(
                                formula_design,
                                dict
                            )
                            and formula_design.get(
                                "components"
                            )
                        ):

                            formula_evaluation = (
                                self.formula_evaluator
                                .evaluate(
                                    formula=(
                                        formula_design
                                    ),

                                    company_metrics=(
                                        company_metrics
                                    )
                                )
                            )


                            if (
                                isinstance(
                                    formula_evaluation,
                                    dict
                                )
                                and formula_evaluation.get(
                                    "status"
                                ) == "completed"
                            ):

                                custom_formula = {
                                    "opportunity":
                                        formula_opportunity,

                                    "design":
                                        formula_design,

                                    "evaluation":
                                        formula_evaluation
                                }


                company_metrics = (
                    self.financial_metric_builder
                    .build_comparison(
                        company_results
                    )
                )

                financial_table = (
                    self.financial_table_formatter
                    .build_comparison_table(
                        company_metrics
                    )
                )
                
                quant_comparison = ""
                evidence_by_ticker = {}

                try:
                    evidence_by_ticker = (
                        self._build_comparison_evidence(
                            company_results
                        )
                    )
                    quant_comparison = (
                        self.quant_comparison_reviewer
                        .build(
                            company_metrics,
                            evidence_by_ticker
                        )
                    )
                except Exception as exc:
                    print(
                        "QUANT COMPARISON FAILED:",
                        repr(exc)
                    )

                comparison_result = (
                    self.comparison_agent
                    .analyze(
                        message=message,

                        quant_comparison=quant_comparison,

                        companies=(
                            work_package.companies
                        ),

                        company_results=(
                            company_results
                        ),

                        comparison_plan=(
                            comparison_plan
                        ),

                        custom_formula=(
                            custom_formula
                        ),

                        financial_table=(
                            financial_table
                        )
                    )
                )


                comparison_response = (
                    comparison_result.get(
                        "response",
                        ""
                    )
                )


                if not isinstance(
                    comparison_response,
                    str
                ):

                    comparison_response = ""


                comparison_response = (
                    comparison_response.strip()
                )

                consensus_summary = self._consensus_summary(
                    message,
                    {
                        "company_metrics": {
                            t: {
                                k: m.get("value")
                                for k, m in ms.items()
                                if isinstance(m, dict)
                            }
                            for t, ms in company_metrics.items()
                            if isinstance(ms, dict)
                        },
                        "company_results": {
                            t: {
                                k: v for k, v in r.items()
                                if k != "quant"
                            }
                            for t, r in company_results.items()
                            if isinstance(r, dict)
                        },
                        "quant_cross_reference": evidence_by_ticker,
                        "quant_comparison": quant_comparison,
                        "comparison_analysis": comparison_response,
                    }
                )
                if consensus_summary:
                    comparison_response = consensus_summary
                
                if financial_table:
                    comparison_response = (
                        "Financial Comparison\n\n"
                        + financial_table
                        + (
                            "\n\n" + quant_comparison
                            if quant_comparison
                            else ""
                        )
                        + "\n\n"
                        + comparison_response
                    )

                if not comparison_response:

                    raise RuntimeError(
                        "ComparisonAgent returned "
                        "no response"
                    )


                final_response = {
                    "approved":
                        True,

                    "confidence":
                        95,

                    "status":
                        "completed",

                    "response":
                        comparison_response,

                    "results":
                        execution_results
                }

                self._add_performance_charts(
                    final_response,
                    execution_results,
                    work_package
                )

                safe_response = (
                    self.outbound_gate
                    .prepare(
                        final_response
                    )
                )


                self.storage_manager.update_job_record(
                    job_id=(
                        work_package.job_id
                    ),

                    status="processing",

                    updates={
                        "comparison_result":
                            comparison_result,

                        "comparison_plan":
                            comparison_plan,

                        "custom_formula":
                            custom_formula,

                        "final_status":
                            "completed"
                    }
                )


                completed_path = (
                    self.storage_manager
                    .move_job(
                        job_id=(
                            work_package.job_id
                        ),

                        from_status="processing",

                        to_status="completed"
                    )
                )


                if (
                    completed_path is None
                    or not completed_path.exists()
                ):

                    raise RuntimeError(
                        "Completed comparison job "
                        "record was not persisted"
                    )


                self.workflow_state.update_status(
                    work_package.job_id,
                    WorkflowStatus.COMPLETED
                )


                safe_response[
                    "job_id"
                ] = work_package.job_id


                safe_response[
                    "status"
                ] = "completed"


                response_text = (
                    safe_response.get(
                        "response"
                    )
                )


                if response_text:

                    self.conversation_context.add_message(
                        conversation_key,
                        "assistant",
                        response_text
                    )


                return safe_response

            quality_context = (
                self.quality_context_builder.build(
                    execution_results
                )
            )

            quality_review = (
                self.quality_manager.review(
                    quality_context
                )
            )

            quality_approved = bool(
                quality_review.get(
                    "approved",
                    False
                )
            )

            quality_confidence = (
                quality_review.get(
                    "confidence",
                    0
                )
            )

            effective_approval = (
                quality_approved
                or not Config.QUALITY_REVIEW_BLOCKING
            )

            aggregated_results = (
                self.aggregator.aggregate(
                    execution_results,
                    quality_review
                )
            )

            final_response = (
                self.response_builder.build(
                    aggregated_results
                )
            )
            response_approved = bool(
                final_response.get(
                    "approved",
                    False
                )
            )

            if (
                Config.QUALITY_REVIEW_BLOCKING
                and response_approved != quality_approved
            ):

                raise RuntimeError(
                    "Quality review and final response "
                    "approval states do not match"
                )
            
            if effective_approval:

                response_text = (
                    self._build_company_response(
                        execution_results,
                        quality_review,
                        message=getattr(work_package, "original_message", "")
                    )
                )

                if response_text.strip():
                    response_text += (
                        "\n\n"
                        f"Quality Review Confidence: "
                        f"{self._display_confidence(quality_confidence, quality_context)}"
                    )
                                        
                    issues = quality_review.get(
                        "issues",
                        []
                    )

                    if issues:

                        response_text += (
                            "\n\n"
                            "Quality Review Notes:\n"
                            + "\n".join(
                                f"- {issue}"
                                for issue in issues
                            )
                        )
                    final_response[
                        "response"
                    ] = response_text

                self._add_performance_charts(
                    final_response,
                    execution_results,
                    work_package
                )

            else:

                quality_issues = (
                    quality_review.get(
                        "issues",
                        []
                    )
                )

                if not isinstance(
                    quality_issues,
                    list
                ):
                    quality_issues = []

                final_response["response"] = (
                    "The analysis completed, but the "
                    "result did not pass the final "
                    "quality review."
                )

                if (
                    Config.DEBUG
                    and quality_issues
                ):
                    final_response["response"] += (
                        "\n\nQuality issues:\n- "
                        + "\n- ".join(
                            str(issue)
                            for issue
                            in quality_issues
                        )
                    )
                       
            self.storage_manager.update_job_record(
                job_id=work_package.job_id,
                status="processing",
                updates={
                    "quality_review":
                        quality_review,

                    "final_status":
                        (
                            "completed"
                            if effective_approval
                            else "quality_rejected"
                        )
                }
            )
            
            self.workflow_state.update_status(
                    work_package.job_id,
                    WorkflowStatus.SANITIZING
                )
            safe_response = (
                    self.outbound_gate.prepare(
                    final_response
                )
            )
            
            response_text = (
                safe_response.get(
                    "response"
                )
            )

            if (
                not isinstance(
                    response_text,
                    str
                )
                or not response_text.strip()
            ):
                safe_response["response"] = (
                    "The analysis completed, but "
                    "no response message was "
                    "generated."
                )
            
            
            if (
                quality_approved 
                or not Config.QUALITY_REVIEW_BLOCKING
            ):
                completed_path = (
                    self.storage_manager.move_job(
                        job_id=work_package.job_id,
                        from_status="processing",
                        to_status="completed"
                    )
                )
                if (
                    completed_path is None
                    or not completed_path.exists()
                ):
                    raise RuntimeError(
                        "Completed job record was not persisted"
                    )
                    
                self.workflow_state.update_status(
                    work_package.job_id,
                    WorkflowStatus.COMPLETED
                )
                

            else:
                failed_path = (
                    self.storage_manager.fail_job(
                        job_id=work_package.job_id,
                        updates={
                            "final_status":
                                "quality_rejected",

                            "quality_review":
                                quality_review
                        }
                    )
                )
                if (
                    failed_path is None
                    or not failed_path.exists()
                ):
                    raise RuntimeError(
                        "Quality-rejected job record "
                        "was not persisted"
                    )
                self.workflow_state.update_status(
                    work_package.job_id,
                    WorkflowStatus.QUALITY_REJECTED
                )
            safe_response["job_id"] = (
                work_package.job_id
            )

            safe_response["status"] = (
                self.workflow_state
                .get_job(
                    work_package.job_id
                )["status"]
            )
            
            response_text = (
                safe_response.get(
                    "response"
                )
            )


            if response_text:

                self.conversation_context.add_message(
                    conversation_key,
                    "assistant",
                    response_text
                )
            return safe_response

        except Exception as e:
            
            print()
            print("=" * 100)
            print("HERMES EXCEPTION")
            print("=" * 100)

            traceback.print_exc()

            print(
                "ERROR:",
                str(e)
            )

            print("=" * 100)
            if (
                work_package is not None
                and hasattr(
                    work_package,
                    "job_id"
                )
            ):
                self.workflow_state.set_error(
                    work_package.job_id,
                    e
                )
                self.storage_manager.fail_job(
                    job_id=work_package.job_id,
                    updates={
                        "final_status": "failed",
                        "error": str(e)
                    }
                )
                job_id = (
                    work_package.job_id
                )

            else:
                job_id = None

            if job_id is not None:
                failure_message = self._format_failure_message(e)
                return self.outbound_gate.prepare({
                    "approved": False,
                    "confidence": 0,
                    "status": "failed",
                    "job_id": job_id,
                    "error": failure_message,
                    "issues": [
                        "No verified analysis result was produced."
                    ],
                    "response": failure_message
                })

            try:
                fallback_message = str(
                    message
                    or ""
                ).strip()

                fallback_research_plan = (
                    self.generic_research_planner
                    .plan(
                        fallback_message
                    )
                )

                if not isinstance(
                    fallback_research_plan,
                    dict
                ):
                    fallback_research_plan = {}

                fallback_search_queries = (
                    fallback_research_plan.get(
                        "queries",
                        []
                    )
                )

                if not isinstance(
                    fallback_search_queries,
                    list
                ):
                    fallback_search_queries = []

                fallback_evidence = (
                    self.generic_evidence_provider
                    .get_context(
                        query=fallback_message,
                        search_queries=(
                            fallback_search_queries
                        ),
                        research_plan=(
                            fallback_research_plan
                        )
                    )
                )

                if not isinstance(
                    fallback_evidence,
                    dict
                ):
                    fallback_evidence = {
                        "available": False,
                        "results": [],
                        "sources": []
                    }

                fallback_result = (
                    self.general_response_agent
                    .analyze(
                        message=fallback_message,
                        evidence=fallback_evidence,
                        research_plan=(
                            fallback_research_plan
                        )
                    )
                )

                safe_fallback = (
                    self.outbound_gate.prepare(
                        fallback_result
                    )
                )

                fallback_response_text = (
                    safe_fallback.get(
                        "response"
                    )
                )

                if fallback_response_text:
                    self.conversation_context.add_message(
                        conversation_key,
                        "assistant",
                        fallback_response_text
                    )

                return safe_fallback

            except Exception as fallback_error:
                print(
                    "EVIDENCE FALLBACK FAILED:",
                    fallback_error
                )
            
            error_response = {
                "approved": False,
                "confidence": 0,
                "status": "failed",
                "job_id": job_id,
                "issues": [
                    "The request could not be completed."
                ]
            }
                  

    def _build_challenger_section(
        self,
        execution_results
    ):

        challenger = (
            execution_results.get(
                "challenger",
                {}
            )
        )

        if not isinstance(
            challenger,
            dict
        ):
            return ""

        if challenger.get(
            "status"
        ) != "completed":
            return ""

        lines = []

        agreement = challenger.get(
            "agreement"
        )

        if agreement:
            lines.append(
                f"Agreement: {agreement}"
            )

        summary = challenger.get(
            "summary"
        )

        if summary:
            lines.append("")
            lines.append(
                str(summary).strip()
            )

        if not lines:
            return ""

        return (
            "Independent Review:\n"
            + "\n".join(lines)
        )
                
    def _build_evidence_section(
        self,
        execution_results
    ):

        market_context = (
            execution_results.get(
                "market_context",
                {}
            )
        )

        if not isinstance(
            market_context,
            dict
        ):
            return ""

        source_status = (
            market_context.get(
                "source_status",
                {}
            )
        )

        if not isinstance(
            source_status,
            dict
        ):
            return ""

        lines = []

        for key in [
            "financial_data",
            "sec_facts",
            "sec_filings",
            "macro",
            "news",
            "live_market_context",
            "social"
        ]:

            value = source_status.get(
                key
            )

            if value is not None:

                lines.append(
                    f"{key}: {value}"
                )

        if not lines:
            return ""

        return (
            "Evidence Availability:\n"
            + "\n".join(lines)
        )

    def _build_social_discussion_section(
        self,
        execution_results
    ):

        market_context = (
            execution_results.get(
                "market_context",
                {}
            )
        )

        if not isinstance(
            market_context,
            dict
        ):
            return ""

        social_summary = (
            market_context.get(
                "social_summary",
                {}
            )
        )
        print()
        print("=" * 50)
        print("HERMES SOCIAL")
        print("=" * 50)

        print(
            social_summary
        )

        if not isinstance(
            social_summary,
            dict
        ):
            return ""

        status = (
            social_summary.get(
                "status",
                "unavailable"
            )
        )

        if status == "unavailable":
            return ""

        lines = []

        discussion_volume = (
            social_summary.get(
                "discussion_volume"
            )
        )

        if discussion_volume is not None:

            lines.append(
                f"Discussion Volume: "
                f"{discussion_volume}"
            )
        
        status = (
            social_summary.get(
                "status",
                "unavailable"
            )
        )

        lines.append(
            f"Status: {status}"
        )

        platforms = (
            social_summary.get(
                "platforms",
                []
            )
        )

        if platforms:

            lines.append(
                "Platforms: "
                + ", ".join(
                    platforms
                )
            )

        platform_counts = (
            social_summary.get(
                "platform_counts",
                {}
            )
        )

        if platform_counts:

            count_lines = []

            for platform, count in (
                platform_counts.items()
            ):
                count_lines.append(
                    f"{platform}: {count}"
                )

            lines.append(
                "Platform Activity: "
                + ", ".join(
                    count_lines
                )
            )

        discussion_themes = (
            social_summary.get(
                "discussion_themes",
                []
            )
        )

        if discussion_themes:

            lines.append(
                "Recurring Themes: "
                + ", ".join(
                    discussion_themes[:10]
                )
            )

        if not lines:
            return ""

        lines.append("")

        lines.append(
            "These observations summarize "
            "retrieved public discussion. "
            "They provide supplemental "
            "context and should not be "
            "treated as verified facts, "
            "financial evidence, or "
            "evidence of public consensus."
        )

        return (
            "Public Discussion Signals:\n"
            + "\n".join(
                lines
            )
        )

    def _build_challenger_section(
        self,
        execution_results
    ):

        challenger = (
            execution_results.get(
                "challenger",
                {}
            )
        )

        if not isinstance(
            challenger,
            dict
        ):
            return ""

        if challenger.get(
            "status"
        ) != "completed":
            return ""

        lines = []

        agreement = challenger.get(
            "agreement"
        )

        if agreement:

            lines.append(
                f"Agreement: {agreement}"
            )

        summary = challenger.get(
            "summary"
        )

        if summary:

            lines.append(
                ""
            )

            lines.append(
                str(summary)
                .strip()
            )

        if not lines:
            return ""

        return (
            "Independent Review:\n"
            + "\n".join(
                lines
            )
        )


    def _display_confidence(self, llm_confidence, quality_context):
        scores = []
        if isinstance(llm_confidence, (int, float)):
            scores.append(int(llm_confidence))
        try:
            heuristic = self.quality_manager._build_fallback_review(
                quality_context
            )
            scores.append(int(heuristic.get("confidence", 0)))
        except Exception as exc:
            print("CONFIDENCE HEURISTIC FAILED:", repr(exc))
        best = max(scores) if scores else 0
        print("QUALITY CONFIDENCE (llm, best):", llm_confidence, best)
        final = "As Per Review" if best < 70 else str(min(best, 100))
        if isinstance(llm_confidence, (int, float)):
            final += f" (Reviewer score: {int(llm_confidence)})"
        return final

    def _consensus_summary(self, message, sources):
        try:
            return self.consensus_agent.synthesize(message, sources)
        except Exception as exc:
            print("CONSENSUS FAILED:", repr(exc))
            return ""

    def _build_portfolio_quant_section(self, quant_executions):
        """Per-ticker quant tables plus a cross-ticker table; also returns data for the consensus agent."""
        if not quant_executions:
            return "", {}
        metrics_by_ticker = (
            self.financial_metric_builder.build_comparison(quant_executions)
        )
        evidence_by_ticker = self._build_comparison_evidence(quant_executions)
        parts = []
        for ticker, metrics in metrics_by_ticker.items():
            table_text = self.financial_table_formatter.build_category_table(
                metrics, "quantitative_models"
            )
            if table_text:
                parts.append(f"**{ticker} Quant**\n\n{table_text}")
        comparison = ""
        try:
            comparison = self.quant_comparison_reviewer.build(
                metrics_by_ticker, evidence_by_ticker
            )
        except Exception as exc:
            print("PORTFOLIO QUANT COMPARISON FAILED:", repr(exc))
        if comparison:
            parts.append(comparison)
        return "\n\n".join(parts), {
            "quant_metrics": {
                t: {k: m.get("value") for k, m in ms.items() if isinstance(m, dict)}
                for t, ms in metrics_by_ticker.items()
            },
            "quant_cross_reference": evidence_by_ticker,
            "quant_comparison": comparison,
        }

    def _build_comparison_evidence(
        self,
        company_results
    ):
        from concurrent.futures import ThreadPoolExecutor

        def gather(item):
            ticker, result = item
            try:
                return ticker, self.quant_evidence_builder.build(
                    result
                )
            except Exception as exc:
                print(
                    "QUANT CROSS-REFERENCE FAILED:",
                    ticker,
                    repr(exc)
                )
                return ticker, {}

        items = [
            (ticker, result)
            for ticker, result in company_results.items()
            if isinstance(result, dict)
        ]
        if not items:
            return {}
        with ThreadPoolExecutor(
            max_workers=min(4, len(items))
        ) as pool:
            return dict(pool.map(gather, items))

    def _build_company_response(
        self,
        execution_results,
        quality_review,
        message=""
    ):
        
        
        market_context = (
            execution_results.get(
                "market_context",
                {}
            )
        )

             
        financial_metrics = (
            self.financial_metric_builder
            .build(
                execution_results
            )
        )

        quant_evidence = {}

        if financial_metrics:
            try:
                quant_evidence = (
                    self.quant_evidence_builder
                    .build(
                        execution_results
                    )
                )
            except Exception as exc:
                print(
                    "QUANT CROSS-REFERENCE FAILED:",
                    repr(exc)
                )

        financial_table = (
           self.financial_table_formatter
        .build_sectioned_tables(
            financial_metrics,
            quant_evidence
        )
            if financial_metrics
            else ""
        )

        research = (
            execution_results.get(
                "research"
            )
        )

        risk = (
            execution_results.get(
                "risk",
                {}
            )
        )

        social_discussion_section = (
            self._build_social_discussion_section(
                execution_results
            )
        )
        
        challenger_section = (
            self._build_challenger_section(
                execution_results
            )
        )
        
        evidence_section = (
            self._build_evidence_section(
                execution_results
            )
        )
        
        challenger_section = (
            self._build_challenger_section(
                execution_results
            )
        )
        
        market_context = (
            execution_results.get(
                "market_context",
                {}
            )
        )

        if not isinstance(
            research,
            str
        ):

            research = ""


        consensus_summary = self._consensus_summary(
            message or "",
            {
                "metrics": {
                    k: m.get("value")
                    for k, m in financial_metrics.items()
                    if isinstance(m, dict)
                },
                "quant_cross_reference": quant_evidence,
                "research": research,
                "risk": risk,
                "challenger": challenger_section,
                "social": social_discussion_section,
                "market_context": market_context,
                "sentiment": execution_results.get("sentiment"),
            }
        )

        sections = []

        if financial_table:
            sections.append(
                financial_table
            )

        etf_section = self._build_etf_fund_section(
            market_context
        )
        if etf_section:
            sections.append(etf_section)
            
        if evidence_section:
            print()
            print("EVIDENCE AVAILABILITY (debug only):")
            print(evidence_section)

        if consensus_summary:
            sections.append(
                "**Summary**\n\n" + consensus_summary
            )
            research = ""
            challenger_section = ""
            social_discussion_section = ""
            risk = {}

        if research.strip():
            sections.append(
                research.strip()
            )
            
        if challenger_section:
            sections.append(
                challenger_section
            )
        
        if social_discussion_section:

            sections.append(
                social_discussion_section
            )


        if isinstance(
            risk,
            dict
        ):

            overall_risk = risk.get(
                "overall_risk"
            )

            risk_score = risk.get(
                "risk_score"
            )

            signal_uncertainty = risk.get(
                "signal_uncertainty"
            )

            risk_lines = []


            if overall_risk:

                risk_lines.append(
                    f"Overall Risk: {overall_risk}"
                )


            if risk_score is not None:

                risk_lines.append(
                    f"Risk Score: {risk_score}"
                )


            if signal_uncertainty:

                risk_lines.append(
                    "Signal Uncertainty: "
                    f"{signal_uncertainty}"
                )


            if risk_lines:

                sections.append(
                    "Risk Summary:\n"
                    + "\n".join(
                        risk_lines
                    )
                )

        if isinstance(market_context, dict):
            sections.append(
                EvidenceProvenance.format_note(
                    market_context,
                    requires_current=market_context.get(
                        "requires_live_data",
                        False
                    )
                )
            )

        return "\n\n".join(
            sections
        )

    def _build_etf_fund_section(self, market_context):
        if not isinstance(market_context, dict):
            return ""
        company = market_context.get("company")
        if (
            not isinstance(company, dict)
            or company.get("entity_type") != "etf"
        ):
            return ""

        classification = company.get(
            "instrument_classification"
        )
        classification_status = (
            classification.get("classification_status")
            if isinstance(classification, dict)
            else None
        )
        context = market_context.get("etf_fund_data")
        if not isinstance(context, dict):
            warning = (
                "\nInstrument type was not verified against "
                "fund metadata."
                if classification_status == "unverified"
                else ""
            )
            return (
                "ETF Fund Profile:\n"
                "Fund profile and holdings data were unavailable."
                + warning
            )
        if context.get("status") != "available":
            message = "Fund profile and holdings data were unavailable"
            if context.get("error"):
                message += f": {context['error']}"
            else:
                message += "."
            if classification_status == "unverified":
                message += (
                    "\nInstrument type was not verified against "
                    "fund metadata."
                )
            return "ETF Fund Profile:\n" + message

        lines = ["ETF Fund Profile:"]
        if classification_status == "unverified":
            lines.append(
                "- Instrument type: ETF (explicit user label; "
                "metadata unverified)"
            )
        overview = context.get("fund_overview")
        if isinstance(overview, dict):
            labels = {
                "categoryName": "Category",
                "family": "Fund family",
                "legalType": "Legal structure"
            }
            lines.extend(
                f"- {label}: {overview[key]}"
                for key, label in labels.items()
                if overview.get(key) not in (None, "")
            )

        operations = context.get("fund_operations")
        if isinstance(operations, list):
            operation_labels = {
                "Annual Report Expense Ratio": "Expense ratio",
                "Annual Holdings Turnover": "Holdings turnover",
                "Total Net Assets": "Net assets"
            }
            for operation in operations:
                if not isinstance(operation, dict):
                    continue
                label = operation_labels.get(
                    operation.get("key")
                )
                value = operation.get(company.get("ticker"))
                if label and value is not None:
                    if isinstance(value, (int, float)):
                        if label == "Net assets":
                            value = f"${value:,.0f}"
                        else:
                            value = f"{value * 100:.2f}%"
                    lines.append(f"- {label}: {value}")

        asset_classes = context.get("asset_classes")
        if isinstance(asset_classes, dict) and asset_classes:
            class_summary = ", ".join(
                f"{asset_class}: {weight * 100:.2f}%"
                if isinstance(weight, (int, float))
                else f"{asset_class}: {weight}"
                for asset_class, weight in asset_classes.items()
                if weight is not None
            )
            if class_summary:
                lines.append(f"- Asset classes: {class_summary}")

        holdings = context.get("top_holdings")
        if isinstance(holdings, list) and holdings:
            lines.append("- Top holdings:")
            for holding in holdings:
                if not isinstance(holding, dict):
                    continue
                name = holding.get("Name")
                symbol = holding.get("key")
                weight = holding.get("Holding Percent")
                if name or symbol:
                    label = " ".join(
                        str(value)
                        for value in (
                            name,
                            f"({symbol})" if symbol else ""
                        )
                        if value
                    )
                    if weight is not None:
                        if isinstance(weight, (int, float)):
                            weight = f"{weight * 100:.2f}%"
                        label += f": {weight}"
                    lines.append(f"  - {label}")

        sectors = context.get("sector_weightings")
        if isinstance(sectors, dict) and sectors:
            sector_summary = ", ".join(
                (
                    f"{sector}: {weight * 100:.2f}%"
                    if isinstance(weight, (int, float))
                    else f"{sector}: {weight}"
                )
                for sector, weight in sectors.items()
                if weight is not None
            )
            if sector_summary:
                lines.append(f"- Sector weightings: {sector_summary}")

        if len(lines) == 1:
            lines.append(
                "Fund profile and holdings data were unavailable."
            )
        return "\n".join(lines)

    def _add_performance_charts(
        self,
        response,
        execution_results,
        work_package
    ):
        if not isinstance(execution_results, dict):
            return

        quant = execution_results.get("quant")
        quant_results = (
            quant.get("results", [])
            if isinstance(quant, dict)
            else []
        )
        if not isinstance(quant_results, list) or not quant_results:
            return

        quantified_tickers = set()
        for result in quant_results:
            if not isinstance(result, dict):
                continue
            company = result.get("company")
            if not isinstance(company, dict):
                continue
            ticker = str(company.get("ticker") or "").strip().upper()
            if ticker:
                quantified_tickers.add(ticker)

        attachments = []
        status_lines = [
            "Performance charts (trailing 1 year):"
        ]
        evaluation_lines = []
        companies = getattr(work_package, "companies", [])
        if not isinstance(companies, list):
            return
        for company in companies:
            if not isinstance(company, dict):
                continue
            ticker = str(company.get("ticker") or "").strip().upper()
            if ticker not in quantified_tickers:
                continue

            try:
                chart = self.performance_chart_provider.generate(company)
            except Exception as exc:
                chart = {
                    "status": "failed",
                    "ticker": ticker,
                    "error": (
                        "Chart generation encountered an error: "
                        f"{exc}"
                    )
                }

            if (
                isinstance(chart, dict)
                and chart.get("status") == "completed"
                and chart.get("path")
            ):
                attachments.append({
                    "path": chart["path"],
                    "filename": f"{ticker}_performance_1y.png",
                    "caption": chart.get("caption", "")
                })
                status_lines.append(
                    f"- {ticker}: chart attached."
                )
                evaluation = self._evaluate_vs_sp500(ticker, chart)
                if evaluation:
                    evaluation_lines.append(evaluation)
                if (
                    chart.get("industry_status") == "unavailable"
                    and chart.get("industry_error")
                ):
                    status_lines.append(
                        f"  Industry peer average unavailable: "
                        f"{chart['industry_error']}"
                    )
            else:
                error = (
                    chart.get("error")
                    if isinstance(chart, dict)
                    else None
                )
                status_lines.append(
                    f"- {ticker}: performance chart unavailable"
                    + (f": {error}" if error else ".")
                )

        if not status_lines[1:]:
            return
        if attachments:
            response["attachments"] = attachments
        response_text = response.get("response")
        if isinstance(response_text, str) and response_text.strip():
            evaluation_text = (
                "**Performance vs S&P 500 (trailing 1 year):**\n"
                + "\n".join(evaluation_lines)
                + "\n\n"
                if evaluation_lines
                else ""
            )
            response["response"] = (
                response_text.rstrip()
                + "\n\n"
                + evaluation_text
                + "\n".join(status_lines)
            )

    @staticmethod
    def _evaluate_vs_sp500(ticker, chart):
        asset = chart.get("asset_return_pct")
        bench = chart.get("benchmark_return_pct")
        if not isinstance(asset, (int, float)) or not isinstance(
            bench, (int, float)
        ):
            return ""
        gap = asset - bench
        label = chart.get("benchmark_label") or "S&P 500"
        if abs(gap) < 1:
            verdict = "roughly in line with the index"
        elif gap > 0:
            verdict = (
                f"outperformed by {gap:.1f} percentage points"
                + (
                    f" ({asset / bench:.1f}x the index return)"
                    if bench > 0 and asset > 0 and asset / bench >= 1.5
                    else ""
                )
            )
        else:
            verdict = f"underperformed by {abs(gap):.1f} percentage points"
        note = ""
        if asset < 0 <= bench:
            note = " It lost value while the index gained."
        elif gap > 0 and asset > 0:
            note = " Higher returns usually come with higher volatility."
        return (
            f"- {ticker} returned {asset:+.1f}% versus {bench:+.1f}% for "
            f"{label} - {verdict}.{note}"
        )

    def _add_portfolio_performance_charts(self, response, holdings):
        try:
            result = self.portfolio_performance_chart_provider.generate(
                holdings
            )
        except Exception as exc:
            result = {
                "status": "failed",
                "error": f"Chart generation encountered an error: {exc}"
            }

        attached_count = 0
        if (
            isinstance(result, dict)
            and result.get("status") == "completed"
            and isinstance(result.get("charts"), list)
        ):
            attachments = response.get("attachments", [])
            if not isinstance(attachments, list):
                attachments = []
            filenames = (
                "portfolio_ytd_return.png",
                "portfolio_rolling_12_month_return.png"
            )
            for chart, filename in zip(result["charts"], filenames):
                if not isinstance(chart, dict) or not chart.get("path"):
                    continue
                attachments.append({
                    "path": chart["path"],
                    "filename": filename,
                    "caption": chart.get("caption", "")
                })
                attached_count += 1
            if attached_count:
                response["attachments"] = attachments

        if attached_count == 2:
            status = (
                "Portfolio return charts attached: year-to-date and "
                "rolling 12-month, compared with the S&P 500 and DJI."
            )
        else:
            error = (
                result.get("error")
                if isinstance(result, dict)
                else None
            )
            status = (
                "Portfolio return charts unavailable"
                + (f": {error}" if error else ".")
            )

        response_text = response.get("response")
        if isinstance(response_text, str) and response_text.strip():
            response["response"] = (
                response_text.rstrip()
                + "\n\n"
                + status
            )
