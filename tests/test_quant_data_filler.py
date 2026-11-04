import unittest

from orchestrator.financial_metric_builder import FinancialMetricBuilder
from orchestrator.quant_data_filler import QuantDataFiller


class FakeRobinhood:
    def __init__(self, closes, cap=45e9):
        self.closes, self.cap = closes, cap

    def bars(self, symbols, interval, days):
        return {s: [{"close": c} for c in self.closes] for s in symbols}

    def fundamentals(self, symbols):
        return {s: {"market_cap": str(self.cap)} for s in symbols}


class FakeAV:
    def __init__(self, profile):
        self.profile = profile

    def etf_profile(self, symbol):
        return self.profile


CALM = [100 * 1.0003 ** i for i in range(260)]
WILD = [100.0]
for i in range(1, 260):
    WILD.append(WILD[-1] * (0.9 if i % 3 == 0 else 1.04))


def analysis(**over):
    base = {"ticker": "ZZZ", "price": None, "market_cap": None, "stability_rating": "Missing Financial Data",
            "financial_strength_rating": "Poor", "financial_strength_score": 0}
    base.update(over)
    return base


class QuantDataFillerTests(unittest.TestCase):
    def filler(self, closes, cap=45e9, profile=None):
        return QuantDataFiller(FakeRobinhood(closes, cap), FakeAV(profile or {}))

    def test_stability_and_fund_strength_filled_from_supplied_data(self):
        out = self.filler(CALM, profile={"net_assets": "4e10", "net_expense_ratio": "0.0008", "leveraged": "NO"}).fill(analysis())
        self.assertEqual(out["stability_rating"][0], "Excellent")
        self.assertEqual(out["financial_strength_rating"][0], "Excellent")

    def test_volatile_small_expensive_fund_rates_poor(self):
        out = self.filler(WILD, cap=20e6, profile={"net_assets": "2e7", "net_expense_ratio": "0.0095", "leveraged": "YES"}).fill(analysis())
        self.assertEqual(out["stability_rating"][0], "Poor")
        self.assertEqual(out["financial_strength_rating"][0], "Poor")

    def test_quant_values_are_never_overridden(self):
        a = analysis(stability_rating="Good", price=50.0, financial_strength_rating="Average", financial_strength_score=40)
        self.assertEqual(self.filler(CALM).fill(a), {})

    def test_stock_keeps_poor_strength_but_stability_is_filled(self):
        out = self.filler(CALM).fill(analysis(price=12.0, market_cap=1e9))
        self.assertIn("stability_rating", out)
        self.assertNotIn("financial_strength_rating", out)

    def test_short_history_and_no_sources_leave_gaps(self):
        self.assertEqual(self.filler(CALM[:50]).fill(analysis()).get("stability_rating"), None)
        self.assertEqual(QuantDataFiller(FakeRobinhood([], cap=None), FakeAV(None)).fill(analysis(financial_strength_rating="Poor")).get("financial_strength_rating"), None)

    def test_builder_replaces_missing_ratings_in_quant_table(self):
        builder = FinancialMetricBuilder(gap_filler=self.filler(CALM, profile={"net_assets": "4e10", "net_expense_ratio": "0.0008"}))
        metrics = builder.build({"quant": {"analysis": analysis()}})
        self.assertEqual(metrics["stability_rating"]["value"], "Excellent")
        self.assertEqual(metrics["financial_strength_rating"]["value"], "Excellent")
        self.assertEqual(metrics["stability_rating"]["category"], "quantitative_models")


if __name__ == "__main__":
    unittest.main()
