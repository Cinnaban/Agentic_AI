import unittest

from agents.qwen_manager import QwenManager

GOOD = {"research": "Detailed research text.", "risk": {"risk_score": 40}, "quant_summary": {"AAPL": {}},
        "failed_agents": [], "social_available": True}


class QualityCapTests(unittest.TestCase):
    def test_complete_results_are_uncapped(self):
        cap, issues = QwenManager.completeness_cap(GOOD)
        self.assertEqual((cap, issues), (100, []))

    def test_empty_research_caps_confidence(self):
        bad = dict(GOOD, research="Research analysis unavailable: the research model returned no usable output (x).")
        cap, issues = QwenManager.completeness_cap(bad)
        self.assertLessEqual(cap, 65)
        self.assertTrue(any("Research" in i for i in issues))

    def test_failed_agents_and_missing_social_lower_cap(self):
        cap, _ = QwenManager.completeness_cap(dict(GOOD, failed_agents=["challenger"], social_available=False))
        self.assertLessEqual(cap, 75)

    def test_tolerant_json(self):
        self.assertEqual(QwenManager._parse_json('```json\n{"approved": true}\n```'), {"approved": True})
        self.assertIsNone(QwenManager._parse_json("no json here"))


if __name__ == "__main__":
    unittest.main()
