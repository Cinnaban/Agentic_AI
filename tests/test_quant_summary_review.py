import unittest

from orchestrator.financial_table_formatter import FinancialTableFormatter
from orchestrator.quant_summary_reviewer import QuantSummaryReviewer


def metric(label, value, type_="text", category="quantitative_models"):
    return {"label": label, "value": value, "type": type_, "source": "quant", "category": category}


PM_METRICS = {
    "prediction_pct": metric("Prediction", -1.01, "change_percent"),
    "confidence": metric("Model Confidence", 0.07, "percent"),
    "recommendation": metric("Model Recommendation", "Bearish"),
    "predictive_rating": metric("Predictive Rating", "Hold"),
    "stability_rating": metric("Stability Rating", "Good"),
    "forecast_rating": metric("Forecast Rating", "Bullish"),
    "forecast_consensus": metric("Forecast Consensus", "Mixed"),
    "forecast_5d": metric("5-Day Forecast", 0.34, "change_percent"),
    "forecast_90d": metric("90-Day Forecast", -5.76, "change_percent"),
    "momentum_rating": metric("Momentum Rating", "Excellent"),
    "financial_strength_rating": metric("Financial Strength", "Poor"),
    "stockholders_equity": metric("Stockholders' Equity", -8.58e9, "large_currency", "reported_financials"),
}


class QuantSummaryReviewTests(unittest.TestCase):

    def test_explains_each_metric(self):
        text = QuantSummaryReviewer().build(PM_METRICS)
        self.assertTrue(text.startswith("**Quant Summary Review**"))
        for needle in ("Model Recommendation: Bearish", "close to noise", "horizons disagree",
                       "Mixed because", "Hold means", "Momentum Excellent", "Stability Good",
                       "Financial Strength Poor", "Negative stockholders' equity", "Mixed signals"):
            self.assertIn(needle, text)

    def test_empty_without_quant_metrics(self):
        self.assertEqual(QuantSummaryReviewer().build({}), "")

    def test_review_sits_directly_below_quant_table(self):
        out = FinancialTableFormatter().build_sectioned_tables(PM_METRICS)
        quant = out.index("**Quantitative Models**")
        review = out.index("**Quant Summary Review**")
        self.assertGreater(review, quant)
        self.assertLess(out.index("| Financial Strength | Poor | Quant |"), review)
        self.assertNotIn("**Reported Financials**", out[quant:review])

    def test_aligned_bullish_has_no_conflict_line(self):
        metrics = {
            "recommendation": metric("Model Recommendation", "Bullish"),
            "momentum_rating": metric("Momentum Rating", "Good"),
            "forecast_30d": metric("30-Day Forecast", 2.0, "change_percent"),
            "forecast_5d": metric("5-Day Forecast", 1.0, "change_percent"),
        }
        text = QuantSummaryReviewer().build(metrics)
        self.assertIn("bullish drift", text)
        self.assertNotIn("Mixed signals", text)


if __name__ == "__main__":
    unittest.main()
