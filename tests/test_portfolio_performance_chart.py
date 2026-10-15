import os
import unittest
from unittest.mock import patch

import pandas as pd

from data.providers.portfolio_performance_chart_provider import (
    PortfolioPerformanceChartProvider
)
from integrations.messaging.response_formatter import ResponseFormatter
from orchestrator.hermes import Hermes


class PortfolioPerformanceChartTests(unittest.TestCase):

    TICKERS = ["AAA", "BBB", "SPY", "DIA"]

    @classmethod
    def setUpClass(cls):
        cls.dates = pd.date_range(
            "2024-12-30",
            "2026-10-14",
            freq="B"
        )
        columns = pd.MultiIndex.from_product(
            [cls.TICKERS, ["Close"]]
        )
        cls.prices = pd.DataFrame(
            {
                ("AAA", "Close"): [
                    100 + index * 0.1
                    for index in range(len(cls.dates))
                ],
                ("BBB", "Close"): [
                    50 + index * 0.08
                    for index in range(len(cls.dates))
                ],
                ("SPY", "Close"): [
                    5000 + index * 2
                    for index in range(len(cls.dates))
                ],
                ("DIA", "Close"): [
                    40000 + index * 10
                    for index in range(len(cls.dates))
                ]
            },
            index=cls.dates,
            columns=columns
        )

    def test_generates_two_weighted_return_charts_against_both_indexes(self):
        provider = PortfolioPerformanceChartProvider()
        holdings = [
            {"ticker": "AAA", "weight": 60},
            {"ticker": "BBB", "weight": 40}
        ]

        with patch(
            "data.providers.portfolio_performance_chart_provider.yf.download",
            return_value=self.prices
        ) as download:
            result = provider.generate(holdings)

        try:
            self.assertEqual(result["status"], "completed")
            self.assertEqual(
                [chart["title"] for chart in result["charts"]],
                [
                    "Average Year-to-Date Return",
                    "Rolling 12-Month Return"
                ]
            )
            self.assertEqual(result["weight_total"], 100)
            self.assertEqual(result["holdings"], ["AAA", "BBB"])
            self.assertTrue(all(
                os.path.isfile(chart["path"])
                for chart in result["charts"]
            ))
            requested = download.call_args.kwargs
            self.assertEqual(
                requested["tickers"],
                ["AAA", "BBB", "SPY", "DIA"]
            )
            self.assertEqual(requested["period"], "2y")
            self.assertTrue(requested["auto_adjust"])
            self.assertIn("Dow Jones Industrial Average", result["charts"][0]["caption"])
            ResponseFormatter.cleanup_attachments({
                "attachments": [
                    {"path": chart["path"]}
                    for chart in result["charts"]
                ]
            })
            self.assertTrue(all(
                not os.path.exists(chart["path"])
                for chart in result["charts"]
            ))
        finally:
            for chart in result.get("charts", []):
                if os.path.exists(chart["path"]):
                    os.unlink(chart["path"])

    def test_weight_normalization_handles_rounded_total(self):
        weights, total, error = (
            PortfolioPerformanceChartProvider._holding_weights([
                {"ticker": "AAA", "weight": 60},
                {"ticker": "BBB", "weight": 40.1}
            ])
        )

        self.assertIsNone(error)
        self.assertAlmostEqual(total, 100.1)
        self.assertAlmostEqual(weights["AAA"] + weights["BBB"], 1)
        self.assertAlmostEqual(weights["AAA"], 60 / 100.1)

    def test_return_series_use_weighted_holdings_and_both_benchmark_indexes(self):
        provider = PortfolioPerformanceChartProvider()
        weights, _, error = provider._holding_weights([
            {"ticker": "AAA", "weight": 60},
            {"ticker": "BBB", "weight": 40}
        ])
        self.assertIsNone(error)

        prices_by_ticker = provider._close_prices(
            self.prices,
            self.TICKERS
        )
        prices = pd.concat(
            [prices_by_ticker[ticker].rename(ticker) for ticker in self.TICKERS],
            axis=1,
            join="inner"
        ).dropna()
        ytd = provider._year_to_date_returns(prices, weights)
        rolling = provider._rolling_12_month_returns(prices, weights)

        ytd_baseline = prices.iloc[
            prices.index.searchsorted(
                pd.Timestamp(year=2026, month=1, day=1),
                side="left"
            ) - 1
        ]
        expected_ytd = sum(
            (prices[ticker].iloc[-1] / ytd_baseline[ticker] - 1) * weight
            for ticker, weight in weights.items()
        ) * 100
        self.assertAlmostEqual(
            ytd["Portfolio (weighted)"].iloc[-1],
            expected_ytd
        )
        self.assertEqual(
            list(ytd.columns),
            [
                "Portfolio (weighted)",
                "S&P 500 (SPY)",
                "Dow Jones Industrial Average (DIA)"
            ]
        )

        final_date = prices.index[-1]
        anchor_position = prices.index.get_indexer(
            [final_date - pd.DateOffset(years=1)],
            method="pad"
        )[0]
        anchor = prices.iloc[anchor_position]
        expected_rolling = sum(
            (prices[ticker].iloc[-1] / anchor[ticker] - 1) * weight
            for ticker, weight in weights.items()
        ) * 100
        self.assertAlmostEqual(
            rolling["Portfolio (weighted)"].iloc[-1],
            expected_rolling
        )

    def test_unavailable_holding_prices_fail_instead_of_charting_partial_portfolio(self):
        provider = PortfolioPerformanceChartProvider()
        incomplete = self.prices.drop(
            columns=[("BBB", "Close")]
        )
        with patch(
            "data.providers.portfolio_performance_chart_provider.yf.download",
            return_value=incomplete
        ):
            result = provider.generate([
                {"ticker": "AAA", "weight": 60},
                {"ticker": "BBB", "weight": 40}
            ])

        self.assertEqual(result["status"], "failed")
        self.assertIn("BBB", result["error"])

    def test_hermes_appends_both_charts_after_the_allocation_chart(self):
        hermes = Hermes.__new__(Hermes)

        class ChartProvider:

            def generate(self, holdings):
                return {
                    "status": "completed",
                    "charts": [
                        {
                            "path": "/tmp/ytd.png",
                            "caption": "YTD comparison"
                        },
                        {
                            "path": "/tmp/rolling.png",
                            "caption": "Rolling comparison"
                        }
                    ]
                }

        hermes.portfolio_performance_chart_provider = ChartProvider()
        response = {
            "response": "Portfolio summary.",
            "attachments": [{
                "path": "/tmp/allocation.png",
                "filename": "portfolio_allocation.png"
            }]
        }

        hermes._add_portfolio_performance_charts(
            response,
            [{"ticker": "AAA", "weight": 100}]
        )

        self.assertEqual(
            [item["filename"] for item in response["attachments"]],
            [
                "portfolio_allocation.png",
                "portfolio_ytd_return.png",
                "portfolio_rolling_12_month_return.png"
            ]
        )
        self.assertIn("year-to-date and rolling 12-month", response["response"])


if __name__ == "__main__":
    unittest.main()
