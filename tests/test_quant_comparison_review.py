import unittest

from orchestrator.quant_comparison_reviewer import QuantComparisonReviewer


def metrics(rec, pred, f30, f90, mom, strength, stab, beta):
    def m(v):
        return {"value": v}
    return {
        "recommendation": m(rec), "prediction_pct": m(pred),
        "forecast_30d": m(f30), "forecast_90d": m(f90),
        "momentum_rating": m(mom), "financial_strength_rating": m(strength),
        "stability_rating": m(stab), "beta": m(beta),
    }


METRICS = {
    "MU": metrics("Bullish", 0.5, 14.8, 132.8, "Good", "Excellent", "Good", 2.2),
    "WDC": metrics("Bearish", -0.7, 44.9, 163.6, "Average", "Good", "Poor", 2.1),
    "P": metrics("Bearish", -0.25, -3.6, 7.0, "Good", "Excellent", "Weak", 1.4),
}
EVIDENCE = {
    "MU": {"analysts": {"buy": 20, "hold": 2, "sell": 0, "n": 22}, "target_upside": 12.0,
           "live_quant": {"signal_score": 0.4, "ic": 0.01, "hit_rate": 0.5}},
    "WDC": {"analysts": {"buy": 3, "hold": 5, "sell": 4, "n": 12}, "target_upside": -8.0},
    "P": {"target_upside": 2.0},
}


class QuantComparisonTests(unittest.TestCase):

    def test_compares_every_ticker(self):
        text = QuantComparisonReviewer().build(METRICS, EVIDENCE)
        for ticker in METRICS:
            self.assertIn(f"**{ticker}**", text)
        self.assertIn("Quant Comparison Summary", text)
        self.assertIn("30-day forecast:** WDC", text)
        self.assertIn("MU has the strongest combined signal", text)
        self.assertIn("little predictive edge", text)

    def test_works_without_cross_reference(self):
        text = QuantComparisonReviewer().build(METRICS, {})
        self.assertIn("Cross-ticker verdict", text)

    def test_needs_two_tickers(self):
        self.assertEqual(QuantComparisonReviewer().build({"MU": METRICS["MU"]}, {}), "")


if __name__ == "__main__":
    unittest.main()
