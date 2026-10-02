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


Generate targeted search queries.

RULES:

- Return no more than 5 queries.

- Queries should cover different evidence needs.

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

- Do not invent facts.

Return ONLY valid JSON:

{{
    "intent": "description",

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

                "queries":
                    [
                        message
                    ],

                "requested_dimensions":
                    []
            }


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


        return {
            "intent":
                result.get(
                    "intent",
                    "general_research"
                ),

            "queries":
                cleaned_queries,

            "requested_dimensions":
                result.get(
                    "requested_dimensions",
                    []
                )
        }