import os
import unittest
from unittest import mock

from orchestrator import chart_engine as ce


class FakeLookup:
    def search(self, name):
        table = {"Amazon": [{"symbol": "AMZN", "name": "Amazon.com, Inc.", "quote_type": "EQUITY"}],
                 "Apple": [{"symbol": "AAPL", "name": "Apple Inc.", "quote_type": "EQUITY"}]}
        return table.get(name, [])


class ChartParsingTests(unittest.TestCase):

    def test_intent_variants(self):
        for text in ("Chart AMZN EBITDA", "plot nvda revenue", "Visualize Apple profit",
                     "update the charts to add PE", "graph CPI"):
            self.assertTrue(ce.is_chart_request(text), text)
        self.assertFalse(ce.is_chart_request("Explain mutual funds vs ETFs"))

    def test_ratio_is_not_a_ticker(self):
        spec = ce.build_spec("Chart AMZN EBITDA vs P/E ratio 2021-2025", lookup=FakeLookup())
        self.assertEqual(spec["tickers"], ["AMZN"])
        self.assertEqual(spec["metrics"], ["ebitda", "pe"])
        self.assertEqual((spec["start"], spec["end"]), (2021, 2025))

    def test_company_name_and_multiple_tickers(self):
        spec = ce.build_spec("Visualize Amazon net profit and P/E", lookup=FakeLookup())
        self.assertEqual(spec["tickers"], ["AMZN"])
        self.assertEqual(spec["metrics"], ["net_income", "pe"])
        spec = ce.build_spec("Plot NVDA and AMD revenue since 2020", lookup=FakeLookup())
        self.assertEqual(spec["tickers"], ["NVDA", "AMD"])
        self.assertEqual(spec["start"], 2020)

    def test_follow_up_merges_and_replaces(self):
        prev = {"tickers": ["AMZN"], "metrics": ["ebitda"], "start": 2021, "end": 2025}
        spec = ce.build_spec("update the charts to have PE ratio be a second y axis as a line",
                             previous=prev, lookup=FakeLookup())
        self.assertEqual(spec["tickers"], ["AMZN"])
        self.assertEqual(spec["metrics"], ["ebitda", "pe"])
        self.assertEqual((spec["start"], spec["end"]), (2021, 2025))
        spec = ce.build_spec("chart only revenue instead", previous=prev, lookup=FakeLookup())
        self.assertEqual(spec["metrics"], ["revenue"])

    def test_economic_and_prices(self):
        self.assertEqual(ce.build_spec("Graph CPI since 2019")["economic"], ["CPI"])
        spec = ce.build_spec("Compare AAPL and MSFT price last 2 years", lookup=FakeLookup())
        self.assertEqual(spec["metrics"], ["price"])
        self.assertEqual(spec["end"] - spec["start"], 1)


class ChartRenderTests(unittest.TestCase):

    def test_dual_axis_render_and_pe(self):
        annual = {2022: {"ebitda": 4e10, "eps": -0.27}, 2023: {"ebitda": 9e10, "eps": 2.9},
                  2024: {"ebitda": 1.2e11, "eps": 5.0}}
        prices = {2022: 84.0, 2023: 151.0, 2024: 220.0}
        spec = {"tickers": ["AMZN"], "metrics": ["ebitda", "pe"], "economic": [], "start": 2022, "end": 2024}
        with mock.patch.object(ce, "fetch_annual", return_value=(annual, {}, ["Yahoo Finance"])), \
                mock.patch.object(ce, "year_end_prices", return_value=prices):
            values, _, _ = ce.compute_fundamentals("AMZN", spec)
            self.assertNotIn(2022, values["pe"])
            self.assertAlmostEqual(values["pe"][2023], 151.0 / 2.9)
            result = ce.ChartEngine(lookup=FakeLookup())._fundamentals(spec)
        path = result["attachments"][0]["path"]
        try:
            self.assertTrue(os.path.basename(path).startswith("performance_"))
            self.assertGreater(os.path.getsize(path), 5000)
            self.assertIn("no data for 2022", result["response"])
        finally:
            os.remove(path)

    def test_non_chart_message_returns_none(self):
        self.assertIsNone(ce.ChartEngine().handle("Explain how physics works"))


if __name__ == "__main__":
    unittest.main()


class OverviewTests(unittest.TestCase):

    def test_overview_falls_back_to_net_profit(self):
        annual = {2024: {"net_income": 5e10, "eps": 5.0}, 2025: {"net_income": 5.5e10, "eps": 5.5}}
        quarterly = {f"2025-{month:02d}-30": {"net_income": 1e10, "eps": 1.0, "pe": 25.0}
                     for month in (3, 6, 9, 12)}
        with mock.patch.object(ce, "fetch_annual", return_value=(annual, {}, ["Yahoo Finance"])), \
                mock.patch.object(ce, "year_end_prices", return_value={2024: 200.0, 2025: 250.0}):
            with mock.patch.object(ce, "compute_quarterly_fundamentals",
                                   return_value=(quarterly, ["Yahoo Finance"])):
                result = ce.ChartEngine().overview("JPM")
        try:
            self.assertEqual(result["metric"], "Net Profit")
            self.assertTrue(os.path.exists(result["path"]))
            self.assertTrue(os.path.exists(result["quarterly_path"]))
            self.assertIn("last 4 years", result["caption"])
            self.assertEqual(len(result["quarterly_periods"]), 4)
        finally:
            os.remove(result["path"])
            os.remove(result["quarterly_path"])

    def test_quarterly_chart_limits_to_last_eight_periods(self):
        data = {
            f"{year}-{month:02d}-28": {"ebitda": float(year * month), "pe": 20.0 + month}
            for year, month in [(2024, 3), (2024, 6), (2024, 9), (2024, 12),
                                (2025, 3), (2025, 6), (2025, 9), (2025, 12),
                                (2026, 3), (2026, 6)]
        }
        path = ce.render_quarterly_fundamentals("AMZN", data, ["Yahoo Finance"])
        try:
            self.assertTrue(os.path.exists(path))
            self.assertGreater(os.path.getsize(path), 5000)
        finally:
            os.remove(path)
