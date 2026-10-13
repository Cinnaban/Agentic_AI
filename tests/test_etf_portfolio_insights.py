import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd

from workers.etf_portfolio_insights import (
    collect_holding_insights,
    filter_recent_news,
    format_holding_insights,
    retrieve_holding_insights
)


class ETFPortfolioInsightsTests(unittest.TestCase):

    def test_stock_insights_include_quarterly_and_fundamental_metrics(self):
        newest = datetime(2026, 9, 30)
        previous = datetime(2026, 6, 30)
        income = pd.DataFrame(
            {
                newest: [1200, 180, 1.2],
                previous: [1000, 140, 0.9]
            },
            index=["Total Revenue", "Net Income", "Diluted EPS"]
        )
        cash_flow = pd.DataFrame(
            {newest: [240, 160]},
            index=["Operating Cash Flow", "Free Cash Flow"]
        )
        balance = pd.DataFrame(
            {newest: [900, 450]},
            index=["Current Assets", "Current Liabilities"]
        )

        record = collect_holding_insights(
            ticker="NVDA",
            entity_type="stock",
            info={
                "shortName": "NVIDIA",
                "sector": "Technology",
                "industry": "Semiconductors",
                "marketCap": 3_000_000_000_000,
                "trailingEps": 4.5,
                "ebitda": 80_000_000_000,
                "currentRatio": 2.1,
                "operatingCashflow": 90_000_000_000,
                "freeCashflow": 75_000_000_000,
                "revenueGrowth": 0.2
            },
            income_statement=income,
            cash_flow_statement=cash_flow,
            balance_sheet=balance
        )

        self.assertEqual(record["entity_type"], "stock")
        self.assertEqual(record["sector"], "Technology")
        self.assertEqual(record["metrics"]["market_cap"], 3_000_000_000_000)
        self.assertEqual(record["quarterly"]["revenue"]["latest"], 1200)
        self.assertAlmostEqual(
            record["quarterly"]["revenue"]["quarter_over_quarter_change_pct"],
            20
        )
        self.assertEqual(record["quarterly"]["current_ratio"]["latest"], 2)

    def test_etf_metrics_are_fund_level_and_company_ratios_not_applicable(self):
        record = collect_holding_insights(
            ticker="SOXX",
            entity_type="etf",
            info={
                "shortName": "iShares Semiconductor ETF",
                "totalAssets": 15_000_000_000,
                "annualReportExpenseRatio": 0.0035,
                "yield": 0.01,
                "beta": 1.2
            },
            fund_context={
                "sector_weightings": {"technology": 0.9},
                "top_holdings": [{"symbol": "NVDA"}]
            }
        )

        self.assertEqual(record["entity_type"], "etf")
        self.assertEqual(record["metrics"]["total_assets"], 15_000_000_000)
        self.assertEqual(record["fund_profile"]["top_holdings"][0]["symbol"], "NVDA")
        self.assertIn("EBITDA", record["not_applicable"])
        self.assertIn("current ratio", record["not_applicable"])

    def test_recent_news_excludes_old_future_undated_and_duplicate_articles(self):
        now = datetime(2026, 10, 12, 23, 0, tzinfo=timezone.utc)
        recent = (now - timedelta(hours=10)).isoformat()
        items = [
            {
                "title": "New earnings update",
                "published_at": recent,
                "url": "https://news.test/recent"
            },
            {
                "title": "Duplicate",
                "published_at": recent,
                "url": "https://news.test/recent"
            },
            {
                "title": "Old item",
                "published_at": (now - timedelta(hours=60)).isoformat(),
                "url": "https://news.test/old"
            },
            {
                "title": "Future item",
                "published_at": (now + timedelta(hours=1)).isoformat(),
                "url": "https://news.test/future"
            },
            {
                "title": "Undated item",
                "published_at": "yesterday",
                "url": "https://news.test/unknown"
            }
        ]

        news = filter_recent_news(items, now=now)

        self.assertEqual(len(news), 1)
        self.assertEqual(news[0]["title"], "New earnings update")

    def test_mixed_report_formats_classification_and_metric_coverage(self):
        now = datetime(2026, 10, 12, 23, 0, tzinfo=timezone.utc)
        output = format_holding_insights(
            [
                {
                    "ticker": "NVDA",
                    "entity_type": "stock",
                    "name": "NVIDIA",
                    "sector": "Technology",
                    "industry": "Semiconductors",
                    "metrics": {
                        "market_cap": 3_000_000_000_000,
                        "eps": 4.5,
                        "operating_margin": 0.5
                    },
                    "quarterly": {
                        "revenue": {
                            "latest": 100,
                            "period_ended": "2026-09-30"
                        }
                    }
                },
                {
                    "ticker": "SOXX",
                    "entity_type": "etf",
                    "name": "Semiconductor ETF",
                    "metrics": {
                        "total_assets": 10_000_000_000,
                        "expense_ratio": 0.0035
                    },
                    "quarterly": {
                        "note": "ETF operating-company ratios not applicable."
                    },
                    "fund_profile": {
                        "sector_weightings": {"technology": 0.9},
                        "top_holdings": [{"symbol": "NVDA"}]
                    }
                }
            ],
            {},
            now=now
        )

        self.assertIn("NVDA — STOCK", output)
        self.assertIn("SOXX — ETF", output)
        self.assertIn("Market capitalization: $3,000,000,000,000.", output)
        self.assertIn("Operating margin: 50.00%.", output)
        self.assertIn("Expense ratio: 0.35%.", output)
        self.assertIn("ETF operating-company ratios not applicable.", output)
        self.assertIn("No timestamp-verified relevant headlines retrieved.", output)

    def test_stock_peer_context_is_limited_to_same_industry_portfolio_holdings(self):
        output = format_holding_insights(
            [
                {
                    "ticker": "NVDA",
                    "entity_type": "stock",
                    "industry": "Semiconductors",
                    "metrics": {"revenue_growth": 0.2}
                },
                {
                    "ticker": "AMD",
                    "entity_type": "stock",
                    "industry": "Semiconductors",
                    "metrics": {"revenue_growth": 0.1}
                },
                {
                    "ticker": "MSFT",
                    "entity_type": "stock",
                    "industry": "Software",
                    "metrics": {"revenue_growth": 0.15}
                }
            ],
            {}
        )

        self.assertIn(
            "partial cohort, not an industry-wide benchmark",
            output
        )
        self.assertIn("- AMD: revenue growth: 10.00%", output)
        self.assertNotIn("- MSFT: revenue growth", output)

    def test_retrieval_reads_stock_quarterlies_but_skips_them_for_etfs(self):
        stock = SimpleNamespace(
            quarterly_income_stmt="income",
            quarterly_cashflow="cashflow",
            quarterly_balance_sheet="balance",
            history=Mock(return_value=None)
        )
        record = retrieve_holding_insights(
            stock,
            "NVDA",
            "stock",
            {},
        )

        self.assertEqual(record["entity_type"], "stock")
        stock.history.assert_called_once()

        fund = SimpleNamespace(history=Mock(return_value=None))
        fund_record = retrieve_holding_insights(
            fund,
            "SOXX",
            "etf",
            {},
            fund_context={}
        )
        self.assertEqual(fund_record["entity_type"], "etf")
        fund.history.assert_called_once()


if __name__ == "__main__":
    unittest.main()
