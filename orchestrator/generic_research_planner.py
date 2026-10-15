import json

from agents.ollama_client import (
    OllamaClient
)

from configs.config import (
    Config
)


class GenericResearchPlanner:

    def __init__(
        self
    ):

        self.ollama = (
            OllamaClient()
        )


    def plan(
        self,
        message,
        active_topic=None
    ):

        if not isinstance(
            message,
            str
        ):

            message = ""


        if not isinstance(
            active_topic,
            str
        ):

            active_topic = ""


        prompt = f"""
You are a public-information research planner.

Your job is NOT to answer the user's question.

Your job is to decide what public-web searches would
help another agent answer the question.

USER QUESTION:

{message}


ACTIVE TOPIC FROM CONVERSATION:

{active_topic or "None"}


First identify the task the user wants performed and the
topics, entities, concepts, and relationships the question
is about. Questions may concern any public-information
domain, including finance, sports, games, science, history,
technology, or culture. Do not assume the topic is a company
or that the question follows a particular sentence pattern.

Generate targeted public-web search queries that preserve
the actual topic and requested relationship.

RULES:

- Return no more than 5 queries.

- Queries should cover different evidence needs.

- Include at least one query that directly searches the
  user's topic or concepts, not the meanings of instruction
  words such as "explain" or "compare".

- Keep every named subject or concept from the question in
  the research scope and relevant searches. If the question
  relates several topics, do not silently drop any of them.

- Interpret the requested relationship from the whole
  question. Compare when comparison is requested; explain
  each concept when that is requested; explain a relationship
  when the question asks how topics relate. Do not force a
  comparison merely because multiple concepts are mentioned.

- For comparisons or explanations involving multiple concepts,
  research several meaningful dimensions that help distinguish
  or connect the topics. Select dimensions that fit the subject,
  and include practical implications or context when reliable
  sources support them.

- Search for reliable sources suited to the topic and claim.
  Use primary or official sources for rules and specifications,
  and reputable independent sources for explanation or context.

- Do not simply repeat the user's question five times.

- Include the organization/topic name when useful.

- For competitor questions, search for competitors,
  alternatives, market participants and industry context.

- For scale questions, search for public indicators
  such as company size, operations, customers, locations,
  funding, market presence or other available scale
  indicators.

- For growth/potential questions, search for market
  context, competitors, company activity and relevant
  industry trends.

- For descriptive questions, prefer organization pages
  and reputable reference material.

- When current activity and historical activity are both
  relevant, search for them separately. Do not infer that
  historical activity is still current.

- Do not invent facts.

Return ONLY valid JSON:

{{
    "intent": "description",

    "task_type": "overview | comparison | explanation | analysis | history | other",

    "research_scope": "One sentence describing the actual topic and task.",

    "queries": [
        "query 1",
        "query 2"
    ],

    "requested_dimensions": [
        "company_description"
    ]
}}
"""


        response = (
            self.ollama.generate(
                prompt,
                model=Config.HERMES_MODEL
            )
        )


        text = response.get(
            "response",
            ""
        )


        try:

            result = json.loads(
                text
            )

        except Exception:

            return {
                "intent":
                    "general_research",

                "task_type":
                    "other",

                "research_scope":
                    message,

                "queries":
                    [
                        message
                    ],

                "requested_dimensions":
                    []
            }

        if not isinstance(result, dict):
            result = {}

        queries = result.get(
            "queries",
            []
        )


        if not isinstance(
            queries,
            list
        ):

            queries = []


        cleaned_queries = []


        for query in queries:

            if not isinstance(
                query,
                str
            ):

                continue


            query = (
                query.strip()
            )


            if not query:

                continue


            if query in cleaned_queries:

                continue


            cleaned_queries.append(
                query
            )


            if len(
                cleaned_queries
            ) >= 5:

                break


        if not cleaned_queries:

            cleaned_queries = [
                message
            ]

                
        evidence_depth = (
            "standard"
        )

        normalized = (
            message
            .strip()
            .lower()
        )


        deep_terms = (
            "compare",
            "competition",
            "competitors",
            "potential",
            "opportunity",
            "growth",
            "market share",
            "market size",
            "why",
            "evaluate",
            "assess",
            "analysis",
            "research"
        )


        summary_terms = (
            "brief",
            "briefly",
            "quick",
            "quickly",
            "summary",
            "summarize",
            "short version",
            "in short",
            "simple explanation"
        )


        if any(
            term in normalized
            for term in summary_terms
        ):

            evidence_depth = (
                "summary"
            )


        elif any(
            term in normalized
            for term in deep_terms
        ):

            evidence_depth = (
                "deep"
            )

        task_type = result.get("task_type", "other")
        if not isinstance(task_type, str) or task_type.casefold() not in {
            "overview",
            "comparison",
            "explanation",
            "analysis",
            "history",
            "other"
        }:
            task_type = "other"
        task_type = task_type.casefold()

        explicit_summary = any(
            term in normalized
            for term in summary_terms
        )
        if not explicit_summary and task_type in {
            "comparison",
            "explanation"
        }:
            evidence_depth = "deep"

        research_scope = result.get("research_scope", message)
        if not isinstance(research_scope, str) or not research_scope.strip():
            research_scope = message

        return {
            "intent":
                result.get(
                    "intent",
                    "general_research"
                ),

            "task_type":
                task_type,

            "research_scope":
                research_scope.strip(),

            "evidence_depth":
                evidence_depth,

            "queries":
                cleaned_queries,

            "requested_dimensions":
                result.get(
                    "requested_dimensions",
                    []
                )
        }