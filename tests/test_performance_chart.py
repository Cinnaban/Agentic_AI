import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from data.providers.performance_chart_provider import (
    PerformanceChartProvider
)
from integrations.messaging.response_formatter import ResponseFormatter
from orchestrator.hermes import Hermes


class PerformanceChartTests(unittest.TestCase):

    def build_prices(self, tickers):
        dates = pd.date_range("2026-01-01", periods=6, freq="D")
        columns = pd.MultiIndex.from_product(
            [tickers, ["Close"]]
        )
        values = []
        for index in range(len(dates)):
            values.append([
                100 + index * (ticker_index + 1)
                for ticker_index, _ in enumerate(tickers)
            ])
        return pd.DataFrame(
            values,
            index=dates,
            columns=columns
        )

    def test_etf_chart_compares_only_with_sp500(self):
        provider = PerformanceChartProvider()
        tickers = ["SOXX", "SPY"]
        with patch(
            "data.providers.performance_chart_provider.yf.download",
            return_value=self.build_prices(tickers)
        ) as download:
            result = provider.generate({
                "ticker": "SOXX",
                "entity_type": "etf"
            })

        try:
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["industry_status"], "not_applicable")
            self.assertTrue(os.path.isfile(result["path"]))
            requested = download.call_args.kwargs["tickers"]
            self.assertEqual(requested, ["SOXX", "SPY"])
            with open(result["path"], "rb") as chart:
                self.assertTrue(chart.read(8).startswith(b"\x89PNG"))
        finally:
            if result.get("path") and os.path.exists(result["path"]):
                os.unlink(result["path"])

    def test_stock_chart_uses_verified_equal_weighted_industry_peers(self):
        provider = PerformanceChartProvider()
        peers = ["PEER1", "PEER2", "PEER3"]
        search = SimpleNamespace(
            quotes=[
                {
                    "symbol": ticker,
                    "quoteType": "EQUITY"
                }
                for ticker in peers
            ]
        )
        peer_tickers = [
            SimpleNamespace(
                info={
                    "quoteType": "EQUITY",
                    "industry": "Semiconductors"
                }
            )
            for _ in peers
        ]
        symbols = ["NVDA", "SPY"] + peers
        with patch(
            "data.providers.performance_chart_provider.yf.Search",
            return_value=search
        ), patch(
            "data.providers.performance_chart_provider.yf.Ticker",
            side_effect=peer_tickers
        ), patch(
            "data.providers.performance_chart_provider.yf.download",
            return_value=self.build_prices(symbols)
        ):
            result = provider.generate({
                "ticker": "NVDA",
                "entity_type": "stock",
                "industry": "Semiconductors"
            })

        try:
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["industry_status"], "available")
            self.assertEqual(result["industry_peer_count"], 3)
            self.assertIn("equal-weighted average of 3", result["caption"])
        finally:
            if result.get("path") and os.path.exists(result["path"]):
                os.unlink(result["path"])

    def test_stock_chart_reports_missing_verified_industry_average(self):
        provider = PerformanceChartProvider()
        with patch(
            "data.providers.performance_chart_provider.yf.Search",
            return_value=SimpleNamespace(quotes=[])
        ), patch(
            "data.providers.performance_chart_provider.yf.download",
            return_value=self.build_prices(["NVDA", "SPY"])
        ):
            result = provider.generate({
                "ticker": "NVDA",
                "entity_type": "stock",
                "industry": "Semiconductors"
            })

        try:
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["industry_status"], "unavailable")
            self.assertIn(
                "industry comparison unavailable",
                result["caption"]
            )
        finally:
            if result.get("path") and os.path.exists(result["path"]):
                os.unlink(result["path"])

    def test_formatter_cleans_only_generated_chart_files(self):
        provider = PerformanceChartProvider()
        ticker_symbols = ["SOXX", "SPY"]
        with patch(
            "data.providers.performance_chart_provider.yf.download",
            return_value=self.build_prices(ticker_symbols)
        ):
            chart = provider.generate({
                "ticker": "SOXX",
                "entity_type": "etf"
            })
        outsider = tempfile.NamedTemporaryFile(
            prefix="performance_",
            suffix=".txt",
            delete=False
        )
        outsider_path = outsider.name
        outsider.close()

        response = {
            "attachments": [
                {"path": chart["path"]},
                {"path": outsider_path}
            ]
        }
        ResponseFormatter.cleanup_attachments(response)
        self.assertFalse(os.path.exists(chart["path"]))
        self.assertTrue(os.path.exists(outsider_path))
        os.unlink(outsider_path)

    def test_hermes_attaches_chart_for_each_quantified_ticker(self):
        hermes = Hermes.__new__(Hermes)

        class ChartProvider:

            def generate(self, company):
                return {
                    "status": "completed",
                    "path": "/tmp/performance_NVDA.png",
                    "caption": "NVDA relative performance"
                }

        hermes.performance_chart_provider = ChartProvider()
        response = {"response": "Quant analysis complete."}
        execution_results = {
            "quant": {
                "results": [{
                    "company": {"ticker": "NVDA"}
                }]
            }
        }
        work_package = SimpleNamespace(
            companies=[{
                "ticker": "NVDA",
                "entity_type": "stock"
            }]
        )

        hermes._add_performance_charts(
            response,
            execution_results,
            work_package
        )

        self.assertEqual(
            response["attachments"][0]["filename"],
            "NVDA_performance_1y.png"
        )
        self.assertIn(
            "NVDA: chart attached.",
            response["response"]
        )


if __name__ == "__main__":
    unittest.main()
