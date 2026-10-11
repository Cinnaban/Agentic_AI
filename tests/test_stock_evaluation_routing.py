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
            "etf_context": {
                "status": "available"
            } if entity_type == "etf" else None
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


if __name__ == "__main__":
    unittest.main()
