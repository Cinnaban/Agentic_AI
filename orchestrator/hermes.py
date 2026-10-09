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
        self.portfolio_request_parser = (
            PortfolioRequestParser()
        )
        self.portfolio_evaluation_agent = (
            PortfolioEvaluationAgent()
        )

        self.portfolio_context_provider = (
            PortfolioContextProvider()
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
        self.conversation_context = (
            ConversationContext()
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

            if is_evaluation_request:

                return {
                    "route":
                        "general_evaluation"
                }

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

                    work_package = (
                        self.build_workflow(
                            effective_message
                        )
                    )


            else:

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
                        f"Intent: {intent}\n\n"
                        f"Provide factual information "
                        f"about {company_text}. "
                        f"Do not perform valuation, "
                        f"forecasting, investment "
                        f"analysis, recommendations, "
                        f"or financial evaluation."
                    )

                    general_result = (
                        self.general_response_agent
                        .analyze(
                            info_prompt
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
                    holdings = (
                        work_package.get(
                            "holdings",
                            []
                        )
                    )

                    if not isinstance(
                        holdings,
                        list
                    ):
                        holdings = []

                    minimum_holdings = int(
                        getattr(
                            Config,
                            "PORTFOLIO_CONTEXT_MIN_HOLDINGS",
                            3
                        )
                    )

                    portfolio_context = {}

                    if (
                        Config.PORTFOLIO_EVALUATION_ENABLED
                        and len(holdings)
                        >= minimum_holdings
                    ):
                        portfolio_context = (
                            self.portfolio_context_provider
                            .get_context(
                                holdings
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
                
                if requires_live_data:

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

                general_result = (
                    self.general_response_agent
                    .analyze(
                        message
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
                
                comparison_result = (
                    self.comparison_agent
                    .analyze(
                        message=message,

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
                
                if financial_table:
                    comparison_response = (
                        "Financial Comparison\n\n"
                        + financial_table
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
                        quality_review
                    )
                )

                if response_text.strip():
                    response_text += (
                        "\n\n"
                        f"Quality Review Confidence: "
                        f"{quality_confidence}"
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
                        "final_status": "failed"
                    }
                )
                job_id = (
                    work_package.job_id
                )

            else:
                job_id = None


            try:
                fallback_result = (
                    self.general_response_agent
                    .analyze(
                        f"""
                The specialized workflow could not complete.

                Failure:
                {str(e)}

                Provide the best possible response using
                general reasoning and available context.

                Do not claim access to unavailable data.

                USER REQUEST:

                {message}
                """
                    )
                )

                return self.outbound_gate.prepare(
                    fallback_result
                )

            except Exception as fallback_error:
                print(
                    "GENERAL FALLBACK FAILED:",
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


    def _build_company_response(
        self,
        execution_results,
        quality_review
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

        financial_table = (
           self.financial_table_formatter
        .build_sectioned_tables(
            financial_metrics
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


        sections = []

        if financial_table:
            sections.append(
                financial_table
            )
            
        if evidence_section:
            sections.append(
                evidence_section
            )

        if research.strip():
            sections.append(
                research.strip()
            )
            
        if challenger_section:
            sections.append(
                challenger_section
            )
        
        if evidence_section:
            sections.append(
                evidence_section
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

        return "\n\n".join(
            sections
        )   
