import unittest

from agents.generic_evidence_agent import GenericEvidenceAgent
from data.providers.generic_evidence_provider import GenericEvidenceProvider
from data.providers.live.firecrawl_backend import FirecrawlBackend


class SearchHardeningTests(unittest.TestCase):

    def test_anchor_gate_rejects_unrelated_pages(self):
        query = "List competitors to TSMC"
        good = {"title": "TSMC competitors", "summary": "Samsung, Intel", "url": ""}
        bad = {"title": "UK police report", "summary": "crime figures", "url": ""}
        self.assertTrue(GenericEvidenceProvider._passes_anchor_gate(good, query, ""))
        self.assertFalse(GenericEvidenceProvider._passes_anchor_gate(bad, query, ""))

    def test_focus_evidence_keeps_relevant_passages(self):
        filler = "Unrelated filler sentence about weather patterns. " * 80
        content = filler + "\nSamsung is the largest TSMC competitor with 11% share.\n" + filler
        evidence = {"results": [{"title": "t", "content": content}]}
        focused = GenericEvidenceAgent._focus_evidence(
            "List competitors to TSMC", evidence, {}
        )
        text = focused["results"][0]["content"]
        self.assertIn("Samsung", text)
        self.assertLessEqual(len(text), GenericEvidenceAgent.EXCERPT_BUDGET + 800)

    def test_direct_fetch_blocks_private_hosts(self):
        result = FirecrawlBackend().retrieve_direct("http://127.0.0.1:3002/")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
