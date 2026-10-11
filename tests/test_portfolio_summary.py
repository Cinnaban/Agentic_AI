import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from agents.portfolio_evaluation_agent import PortfolioEvaluationAgent
from data.providers.portfolio_context_provider import PortfolioContextProvider
from workers.etf_portfolio_evaluation import (
    generate_etf_portfolio_appendix
)


class PortfolioSummaryTests(unittest.TestCase):

    def test_portfolio_composition_splits_stock_etf_and_unresolved_weights(self):
        result = PortfolioEvaluationAgent._build_portfolio_overview([
            {"ticker": "NVDA", "weight": 50, "entity_type": "stock"},
            {"ticker": "SOXX", "weight": 30, "entity_type": "etf"},
            {"ticker": "UNKN", "weight": 10, "entity_type": "unresolved"}
        ])

        self.assertIn("1 stock, 1 ETF, 1 unclassified", result)
        self.assertIn("stocks 50.00%, ETFs 30.00%", result)
        self.assertIn("total 90.00%", result)
        self.assertIn("do not total 100%", result)
        self.assertIn("excluded from stock/ETF comparisons", result)

    def test_etf_snapshot_uses_fund_metrics_not_company_valuation_fields(self):
        provider = PortfolioContextProvider.__new__(PortfolioContextProvider)
        captured = {}

        def get_context(**kwargs):
            captured.update(kwargs)
            return {
                "company": kwargs["company"],
                "financial_data": {
                    "price": 500,
                    "trailing_pe": 25,
                    "dividend_yield": 0.01,
                    "beta": 1.1
                },
                "source_status": {},
                "social_summary": {"status": "unavailable"}
            }

        provider.market_context_provider = SimpleNamespace(
            get_context=get_context
        )
        etf_context = {
            "status": "available",
            "asset_classes": {"equity": 1.0},
            "top_holdings": [{"symbol": "NVDA"}]
        }

        result = provider.get_context(
            holdings=[{
                "ticker": "SOXX",
                "weight": 20,
                "entity_type": "etf",
                "classification_status": "resolved",
                "etf_context": etf_context
            }]
        )

        snapshot = result["holdings"][0]
        self.assertEqual(captured["company"]["entity_type"], "etf")
        self.assertEqual(captured["company"]["etf_context"], etf_context)
        self.assertEqual(snapshot["entity_type"], "etf")
        self.assertNotIn("trailing_pe", snapshot["financial_summary"])
        self.assertEqual(snapshot["etf_context"]["top_holdings"], [
            {"symbol": "NVDA"}
        ])
        self.assertEqual(result["financial_coverage"]["available_count"], 1)

    def test_holding_coverage_labels_etfs_without_company_valuation_metrics(self):
        agent = PortfolioEvaluationAgent.__new__(PortfolioEvaluationAgent)
        coverage = agent._build_holding_coverage({
            "holding_count": 1,
            "researched_count": 1,
            "holdings": [{
                "ticker": "SOXX",
                "entity_type": "etf",
                "classification_status": "resolved",
                "weight": 100,
                "financial_summary": {
                    "price": 200,
                    "dividend_yield": 0.01,
                    "beta": 1.2
                },
                "etf_context": {
                    "asset_classes": {"equity": 1.0},
                    "top_holdings": [{"symbol": "NVDA"}]
                }
            }]
        })

        self.assertIn("SOXX (ETF)", coverage)
        self.assertIn("Distribution Yield", coverage)
        self.assertIn("reported top holdings: NVDA", coverage)
        self.assertNotIn("Trailing P/E", coverage)
        self.assertNotIn("Market Cap", coverage)

    def test_empty_portfolio_requests_a_valid_holding_list_without_model_call(self):
        agent = PortfolioEvaluationAgent()
        agent.ollama.generate = Mock()

        result = agent.analyze(
            message="Evaluate my portfolio",
            holdings=[]
        )

        self.assertIn("couldn't identify portfolio holdings", result["response"])
        agent.ollama.generate.assert_not_called()

    def test_etf_update_appendix_reports_unweighted_metrics_and_no_weights(self):
        result = generate_etf_portfolio_appendix([
            {
                "ticker": "SOXX",
                "expense_ratio": 0.0035,
                "dividend_yield": 0.01,
                "beta": 1.2
            },
            {
                "ticker": "SPY",
                "expense_ratio": 0.0009,
                "dividend_yield": 0.015,
                "beta": 1.0
            }
        ])

        self.assertIn("unweighted averages", result)
        self.assertIn("Unweighted average expense ratio: 0.22%", result)
        self.assertIn("Unweighted average distribution yield: 1.25%", result)
        self.assertIn("Unweighted average beta: 1.10", result)
        self.assertIn("historical market-sensitivity measure", result)

    def test_etf_update_appendix_handles_missing_metrics_explicitly(self):
        result = generate_etf_portfolio_appendix([
            {"ticker": "SOXX"}
        ])

        self.assertIn("Expense ratio: no retrieved values.", result)
        self.assertIn("Distribution yield: no retrieved values.", result)
        self.assertIn("Beta: no retrieved values.", result)


if __name__ == "__main__":
    unittest.main()
