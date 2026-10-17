import unittest

from agents.company_detection_agent import CompanyDetectionAgent
from orchestrator.comparison_intent import ComparisonIntent


COMPANIES = [
    {"name": "INTC", "ticker": "INTC"},
    {"name": "AMD", "ticker": "AMD"},
]


class ComparisonDetectionTests(unittest.TestCase):

    def test_comparison_phrasings(self):
        intent = ComparisonIntent()
        for text in (
            "Compare INTC and AMD",
            "INTC vs AMD",
            "INTC vs. AMD",
            "INTC versus AMD",
            "Should I buy INTC or AMD",
        ):
            self.assertTrue(intent.is_comparison(text, COMPANIES), text)

    def test_single_company_is_not_comparison(self):
        self.assertFalse(
            ComparisonIntent().is_comparison("Compare INTC", COMPANIES[:1])
        )

    def test_lookup_adds_named_company_next_to_ticker(self):
        candidates = [{
            "symbol": "INTC",
            "name": "Intel Corporation",
            "quote_type": "EQUITY",
            "searched_name": "Intel",
        }]
        result = CompanyDetectionAgent._add_lookup_companies(
            "Compare Intel and AMD",
            ["Intel", "AMD"],
            candidates,
            ["AMD"],
            [{"name": "AMD", "ticker": "AMD", "entity_type": "security"}],
        )
        self.assertEqual([c["ticker"] for c in result], ["AMD", "INTC"])

    def test_no_additions_without_comparison_wording(self):
        result = CompanyDetectionAgent._add_lookup_companies(
            "Tell me about Intel and AMD",
            ["Intel", "AMD"],
            [],
            ["AMD"],
            [{"name": "AMD", "ticker": "AMD"}],
        )
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
