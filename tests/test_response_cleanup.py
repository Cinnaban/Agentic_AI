import unittest
from types import SimpleNamespace

from orchestrator.hermes import Hermes


class ResponseCleanupTests(unittest.TestCase):

    def hermes(self, heuristic):
        h = Hermes.__new__(Hermes)
        h.quality_manager = SimpleNamespace(
            _build_fallback_review=lambda ctx: {"confidence": heuristic}
        )
        return h

    def test_high_confidence_is_shown(self):
        self.assertEqual(self.hermes(95)._display_confidence(0, {}), "95 (Reviewer score: 0)")

    def test_low_confidence_reads_as_per_review(self):
        self.assertEqual(self.hermes(40)._display_confidence(30, {}), "As Per Review (Reviewer score: 30)")

    def test_llm_confidence_used_when_higher(self):
        self.assertEqual(self.hermes(40)._display_confidence(88, {}), "88 (Reviewer score: 88)")

    def test_sp500_evaluation(self):
        text = Hermes._evaluate_vs_sp500(
            "MU", {"asset_return_pct": 300.0, "benchmark_return_pct": 15.0,
                   "benchmark_label": "S&P 500 (SPY)"})
        self.assertIn("outperformed by 285.0 percentage points", text)
        under = Hermes._evaluate_vs_sp500(
            "UCTT", {"asset_return_pct": -20.0, "benchmark_return_pct": 15.0})
        self.assertIn("underperformed by 35.0", under)
        self.assertIn("lost value", under)


if __name__ == "__main__":
    unittest.main()
