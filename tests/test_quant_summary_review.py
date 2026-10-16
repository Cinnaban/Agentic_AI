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
                       "Financial Strength Poor", "negative stockholders' equity", "Mixed signals"):
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



from orchestrator.quant_evidence_builder import QuantEvidenceBuilder, headline_tone  # noqa: E402

VZ = {
    "prediction_pct": metric("Prediction", 2.87, "change_percent"),
    "confidence": metric("Model Confidence", 0.09, "percent"),
    "recommendation": metric("Model Recommendation", "Strong Bullish"),
    "predictive_rating": metric("Predictive Rating", "Buy"),
    "stability_rating": metric("Stability Rating", "Good"),
    "forecast_rating": metric("Forecast Rating", "Strong Bullish"),
    "momentum_rating": metric("Momentum Rating", "Average"),
    "financial_strength_rating": metric("Financial Strength", "Weak"),
    "forecast_30d": metric("30-Day Forecast", 5.9, "change_percent"),
    "revenue": metric("Revenue", 34.25e9, "large_currency", "reported_financials"),
    "net_income": metric("Net Income", 3.83e9, "large_currency", "reported_financials"),
    "assets": metric("Total Assets", 410.19e9, "large_currency", "reported_financials"),
    "liabilities": metric("Total Liabilities", 330e9, "large_currency", "reported_financials"),
}

EVIDENCE = {
    "symbol": "VZ", "price": 44.79, "change_pct": 0.012,
    "analysts": {"buy": 12, "hold": 14, "sell": 2, "n": 28},
    "target_upside": 0.12, "next_earnings": "2026-10-21",
    "live_quant": {"signal_score": 0.4, "rsi14": 72, "vwap_dev_pct": 0.004, "realized_vol_ann": 0.18,
                   "beta_vs_spy": 0.25, "ic": 0.01, "hit_rate": 0.50},
    "web": [
        {"title": "Verizon raises outlook after strong subscriber growth", "source": "Reuters",
         "text": "Verizon raises outlook after strong subscriber growth", "via": "Firecrawl"},
        {"title": "Verizon faces lawsuit over fees", "source": "AP", "text": "lawsuit fees", "via": None},
    ],
}


class QuantCrossReferenceTests(unittest.TestCase):

    def test_evidence_reinforces_each_key_point(self):
        text = QuantSummaryReviewer().build(VZ, EVIDENCE)
        for needle in ("Robinhood analysts are 43% Buy", "mean analyst price target is +12.0%",
                       "live intraday signal is +0.40", "little predictive edge", "scraped with Firecrawl",
                       "live RSI is 72", "beta versus SPY is 0.25", "SEC liabilities are 80% of assets",
                       "net margin is 11%", "next earnings report on 2026-10-21", "Cross-reference verdict",
                       "Mixed signals"):
            self.assertIn(needle, text)

    def test_verdict_counts_agreement_and_conflict(self):
        text = QuantSummaryReviewer().build(VZ, EVIDENCE)
        verdict = [line for line in text.splitlines() if "Cross-reference verdict" in line][0]
        self.assertIn("3 agree (analyst ratings, live signal, price target)", verdict)
        self.assertIn("1 neutral (headline tone)", verdict)

    def test_without_evidence_has_no_cross_check(self):
        text = QuantSummaryReviewer().build(VZ, {})
        self.assertNotIn("Robinhood", text)
        self.assertNotIn("Cross-reference verdict", text)

    def test_builder_collects_robinhood_and_firecrawl(self):
        results = {"market_context": {
            "company": {"ticker": "VZ"},
            "live_market_context": {"results": [
                {"title": "VZ page", "source": "Site", "summary": "strong growth", "content": "record growth",
                 "content_retrieved_by": "Firecrawl"},
                {"title": "VZ quote", "authoritative": True, "source": "Robinhood"}]},
            "news": [{"title": "Verizon downgrade", "source": "Feed"}]}}
        snap = {"quote": {"price": 44.0, "change_pct": 0.01},
                "ratings": {"num_buy_ratings": 5, "num_hold_ratings": 1, "num_sell_ratings": 0},
                "upside_to_target": 0.1, "next_earnings": "2026-10-21"}
        builder = QuantEvidenceBuilder(snapshot_fn=lambda s: snap,
                                       live_quant_fn=lambda s: {"signal_score": 0.2, "scorecard": {"ic": 0.1}})
        ev = builder.build(results)
        self.assertEqual(ev["analysts"]["n"], 6)
        self.assertEqual(ev["live_quant"]["ic"], 0.1)
        self.assertEqual([w["via"] for w in ev["web"]], ["Firecrawl", None])

    def test_builder_survives_source_failures(self):
        def boom(_):
            raise RuntimeError("down")
        ev = QuantEvidenceBuilder(snapshot_fn=boom, live_quant_fn=boom).build(
            {"market_context": {"company": {"ticker": "VZ"}}})
        self.assertEqual(ev, {})

    def test_headline_tone(self):
        self.assertEqual(headline_tone("analyst upgrade after record growth"), 1)
        self.assertEqual(headline_tone("lawsuit and layoffs"), -1)
        self.assertEqual(headline_tone("company opens office"), 0)


if __name__ == "__main__":
    unittest.main()
