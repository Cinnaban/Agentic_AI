import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from agents.portfolio_evaluation_agent import PortfolioEvaluationAgent
from data.providers.portfolio_context_provider import PortfolioContextProvider
from data.providers.portfolio_allocation_chart_provider import (
    PortfolioAllocationChartProvider
)
from workers.etf_portfolio_evaluation import (
    format_change_direction,
    generate_etf_portfolio_appendix
)
from pathlib import Path
from tempfile import gettempdir


class PortfolioSummaryTests(unittest.TestCase):

    def test_portfolio_composition_splits_stock_etf_and_unresolved_weights(self):
        result = PortfolioEvaluationAgent._build_portfolio_overview([
            {
                "ticker": "NVDA",
                "weight": 50,
                "entity_type": "stock",
                "sector": "Technology"
            },
            {"ticker": "SOXX", "weight": 30, "entity_type": "etf"},
            {"ticker": "UNKN", "weight": 10, "entity_type": "unresolved"}
        ])

        self.assertIn("1 stock, 1 ETF, 1 unclassified", result)
        self.assertIn("stocks 50.00%, ETFs 30.00%", result)
        self.assertIn("total 90.00%", result)
        self.assertIn("do not total 100%", result)
        self.assertIn("excluded from stock/ETF comparisons", result)
        self.assertIn("Technology 50.00%", result)

    def test_etf_sector_exposure_is_reported_separately_from_stock_weight(self):
        result = PortfolioEvaluationAgent._build_portfolio_overview([
            {
                "ticker": "NVDA",
                "weight": 65,
                "entity_type": "stock",
                "sector": "Technology"
            },
            {
                "ticker": "SCHD",
                "weight": 35,
                "entity_type": "etf",
                "etf_context": {
                    "sector_weightings": {
                        "financialServices": 0.40,
                        "technology": 0.20
                    }
                }
            }
        ])

        self.assertIn("Technology 65.00%", result)
        self.assertIn("SCHD: financialServices 40.0%", result)
        self.assertIn("not added to portfolio stock-sector weights", result)

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
        provider.storage = SimpleNamespace(
            build_cache_key=lambda value: "test-portfolio-key",
            get_cached_data=lambda namespace, key: None,
            set_cached_data=lambda *args: None
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

    def test_etf_update_appendix_excludes_stocks_from_etf_averages(self):
        result = generate_etf_portfolio_appendix([
            {
                "ticker": "SOXX",
                "entity_type": "etf",
                "expense_ratio": 0.004,
                "dividend_yield": 0.01,
                "beta": 1.1
            },
            {
                "ticker": "NVDA",
                "entity_type": "stock",
                "expense_ratio": 0.8,
                "dividend_yield": 0.02,
                "beta": 2.0
            }
        ])

        self.assertIn("Unweighted average expense ratio: 0.40%", result)
        self.assertIn("Stock operating metrics are evaluated separately", result)
        self.assertNotIn("Unweighted average expense ratio: 40.20%", result)

    def test_allocation_chart_shows_each_holding_and_type_colors(self):
        result = PortfolioAllocationChartProvider().generate([
            {"ticker": "SCHD", "weight": 35, "entity_type": "etf"},
            {"ticker": "META", "weight": 30, "entity_type": "stock"},
            {"ticker": "GE", "weight": 25, "entity_type": "stock"},
            {"ticker": "QS", "weight": 10, "entity_type": "stock"}
        ])

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["total_weight"], 100)
        self.assertTrue(Path(result["path"]).is_file())
        self.assertTrue(
            Path(result["path"]).resolve().parent
            == Path(gettempdir()).resolve()
        )
        Path(result["path"]).unlink()

    def test_allocation_chart_marks_unbalanced_weights_as_not_normalized(self):
        result = PortfolioAllocationChartProvider().generate([
            {"ticker": "SCHD", "weight": 35, "entity_type": "etf"},
            {"ticker": "META", "weight": 30, "entity_type": "stock"}
        ])

        self.assertEqual(result["status"], "completed")
        self.assertIn("not normalized", result["caption"])
        Path(result["path"]).unlink()

    def test_etf_update_marks_eps_and_dividend_changes_by_direction(self):
        self.assertEqual(
            format_change_direction("EPS", "1.25", "1.50"),
            "🟢 increase"
        )
        self.assertEqual(
            format_change_direction("Dividend Yield", "3.5%", "3.0%"),
            "🔴 decrease"
        )
        self.assertEqual(
            format_change_direction("Dividend Yield", "0.035", "3.5%"),
            "⚪ unchanged"
        )
        self.assertEqual(
            format_change_direction("EPS", "1.25", "1.25"),
            "⚪ unchanged"
        )


if __name__ == "__main__":
    unittest.main()
