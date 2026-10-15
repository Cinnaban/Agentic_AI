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

    def test_search_queries_preserve_varied_multi_topic_requests(self):
        provider = GenericEvidenceProvider.__new__(GenericEvidenceProvider)
        provider.max_search_queries = 5
        requests = (
            "Explain the difference between mutual funds and ETFs",
            "Compare mutual funds and ETFs",
            "Explain mutual funds and ETFs",
            "Mutual Funds vs ETFs",
            "Explain the difference between FPS gaming and RTS gaming",
            "Compare FPS gaming and RTS gaming",
            "Explain MOBA gaming to FPS and RTS gaming",
            "Compare the Lakers and Celtics"
        )
        for query in requests:
            with self.subTest(query=query):
                planned_queries = [f"reliable sources about {query}"]
                queries = provider._build_factual_queries(
                    query=query,
                    search_queries=planned_queries,
                    subject=None
                )
                self.assertEqual(queries[0], query)
                self.assertIn(planned_queries[0], queries)

    def test_search_result_relevance_is_domain_neutral(self):
        cases = (
            (
                "Explain the difference between mutual funds and ETFs",
                "Mutual funds versus exchange-traded funds",
                "Key - meaning and usage"
            ),
            (
                "Compare FPS gaming and RTS gaming",
                "FPS and RTS games: genres and gameplay",
                "Key - meaning and usage"
            ),
            (
                "Compare the Lakers and Celtics",
                "Lakers-Celtics rivalry",
                "Key - meaning and usage"
            )
        )
        for query, relevant_title, unrelated_title in cases:
            with self.subTest(query=query):
                results = GenericEvidenceProvider._rank_and_filter_results(
                    [{
                        "title": unrelated_title,
                        "summary": "A key is used to open a lock.",
                        "url": "https://dictionary.example/key",
                        "search_query": query
                    }, {
                        "title": relevant_title,
                        "summary": relevant_title,
                        "url": "https://example.org/topic",
                        "search_query": query
                    }],
                    query=query
                )
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["title"], relevant_title)

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

    def test_factual_queries_keep_user_question_and_planned_searches(self):
        provider = GenericEvidenceProvider.__new__(GenericEvidenceProvider)
        provider.max_search_queries = 5
        original_query = "Compare NASCAR and Formula One racing"
        planned_queries = [
            "NASCAR and Formula One rules and race formats",
            "NASCAR and Formula One authoritative sources"
        ]
        queries = provider._build_factual_queries(
            query=original_query,
            search_queries=planned_queries,
            subject=None
        )

        self.assertEqual(
            queries,
            [original_query] + planned_queries
        )

    def test_context_preserves_topic_and_filters_irrelevant_search_results(self):
        provider = GenericEvidenceProvider()
        provider.freshness_detector = SimpleNamespace(
            requires_live_data=lambda query: False
        )
        provider.reference_archive = Mock()
        provider.reference_archive.get_query.return_value = None
        provider.max_search_queries = 5
        provider.max_pages = 15
        search_result = {
            "title": "NASCAR history and origins",
            "summary": "A history of NASCAR racing",
            "url": "https://www.nascar.com/history/",
            "source": "Public Web Search",
            "source_type": "public_web"
        }
        irrelevant_result = {
            "title": "Tell | English meaning",
            "summary": "History of the word tell",
            "url": "https://dictionary.cambridge.org/dictionary/english/tell",
            "source": "Public Web Search",
            "source_type": "public_web"
        }
        provider.web = SimpleNamespace(
            search=Mock(return_value=[
                dict(search_result),
                dict(irrelevant_result)
            ])
        )
        query_text = "Explain the difference between NASCAR and Formula One"
        planned_queries = [
            "NASCAR and Formula One rules and race formats",
            "NASCAR and Formula One history from reputable sources"
        ]

        with patch.object(
            GenericEvidenceProvider,
            "_get_wikipedia_evidence",
            return_value=(None, {"status": "not_found"})
        ), patch.object(
            provider,
            "_enrich",
            side_effect=lambda results, **kwargs: results
        ):
            evidence = provider.get_context(
                query=query_text,
                search_queries=planned_queries
            )

        self.assertIsNone(evidence["subject"])
        self.assertIn(query_text, evidence["search_queries"])
        self.assertTrue(all(
            query in evidence["search_queries"]
            for query in planned_queries
        ))
        self.assertTrue(evidence["results"])
        self.assertEqual(
            [result["title"] for result in evidence["results"]],
            ["NASCAR history and origins"]
        )
        self.assertEqual(
            provider.web.search.call_count,
            len(evidence["search_queries"])
        )

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
            evidence["results"][0]["url"],
            "https://piranha-games.com/"
        )
        self.assertIn(
            "en.wikipedia.org",
            [result["source_host"] for result in evidence["results"]]
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

    def test_official_homepage_is_scraped_as_primary_evidence(self):
        provider = GenericEvidenceProvider()
        provider.web = SimpleNamespace(search=lambda company, query: [{
            "title": "Piranha Games Official Website",
            "summary": "Official website for Piranha Games",
            "url": "https://piranha-games.com/games",
            "source": "Public Web Search",
            "source_type": "public_web"
        }])
        provider.firecrawl = SimpleNamespace(
            health_check=Mock(return_value=True),
            retrieve=Mock(return_value={
                "markdown": (
                    "Piranha Games is a video game developer. "
                    "The studio develops games in the MechWarrior series."
                ),
                "metadata": {"title": "Piranha Games"}
            })
        )
        provider.social = Mock()
        provider.social_summary_builder = Mock()

        with patch.object(
            GenericEvidenceProvider,
            "_get_wikipedia_evidence",
            return_value=(None, {"status": "not_found"})
        ):
            evidence = provider.get_context(
                query="What can you tell me about Piranha Games?",
                subject="Piranha Games"
            )

        homepage = next(
            result for result in evidence["results"]
            if result.get("page_kind") == "official_homepage"
        )
        self.assertEqual(
            homepage["url"],
            "https://piranha-games.com/"
        )
        self.assertEqual(
            homepage["evidence_level"],
            "retrieved_webpage"
        )
        self.assertIn("MechWarrior", homepage["content"])
        provider.firecrawl.retrieve.assert_any_call(
            "https://piranha-games.com/"
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
        self.assertIn("Use a simplified structure with these sections in order", prompt)
        self.assertIn("develop 3-5 relevant, evidence-backed", prompt)
        self.assertIn("practical significance", prompt)
        self.assertIn("not describing what the question asks", prompt)
        self.assertNotIn("Assessment labels", prompt)
        self.assertNotIn("Question:\n", prompt)
        self.assertNotIn("Interpreted question:", prompt)
        self.assertIn("private chain-of-thought", prompt)
        self.assertIn("[S1]", prompt)
        self.assertIn("https://en.wikipedia.org/wiki/Piranha_Games", result["response"])
        self.assertIn("Sources:", result["response"])

    def test_generic_response_keeps_summary_answer_assessment_and_sources(self):
        agent = GenericEvidenceAgent()
        agent.ollama = Mock()
        agent.ollama.generate.return_value = {
            "response": (
                "Here is my attempt at answering the question with the "
                "provided evidence and rules:\n\n"
                "Question interpretation:\n"
                "Compare ETFs and mutual funds.\n\n"
                "Summary: ETFs and mutual funds pool investors' money "
                "but differ in trading and management [S1].\n\n"
                "Answer interpretation:\n"
                "Explain pricing and management.\n\n"
                "Answer: ETFs trade throughout the day, while mutual "
                "funds are priced once daily [S1].\n"
                "- ETFs often track indexes, while mutual funds may be "
                "actively managed [S1].\n\n"
                "Context interpretation:\n"
                "Both pool investor money.\n\n"
                "Assessment: These differences are supported by the cited "
                "source; no independent confirmation was provided.\n\n"
                "Sources:\n- [S1] fund guide"
            )
        }
        evidence = {
            "results": [{
                "title": "Fund guide",
                "content": "ETF and mutual fund details",
                "url": "https://example.org/funds"
            }],
            "sources": [{
                "source_id": "S1",
                "title": "Fund guide",
                "publisher": "Example",
                "url": "https://example.org/funds"
            }, {
                "source_id": "S2",
                "title": "Unrelated dictionary entry",
                "publisher": "Dictionary",
                "url": "https://example.org/dictionary"
            }]
        }

        result = agent.analyze(
            "Explain the difference between mutual funds and ETFs",
            evidence
        )
        response = result["response"]

        self.assertTrue(response.startswith("Summary:"))
        self.assertIn("Answer:\nETFs trade throughout", response)
        self.assertIn("Assessment:\nThese differences are supported", response)
        self.assertIn("Sources:\n- [S1] Fund guide (Example)", response)
        self.assertTrue(response.endswith("https://example.org/funds"))
        self.assertNotIn("Unrelated dictionary", response)
        for unwanted in (
            "Here is my attempt",
            "Question interpretation:",
            "Answer interpretation:",
            "Context interpretation:",
            "fund guide\n\nSources:"
        ):
            self.assertNotIn(unwanted, response)

    def test_planned_comparison_uses_topic_synthesis_not_direct_fact_path(self):
        agent = GenericEvidenceAgent()
        agent.ollama = Mock()
        agent.ollama.generate.return_value = {
            "response": (
                "Summary: The two racing series use different formats [S1].\n\n"
                "Answer: NASCAR uses stock cars and oval-heavy schedules; "
                "Formula One uses purpose-built cars and international "
                "Grand Prix circuits [S1].\n\n"
                "Assessment: These distinctions are supported by the cited "
                "source."
            )
        }
        evidence = {
            "results": [{
                "title": "NASCAR and Formula One",
                "content": "Information about both racing series.",
                "url": "https://sports.example/racing"
            }],
            "sources": [{
                "source_id": "S1",
                "title": "NASCAR and Formula One",
                "publisher": "Sports Reference",
                "url": "https://sports.example/racing"
            }]
        }

        result = agent.analyze(
            "What is the difference between NASCAR and Formula One?",
            evidence,
            research_plan={
                "task_type": "comparison",
                "research_scope": (
                    "Compare NASCAR and Formula One as motorsport series."
                )
            }
        )
        prompt = agent.ollama.generate.call_args.args[0]

        self.assertIn("NASCAR and Formula One as motorsport series", prompt)
        self.assertIn("What is the difference between NASCAR and Formula One?", prompt)
        self.assertTrue(result["response"].startswith("Summary:"))
        self.assertIn("Sources:", result["response"])

    def test_overview_answer_is_synthesized_from_retrieved_page(self):
        agent = GenericEvidenceAgent()
        agent.ollama = Mock()
        agent.ollama.generate.return_value = {
            "response": (
                "Summary: Piranha Games develops video games [S1].\n\n"
                "Answer: The studio develops games in the MechWarrior "
                "series [S1].\n\n"
                "Assessment: The retrieved page supports this brief "
                "description."
            )
        }
        text = (
            "Piranha Games Inc. is a Canadian video game developer "
            "based in Burnaby, British Columbia. "
            "Notable titles developed by the studio include "
            "MechWarrior Online and MechWarrior 5: Mercenaries. "
            "Piranha Games is one of the oldest game developers in "
            "the Greater Vancouver area.\\[2\\] "
            "This final fragment should not be included"
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
            evidence=evidence,
            research_plan={"task_type": "overview"}
        )

        agent.ollama.generate.assert_called_once()
        self.assertIn("Piranha Games develops video games", result["response"])
        self.assertIn("[S1]", result["response"])

    def test_history_task_returns_source_grounded_summary(self):
        agent = GenericEvidenceAgent()
        agent.ollama = Mock()
        evidence = {
            "query": "Tell me the history of Razer Hong Kong",
            "subject": "Razer Hong Kong",
            "results": [{
                "source_id": "S1",
                "title": "Razer",
                "source": "en.wikipedia.org",
                "source_host": "en.wikipedia.org",
                "source_role": "reference",
                "evidence_level": "retrieved_reference",
                "content": (
                    "Razer Hong Kong is part of Razer Inc., a company "
                    "founded in 2005 by Min-Liang Tan and Robert Krakoff. "
                    "The company launched its first gaming products in "
                    "2005 and expanded into additional markets afterward."
                ),
                "url": "https://en.wikipedia.org/wiki/Razer"
            }],
            "sources": [{
                "source_id": "S1",
                "title": "Razer",
                "publisher": "en.wikipedia.org",
                "url": "https://en.wikipedia.org/wiki/Razer"
            }]
        }

        result = agent.analyze(
            message="Tell me the history of Razer Hong Kong",
            evidence=evidence,
            research_plan={"task_type": "history"}
        )

        agent.ollama.generate.assert_not_called()
        self.assertNotIn("History summary:", result["response"])
        self.assertIn("founded in 2005", result["response"])
        self.assertIn("launched its first gaming products in 2005", result["response"])
        self.assertIn("[S1]", result["response"])
        self.assertNotIn("Assessment:", result["response"])
        self.assertNotIn("Answer the original question", result["response"])

    def test_prompt_instructions_from_model_are_replaced_with_evidence_summary(self):
        agent = GenericEvidenceAgent()
        agent.ollama = Mock()
        agent.ollama.generate.return_value = {
            "response": (
                "Answer the original question in 2-4 short sections using "
                "the retrieved evidence. Do not replace it with a rephrased "
                "question."
            )
        }
        evidence = {
            "subject": "Piranha Games Inc",
            "results": [{
                "source_id": "S1",
                "title": "Piranha Games",
                "source": "en.wikipedia.org",
                "source_host": "en.wikipedia.org",
                "source_role": "reference",
                "evidence_level": "retrieved_reference",
                "content": (
                    "Piranha Games Inc. is a Canadian video game developer "
                    "based in Burnaby, British Columbia. The studio developed "
                    "MechWarrior Online and other video games."
                ),
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
            message="Compare independent coverage about Piranha Games Inc",
            evidence=evidence
        )

        self.assertIn("Burnaby, British Columbia", result["response"])
        self.assertNotIn(
            "Answer the original question in 2-4 short sections",
            result["response"]
        )
        self.assertNotIn("Do not replace it", result["response"])
        self.assertIn("[S1]", result["response"])

    def test_reused_archive_evidence_is_disclosed_in_direct_answers(self):
        agent = GenericEvidenceAgent()
        agent.ollama = Mock()
        evidence = {
            "subject": "Example Research",
            "archive_reused": True,
            "archive_as_of": "2026-10-01T00:00:00+00:00",
            "results": [{
                "source_id": "S1",
                "title": "Example Research",
                "source": "example.org",
                "source_host": "example.org",
                "source_role": "reference",
                "evidence_level": "retrieved_reference",
                "content": (
                    "Example Research is a nonprofit publisher of "
                    "public educational research materials."
                ),
                "url": "https://example.org/about"
            }],
            "sources": [{
                "source_id": "S1",
                "title": "Example Research",
                "publisher": "example.org",
                "url": "https://example.org/about"
            }]
        }

        result = agent.analyze(
            "What is Example Research?",
            evidence,
            research_plan={"task_type": "history"}
        )

        self.assertIn("not revalidated for this request", result["response"])
        self.assertIn("2026-10-01", result["response"])
        agent.ollama.generate.assert_not_called()

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
            evidence=evidence,
            research_plan={"task_type": "history"}
        )

        agent.ollama.generate.assert_not_called()
        self.assertIn(
            "Search-result snippets alone are not enough",
            result["response"]
        )
        self.assertNotIn("Sources:", result["response"])

    def test_direct_factual_answer_rejects_page_text_for_another_subject(self):
        agent = GenericEvidenceAgent()
        evidence = {
            "subject": "Piranha Games Inc",
            "results": [{
                "source_id": "S1",
                "title": "Piranha Games",
                "source_role": "reference",
                "evidence_level": "retrieved_reference",
                "content": (
                    "The Wikimedia Foundation is a nonprofit, tax-exempt "
                    "organization. It operates Wikipedia and other "
                    "collaborative knowledge projects. "
                    "We have earned the Platinum Seal of Transparency "
                    "from Candid."
                ),
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
            evidence=evidence,
            research_plan={"task_type": "history"}
        )

        self.assertIn(
            "couldn't verify a factual summary",
            result["response"]
        )
        self.assertNotIn("Wikimedia Foundation", result["response"])
        self.assertNotIn("Sources:", result["response"])

    def test_general_overview_is_not_forced_into_project_template(self):
        agent = GenericEvidenceAgent()
        agent.ollama = Mock()
        agent.ollama.generate.return_value = {
            "response": (
                "Summary: The Boston Celtics are a professional basketball "
                "team [S1].\n\n"
                "Answer: The Celtics compete in the NBA and play home games "
                "in Boston [S1].\n\n"
                "Assessment: The cited page supports this overview."
            )
        }
        evidence = {
            "subject": "Boston Celtics",
            "results": [{
                "source_id": "S1",
                "title": "Boston Celtics",
                "source_role": "reference",
                "evidence_level": "retrieved_webpage",
                "content": (
                    "The Boston Celtics are a professional basketball team "
                    "that competes in the NBA."
                ),
                "url": "https://sports.example/celtics"
            }],
            "sources": [{
                "source_id": "S1",
                "title": "Boston Celtics",
                "publisher": "Sports Reference",
                "url": "https://sports.example/celtics"
            }]
        }

        result = agent.analyze(
            message="What can you tell me about the Boston Celtics?",
            evidence=evidence,
            research_plan={"task_type": "overview"}
        )
        prompt = agent.ollama.generate.call_args.args[0]

        self.assertIn("Boston Celtics", prompt)
        self.assertNotIn("Notable work", prompt)
        self.assertNotIn("current projects", prompt)
        self.assertIn("professional basketball team", result["response"])

    def test_homepage_uses_generic_source_grounded_response_path(self):
        agent = GenericEvidenceAgent()
        agent.ollama = Mock()
        agent.ollama.generate.return_value = {
            "response": (
                "Summary: Piranha Games describes itself as a video game "
                "developer [S1].\n\n"
                "Answer: Its page discusses the MechWarrior series [S1].\n\n"
                "Assessment: This summary reflects the organization's own "
                "description."
            )
        }
        content = (
            "Piranha Games is a video game developer based in Burnaby. "
            "The studio develops games in the MechWarrior series, including "
            "MechWarrior Online and MechWarrior 5: Clans."
        )
        evidence = {
            "subject": "Piranha Games",
            "results": [{
                "source_id": "S1",
                "title": "Piranha Games",
                "page_kind": "official_homepage",
                "source_role": "official_candidate",
                "evidence_level": "retrieved_webpage",
                "content": content,
                "url": "https://piranha-games.com/"
            }],
            "sources": [{
                "source_id": "S1",
                "title": "Piranha Games",
                "publisher": "piranha-games.com",
                "url": "https://piranha-games.com/"
            }]
        }

        result = agent.analyze(
            message="What can you tell me about Piranha Games?",
            evidence=evidence,
            research_plan={
                "task_type": "overview",
                "research_scope": "Summarize the Piranha Games homepage."
            }
        )
        prompt = agent.ollama.generate.call_args.args[0]

        self.assertIn("MechWarrior Online and MechWarrior 5: Clans", prompt)
        self.assertIn("Do not follow", prompt)
        self.assertIn("Summarize the Piranha Games homepage", prompt)
        self.assertIn("MechWarrior", result["response"])
        self.assertIn("https://piranha-games.com/", result["response"])
        self.assertEqual(result["sources"], evidence["sources"])

    def test_firecrawl_does_not_replace_direct_reference_article_text(self):
        provider = GenericEvidenceProvider.__new__(GenericEvidenceProvider)
        provider.firecrawl = SimpleNamespace(
            health_check=Mock(return_value=True),
            retrieve=Mock()
        )
        result = {
            "title": "Piranha Games",
            "url": "https://en.wikipedia.org/wiki/Piranha_Games",
            "source_role": "reference",
            "evidence_level": "retrieved_reference",
            "content": "Verified Wikipedia article text.",
            "search_query": "Direct Wikipedia article lookup"
        }

        enriched = provider._enrich([result], page_limit=1)

        self.assertEqual(
            enriched[0]["content"],
            "Verified Wikipedia article text."
        )
        provider.firecrawl.retrieve.assert_not_called()

    def test_firecrawl_content_with_unrelated_page_title_is_discarded(self):
        provider = GenericEvidenceProvider.__new__(GenericEvidenceProvider)
        provider.firecrawl = SimpleNamespace(
            health_check=Mock(return_value=True),
            retrieve=Mock(return_value={
                "markdown": (
                    "The Wikimedia Foundation is a nonprofit organization."
                ),
                "metadata": {
                    "title": "Wikimedia Foundation"
                }
            })
        )
        result = {
            "title": "Piranha Games",
            "url": "https://piranha-games.com/about",
            "source_role": "official_candidate",
            "evidence_level": "search_snippet",
            "summary": "Piranha Games developer",
            "search_query": '"Piranha Games" official website'
        }

        enriched = provider._enrich([result], page_limit=1)

        self.assertNotIn("content", enriched[0])
        self.assertEqual(
            enriched[0]["evidence_level"],
            "search_snippet"
        )


if __name__ == "__main__":
    unittest.main()
