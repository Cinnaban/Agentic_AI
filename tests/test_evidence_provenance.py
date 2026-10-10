import unittest

from orchestrator.evidence_provenance import EvidenceProvenance


class EvidenceProvenanceTests(unittest.TestCase):

    def test_formats_retrieval_time_and_publisher_dates(self):
        note = EvidenceProvenance.format_note({
            "retrieved_at": "2026-10-10T12:34:56-07:00",
            "results": [
                {
                    "source": "Example News",
                    "published_at": "2026-10-09T08:00:00Z"
                },
                {
                    "source": "Example News",
                    "published_at": "2026-10-10"
                }
            ]
        })

        self.assertIn("Retrieved: 2026-10-10 19:34 UTC", note)
        self.assertIn("Sources: Example News", note)
        self.assertIn("Example News (latest supplied publication: 2026-10-10)", note)

    def test_marks_unavailable_current_evidence(self):
        result = EvidenceProvenance.add_to_result(
            {"status": "completed", "response": "No current news found."},
            {
                "retrieved_at": "2026-10-10T12:00:00Z",
                "results": [],
                "sources": []
            },
            requires_current=True
        )

        self.assertIn(
            "Current information could not be verified",
            result["response"]
        )
        self.assertIn("Retrieved: 2026-10-10 12:00 UTC", result["response"])

    def test_reports_company_sources_and_unavailable_evidence(self):
        note = EvidenceProvenance.format_note({
            "retrieved_at": "2026-10-10T12:00:00Z",
            "requires_live_data": True,
            "live_market_context": {
                "available": False,
                "results": []
            },
            "source_status": {
                "financial_data": "available",
                "sec_facts": "available",
                "sec_filings": "available",
                "macro": "unavailable",
                "live_market_context": "unavailable",
                "news": "available",
                "social": "unavailable"
            }
        })

        self.assertIn("Gaming PC quantitative analysis", note)
        self.assertIn("SEC facts/filings", note)
        self.assertIn("FRED macroeconomic data", note)
        self.assertIn("Current information could not be verified", note)


if __name__ == "__main__":
    unittest.main()
