import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from agents.generic_evidence_agent import GenericEvidenceAgent
from data.providers.generic_evidence_provider import (
    GenericEvidenceProvider
)


class Response:

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class GenericFactualSourceTests(unittest.TestCase):

    def test_wikipedia_lookup_selects_matching_article_and_extract(self):
        responses = [
            Response({
                "query": {
                    "search": [
                        {"title": "Piranha"},
                        {"title": "Piranha Games"}
                    ]
                }
            }),
            Response({
                "query": {
                    "pages": {
                        "123": {
                            "title": "Piranha Games",
                            "fullurl": (
                                "https://en.wikipedia.org/wiki/"
                                "Piranha_Games"
                            ),
                            "extract": "Piranha Games is a video game developer."
                        }
                    }
                }
            })
        ]
        with patch(
            "data.providers.generic_evidence_provider.requests.get",
            side_effect=responses
        ):
            result, status = (
                GenericEvidenceProvider._get_wikipedia_evidence(
                    "Piranha Games Inc"
                )
            )

        self.assertEqual(status["status"], "available")
        self.assertEqual(result["source_role"], "reference")
        self.assertEqual(result["evidence_level"], "retrieved_reference")
        self.assertIn("video game developer", result["content"])

    def test_factual_queries_prioritize_official_site_and_wikipedia(self):
        provider = GenericEvidenceProvider.__new__(GenericEvidenceProvider)
        provider.max_search_queries = 5
        queries = provider._build_factual_queries(
            query="What can you tell me about Piranha Games Inc?",
            search_queries=[
                "unrelated subreddit discussion",
                "Piranha Games Inc games"
            ],
            subject="Piranha Games Inc"
        )

        self.assertEqual(
            queries[:3],
            [
                '"Piranha Games Inc" official website',
                '"Piranha Games Inc" Wikipedia',
                '"Piranha Games Inc"'
            ]
        )
        self.assertNotIn("unrelated subreddit discussion", queries)
        self.assertIn("Piranha Games Inc games", queries)

    def test_factual_context_filters_irrelevant_and_social_results(self):
        provider = GenericEvidenceProvider()
        provider.max_search_queries = 5
        provider.max_pages = 15
        provider.web = SimpleNamespace(
            search=lambda company, query: [
                {
                    "title": "Piranha Games Official Site",
                    "summary": "Video game developer information",
                    "url": "https://piranha-games.com/about",
                    "source": "Public Web Search",
                    "source_type": "public_web"
                },
                {
                    "title": "Piranha Games - Wikipedia",
                    "summary": "A Canadian video game developer",
                    "url": (
                        "https://en.wikipedia.org/wiki/Piranha_Games"
                    ),
                    "source": "Public Web Search",
                    "source_type": "public_web"
                },
                {
                    "title": "AskGothic subreddit discussion",
                    "summary": "Piranha, auto battletech and frame pages",
                    "url": "https://www.reddit.com/r/AskGothic"
                },
                {
                    "title": "Piranha body fish",
                    "summary": "Fish facts",
                    "url": "https://example.org/piranha-fish"
                }
            ]
        )
        provider.firecrawl = SimpleNamespace(
            health_check=lambda: False
        )
        provider.social = Mock()
        provider.social_summary_builder = Mock()

        with patch(
            "data.providers.generic_evidence_provider."
            "GenericEvidenceProvider._get_wikipedia_evidence",
            return_value=(
                {
                    "title": "Piranha Games",
                    "url": (
                        "https://en.wikipedia.org/wiki/Piranha_Games"
                    ),
                    "source": "en.wikipedia.org",
                    "source_host": "en.wikipedia.org",
                    "source_role": "reference",
                    "source_type": "encyclopedia",
                    "evidence_level": "retrieved_reference",
                    "content": "Piranha Games is a game developer.",
                    "search_query": "Direct Wikipedia article lookup"
                },
                {"status": "available"}
            )
        ):
            evidence = provider.get_context(
                query="What can you tell me about Piranha Games Inc?",
                search_queries=["unrelated subreddit"],
                subject="Piranha Games Inc"
            )

        self.assertEqual(
            [result["source_host"] for result in evidence["results"]],
            ["piranha-games.com", "en.wikipedia.org"]
        )
        self.assertEqual(evidence["social_results"], [])
        self.assertFalse(provider.social.get_context.called)
        self.assertEqual(
            evidence["results"][0]["source_id"],
            "S1"
        )
        self.assertEqual(
            evidence["sources"][1]["publisher"],
            "en.wikipedia.org"
        )

    def test_social_search_only_runs_for_explicit_discussion_requests(self):
        provider = GenericEvidenceProvider()
        provider.max_search_queries = 5
        provider.max_pages = 15
        provider.web = SimpleNamespace(search=lambda company, query: [])
        provider.firecrawl = SimpleNamespace(health_check=lambda: False)
        provider.social = Mock()
        provider.social.get_context.return_value = {
            "results": [],
            "sources": []
        }
        provider.social_summary_builder = SimpleNamespace(
            build=lambda results: {}
        )

        provider.get_context(query="What is Reddit?")
        provider.social.get_context.assert_not_called()

        provider.get_context(
            query="What are people discussing on r/AskGothic?"
        )
        provider.social.get_context.assert_called_once()

    def test_generic_answer_prompt_requires_sources_and_preserves_question(self):
        agent = GenericEvidenceAgent()
        agent.ollama = Mock()
        agent.ollama.generate.return_value = {
            "response": (
                "Piranha Games develops video games [S1]."
            )
        }
        evidence = {
            "results": [{
                "title": "Piranha Games",
                "content": "Piranha Games develops video games.",
                "url": "https://en.wikipedia.org/wiki/Piranha_Games"
            }],
            "sources": [{
                "source_id": "S1",
                "title": "Piranha Games",
                "publisher": "en.wikipedia.org",
                "url": "https://en.wikipedia.org/wiki/Piranha_Games"
            }]
        }

        result = agent.analyze(
            message=(
                "Compare independent coverage and available evidence "
                "about Piranha Games Inc"
            ),
            evidence=evidence,
            research_plan={}
        )
        prompt = agent.ollama.generate.call_args.args[0]

        self.assertIn("Do not reinterpret it", prompt)
        self.assertIn("Do not fill gaps from model memory", prompt)
        self.assertIn("[S1]", prompt)
        self.assertIn("https://en.wikipedia.org/wiki/Piranha_Games", result["response"])
        self.assertIn("Sources:", result["response"])

    def test_direct_factual_answer_uses_page_text_without_model_synthesis(self):
        agent = GenericEvidenceAgent()
        agent.ollama = Mock()
        text = (
            "Piranha Games Inc. is a Canadian video game developer "
            "based in Burnaby, British Columbia. The company was "
            "founded by Russ Bullock and Bryan Ekman."
        )
        evidence = {
            "query": "What can you tell me about Piranha Games Inc?",
            "subject": "Piranha Games Inc",
            "results": [{
                "source_id": "S1",
                "title": "Piranha Games",
                "source": "en.wikipedia.org",
                "source_host": "en.wikipedia.org",
                "source_role": "reference",
                "evidence_level": "retrieved_reference",
                "content": text,
                "url": "https://en.wikipedia.org/wiki/Piranha_Games"
            }],
            "sources": [{
                "source_id": "S1",
                "title": "Piranha Games",
                "publisher": "en.wikipedia.org",
                "url": "https://en.wikipedia.org/wiki/Piranha_Games"
            }]
        }

        result = agent.analyze(
            message="What can you tell me about Piranha Games Inc?",
            evidence=evidence
        )

        agent.ollama.generate.assert_not_called()
        self.assertIn("Burnaby, British Columbia", result["response"])
        self.assertIn("Russ Bullock and Bryan Ekman", result["response"])
        self.assertNotIn("Edmonton", result["response"])
        self.assertNotIn("Cliff Bleszinski", result["response"])
        self.assertNotIn("official website", result["response"].lower())
        self.assertIn("[S1]", result["response"])

    def test_direct_factual_answer_fails_closed_when_only_snippets_exist(self):
        agent = GenericEvidenceAgent()
        agent.ollama = Mock()
        evidence = {
            "subject": "Piranha Games",
            "results": [{
                "source_id": "S1",
                "title": "Piranha Games",
                "summary": "A video game developer",
                "source_role": "reference",
                "evidence_level": "search_snippet",
                "url": "https://en.wikipedia.org/wiki/Piranha_Games"
            }],
            "sources": [{
                "source_id": "S1",
                "title": "Piranha Games",
                "publisher": "en.wikipedia.org",
                "url": "https://en.wikipedia.org/wiki/Piranha_Games"
            }]
        }

        result = agent.analyze(
            message="What can you tell me about Piranha Games?",
            evidence=evidence
        )

        agent.ollama.generate.assert_not_called()
        self.assertIn(
            "Search-result snippets alone are not enough",
            result["response"]
        )
        self.assertNotIn("Sources:", result["response"])


if __name__ == "__main__":
    unittest.main()
