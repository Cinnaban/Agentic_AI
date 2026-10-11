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

    def test_explicit_single_ticker_evaluation_requires_quant(self):
        workflow = self.hermes.build_workflow(
            "Evaluate the ETF EUV"
        )

        self.assertEqual(workflow.companies[0]["ticker"], "EUV")
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
