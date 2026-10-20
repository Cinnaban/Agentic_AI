import unittest
from unittest.mock import patch

from agents.consensus_agent import ConsensusAgent, prune, scrub
from orchestrator.financial_table_formatter import FinancialTableFormatter
from orchestrator.quant_comparison_reviewer import QuantComparisonReviewer


def metric(label, value, category, source="quant"):
    return {"label": label, "value": value, "category": category, "source": source}


class ConsensusTests(unittest.TestCase):

    def test_prune_drops_empty_values(self):
        data = {"a": None, "b": "N/A", "c": {"d": "", "e": 1}, "f": [None, "x"]}
        self.assertEqual(prune(data), {"c": {"e": 1}, "f": ["x"]})

    def test_scrub_removes_missing_data_and_process_talk(self):
        text = (
            "LRCX leads on momentum. Beta data is unavailable. "
            "Cross-referencing the sources confirms it.\n"
            "- Strong balance sheet\n- Revenue is N/A"
        )
        out = scrub(text)
        self.assertIn("LRCX leads on momentum.", out)
        self.assertIn("Strong balance sheet", out)
        for bad in ("unavailable", "Cross-referenc", "N/A"):
            self.assertNotIn(bad, out)

    def test_synthesize_returns_clean_summary(self):
        agent = ConsensusAgent()
        reply = {"response": "LRCX looks strongest. Data is missing for INTC. Its forecasts are positive across horizons."}
        with patch.object(agent.ollama, "generate", return_value=reply):
            out = agent.synthesize("Compare LRCX and INTC", {"x": {"y": 1}})
        self.assertIn("LRCX looks strongest.", out)
        self.assertNotIn("missing", out)

    def test_synthesize_empty_sources_skips_model(self):
        agent = ConsensusAgent()
        with patch.object(agent.ollama, "generate") as gen:
            self.assertEqual(agent.synthesize("q", {"a": None}), "")
            gen.assert_not_called()

    def test_comparison_uses_sectioned_fenced_tables(self):
        metrics = {
            "LRCX": {"price": metric("Price", 263.94, "market", "market"),
                     "rec": metric("Model Recommendation", "Bullish", "quantitative_models")},
            "INTC": {"price": metric("Price", 89.85, "market", "market"),
                     "rec": metric("Model Recommendation", "Hold", "quantitative_models")},
        }
        out = FinancialTableFormatter().build_comparison_table(metrics)
        self.assertIn("**Market & Valuation**", out)
        self.assertIn("**Quantitative Models**", out)
        self.assertEqual(out.count("```") % 2, 0)
        self.assertNotIn("|---", out)

    def test_quant_comparison_is_table(self):
        metrics = {
            "A": {"recommendation": metric("Rec", "Bullish", "quantitative_models"),
                  "forecast_30d": metric("30d", 1.0, "quantitative_models")},
            "B": {"recommendation": metric("Rec", "Bearish", "quantitative_models"),
                  "forecast_30d": metric("30d", -2.0, "quantitative_models")},
        }
        out = QuantComparisonReviewer().build(metrics, {})
        self.assertIn("Quant Comparison Summary", out)
        self.assertIn("Combined", out)
        self.assertIn("```", out)


if __name__ == "__main__":
    unittest.main()
