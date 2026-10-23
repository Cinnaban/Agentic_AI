import unittest

from orchestrator.freshness_detector import FreshnessDetector


class FinancialQueryTests(unittest.TestCase):
    def test_non_financial_latest_queries(self):
        detector = FreshnessDetector()
        for query in (
            "What is the latest on Magic The Gathering?",
            "Latest news on the Jaguars",
            "What's new in FPS gaming today?",
        ):
            self.assertTrue(detector.requires_live_data(query))
            self.assertFalse(detector.is_financial_query(query), query)

    def test_financial_latest_queries(self):
        detector = FreshnessDetector()
        for query in (
            "What is the S&P 500 doing today?",
            "Latest on bitcoin price",
            "Current interest rates",
        ):
            self.assertTrue(detector.is_financial_query(query), query)


if __name__ == "__main__":
    unittest.main()
