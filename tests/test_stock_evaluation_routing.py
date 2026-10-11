import unittest

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
