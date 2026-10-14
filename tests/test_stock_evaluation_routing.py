import unittest
from unittest.mock import Mock
import json

from agents.company_detection_agent import CompanyDetectionAgent
from workers.agent_executor import AgentExecutor
from orchestrator.hermes import Hermes
from orchestrator.portfolio_request_parser import PortfolioRequestParser
from job_queue.job_factory import JobFactory


class CompanyAgent:

    def __init__(self, result):
        self.result = result

    def analyze(self, message):
        return self.result


class AssignmentAgent:

    def analyze(self, companies, message):
        return {
            "research": False,
            "sentiment": False,
            "quant": False,
            "risk": False
        }


class QuantAssignmentAgent:

    def analyze(self, companies, message):
        return {
            "research": True,
            "sentiment": False,
            "quant": True,
            "risk": True
        }


class InstrumentTypeProvider:

    def resolve(self, ticker, message):
        entity_type = "etf" if "ETF" in message.upper() else "stock"
        return {
            "entity_type": entity_type,
            "classification_status": "resolved",
            "classification_source": "test",
            "sector": "Technology",
            "industry": "Semiconductors",
            "etf_context": {
                "status": "available"
            } if entity_type == "etf" else None
        }

class PortfolioInstrumentTypeProvider:

    def resolve(self, ticker, message):
        if ticker == "SOXX":
            return {
                "entity_type": "etf",
                "classification_status": "resolved",
                "etf_context": {"status": "available"}
            }
        if ticker == "NVDA":
            return {
                "entity_type": "stock",
                "classification_status": "resolved",
                "sector": "Technology",
                "industry": "Semiconductors"
            }
        return {
            "entity_type": "security",
            "classification_status": "unresolved"
        }


class StockEvaluationRoutingTests(unittest.TestCase):

    def setUp(self):
        self.hermes = Hermes.__new__(Hermes)
        self.hermes.portfolio_request_parser = (
            PortfolioRequestParser()
        )
        self.hermes.job_factory = JobFactory()
        self.hermes.company_agent = CompanyAgent({
            "is_company_request": True,
            "intent": "general_information",
            "companies": [
                {
                    "name": "EUV",
                    "ticker": "EUV",
                    "entity_type": "security"
                }
            ]
        })
        self.hermes.assignment_agent = AssignmentAgent()
        self.hermes.etf_fund_provider = InstrumentTypeProvider()

    def test_explicit_single_etf_evaluation_requires_quant_research_and_risk(self):
        workflow = self.hermes.build_workflow(
            "Evaluate the ETF EUV"
        )

        self.assertEqual(workflow.companies[0]["ticker"], "EUV")
        self.assertEqual(workflow.companies[0]["entity_type"], "etf")
        self.assertTrue(workflow.required_agents["quant"])
        self.assertTrue(workflow.required_agents["research"])
        self.assertTrue(workflow.required_agents["risk"])

    def test_quant_stock_analysis_is_classified_before_worker_submission(self):
        self.hermes.company_agent = CompanyAgent({
            "is_company_request": True,
            "intent": "analysis",
            "companies": [{
                "name": "NVIDIA",
                "ticker": "NVDA",
                "entity_type": "security"
            }]
        })
        self.hermes.assignment_agent = QuantAssignmentAgent()

        workflow = self.hermes.build_workflow("Analyze Nvidia")

        self.assertEqual(workflow.companies[0]["entity_type"], "stock")
        self.assertEqual(workflow.companies[0]["sector"], "Technology")
        self.assertEqual(workflow.companies[0]["industry"], "Semiconductors")
        self.assertTrue(workflow.required_agents["quant"])

    def test_explicit_analyze_ticker_forces_quant_even_if_classifier_says_information(self):
        self.hermes.company_agent = CompanyAgent({
            "is_company_request": True,
            "intent": "general_information",
            "companies": [{
                "name": "Alphabet",
                "ticker": "GOOGL",
                "entity_type": "security"
            }]
        })
        self.hermes.assignment_agent = AssignmentAgent()

        workflow = self.hermes.build_workflow("Analyze GOOGL")

        self.assertEqual(workflow.companies[0]["ticker"], "GOOGL")
        self.assertTrue(workflow.required_agents["quant"])

    def test_lowercase_intel_analysis_resolves_to_quant_instead_of_model_drift(self):
        detector = CompanyDetectionAgent()
        detector.ollama = Mock()
        detector.ollama.generate.return_value = {
            "response": json.dumps({
                "is_company_request": True,
                "intent": "general_information",
                "companies": [{
                    "name": "KeyCorp",
                    "ticker": "KEY"
                }]
            })
        }
        self.hermes.company_agent = detector
        self.hermes.assignment_agent = AssignmentAgent()
        self.hermes.etf_fund_provider = InstrumentTypeProvider()

        workflow = self.hermes.build_workflow("Analyze intel")

        self.assertEqual(
            [company["ticker"] for company in workflow.companies],
            ["INTC"]
        )
        self.assertEqual(workflow.companies[0]["name"], "Intel")
        self.assertTrue(workflow.required_agents["quant"])

    def test_quant_failure_is_propagated_without_attempting_market_context(self):
        executor = AgentExecutor.__new__(AgentExecutor)
        executor.freshness_detector = type(
            "FreshnessDetectorMock",
            (),
            {"requires_live_data": lambda self, message: False}
        )()
        executor.quant_agent = type(
            "QuantAgentMock",
            (),
            {
                "analyze": lambda self, package: {
                    "status": "failed",
                    "error": "Gaming PC returned no quant results"
                }
            }
        )()
        executor.market_context_provider = Mock()
        work_package = type(
            "WorkPackage",
            (),
            {
                "companies": [{"name": "Intel", "ticker": "INTC"}],
                "required_agents": {"quant": True},
                "original_message": "Evaluate INTC"
            }
        )()

        result = executor.execute(work_package)

        self.assertEqual(result["status"], "failed")
        self.assertIn("no quant results", result["error"])
        executor.market_context_provider.get_context.assert_not_called()

    def test_multi_company_quant_failure_stops_before_partial_analysis(self):
        executor = AgentExecutor.__new__(AgentExecutor)
        executor.freshness_detector = type(
            "FreshnessDetectorMock",
            (),
            {"requires_live_data": lambda self, message: False}
        )()
        executor.quant_agent = type(
            "QuantAgentMock",
            (),
            {
                "analyze": lambda self, package: {
                    "status": "failed",
                    "error": "Gaming PC compute service unavailable"
                }
            }
        )()
        work_package = type(
            "WorkPackage",
            (),
            {
                "companies": [
                    {"name": "Intel", "ticker": "INTC"},
                    {"name": "AMD", "ticker": "AMD"}
                ],
                "required_agents": {"quant": True},
                "original_message": "Compare Intel and AMD"
            }
        )()

        result = executor.execute(work_package)

        self.assertEqual(result["status"], "failed")
        self.assertIn("Gaming PC", result["error"])

    def test_worker_failure_message_explains_the_next_step(self):
        message = Hermes._format_failure_message(
            "All Gaming PC quant requests failed: "
            "Cannot connect to the Gaming PC compute service."
        )

        self.assertIn("quantitative analysis could not run", message)
        self.assertIn("Check that the Gaming PC compute service is online", message)
        self.assertIn("No verified result was produced", message)

    def test_portfolio_evaluation_keeps_portfolio_route(self):
        workflow = self.hermes.build_workflow(
            "Evaluate my portfolio"
        )

        self.assertEqual(workflow["route"], "general_evaluation")
        self.assertEqual(workflow["evaluation_type"], "portfolio")

    def test_evaluation_without_a_security_keeps_generic_route(self):
        self.hermes.company_agent = CompanyAgent({
            "is_company_request": False,
            "intent": "general_information",
            "companies": []
        })

        workflow = self.hermes.build_workflow(
            "Evaluate this idea"
        )

        self.assertEqual(workflow["route"], "general_evaluation")

    def test_portfolio_holding_classification_distinguishes_stocks_and_etfs(self):
        self.hermes.etf_fund_provider = PortfolioInstrumentTypeProvider()
        holdings = [
            {"ticker": "NVDA", "weight": 60},
            {"ticker": "SOXX", "weight": 30},
            {"ticker": "UNKNOWN", "weight": 10}
        ]

        result = self.hermes._classify_portfolio_holdings(holdings)

        self.assertEqual(result[0]["entity_type"], "stock")
        self.assertEqual(result[0]["sector"], "Technology")
        self.assertEqual(result[0]["industry"], "Semiconductors")
        self.assertEqual(result[1]["entity_type"], "etf")
        self.assertEqual(result[1]["etf_context"]["status"], "available")
        self.assertEqual(result[2]["entity_type"], "unresolved")


if __name__ == "__main__":
    unittest.main()
