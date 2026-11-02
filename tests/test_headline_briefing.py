import unittest

from agents.generic_evidence_agent import GenericEvidenceAgent
from orchestrator.direct_answer import DirectAnswerAgent

BODY = "Intel confirmed the chip will ship as a professional card with a lot of memory this year. " * 3


def item(sid, title, date=None, read=True, url=None):
    return {"source_id": sid, "title": title, "published_at": date, "url": url or f"https://x.com/{sid}",
            "evidence_level": "retrieved_webpage" if read else "search_snippet", "content": BODY, "summary": BODY}


class HeadlineBriefingTests(unittest.TestCase):
    def test_what_happened_queries_use_briefing_without_dates(self):
        results = [item("S1", "A"), item("S2", "B", "2026-01-21"), item("S3", "C", url="https://youtube.com/w")]
        items = GenericEvidenceAgent._dated_items("What happened to the Intel B770 graphics card?", results)
        self.assertEqual([i["source_id"] for i in items], ["S2", "S1"])

    def test_plain_factual_questions_are_not_briefings(self):
        results = [item("S1", "A"), item("S2", "B")]
        self.assertEqual(GenericEvidenceAgent._dated_items("Explain FPS and RTS gaming", results), [])

    def test_prose_drops_menus_and_links(self):
        text = "[Home](https://a.b)\n* [Claude](https://c.d)\n![x](y.png)\n" + BODY
        cleaned = GenericEvidenceAgent._prose(text)
        self.assertNotIn("http", cleaned)
        self.assertIn("professional card", cleaned)

    def test_prompt_forbids_verdict_language(self):
        prompt = GenericEvidenceAgent._build_news_prompt("q", [item("S1", "A"), item("S2", "B")])
        self.assertIn("Never use the words verdict", prompt)
        self.assertIn("ARTICLE TEXT", prompt)

    def test_briefings_skip_direct_answer_wrapper(self):
        briefing = "Summary:\nx\n\nAnswer:\n" + "y " * 300 + "\n\nAssessment:\nz\n\nSources:\n- [S1]"
        self.assertFalse(DirectAnswerAgent.applies("What happened to X?", briefing))
        self.assertTrue(DirectAnswerAgent.applies("Is AAPL a buy?", "AAPL table " * 100))


if __name__ == "__main__":
    unittest.main()
