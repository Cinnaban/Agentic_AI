import json

from agents.ollama_client import (
    OllamaClient
)

from configs.config import (
    Config
)


class CurrentTopicAgent:

    def __init__(
        self
    ):

        self.ollama = (
            OllamaClient()
        )


    def analyze(
        self,
        message,
        live_context
    ):

        if not isinstance(
            live_context,
            dict
        ):

            live_context = {}


        results = live_context.get(
            "results",
            []
        )


        if not results:

            return {
                "status":
                    "completed",

                "response": (
                    "I couldn't verify current "
                    "information from the configured "
                    "live sources."
                )
            }


        prompt = f"""
You are answering a current-information question.

CURRENT-EVIDENCE REQUIREMENTS:

- The supplied Retrieved Current Evidence is the only
  allowed source for claims about recent or current events.

- Do not mention your model knowledge cutoff.

- Treat the supplied recency policy as authoritative
  for this response.

- Do not describe evidence outside that policy window
  as current.

- If no results survive the recency policy, state that
  no sufficiently recent evidence was retrieved.

- Never fall back to model-memory events when a current
  request has no surviving recent evidence.
  
- Never mention the model's training cutoff as the date
  of current information.

- Do not say that your latest knowledge is from 2023,
  2024, 2025, or any other model-training date.

- Do not answer a current-information question from
  general model memory when retrieved current evidence
  is available.

- Determine recency from the supplied publication dates,
  not from model memory.

- Prefer the newest relevant supplied evidence.

- When Firecrawl content is available, use that content
  as the detailed evidence for the associated article.

- The original article publisher remains the source.
  Firecrawl is only the retrieval mechanism.

- If current evidence is available, answer from it.

- If current evidence is unavailable, explicitly state:
  "I couldn't verify current information from the
  configured live sources."

- Never substitute stale model knowledge for unavailable
  live evidence.

- Never describe the model's training cutoff or model
  knowledge date as the date of the current information.

User Question:

{message}

Retrieved Current Evidence:

{json.dumps(
    live_context,
    indent=2
)}

RULES:

- Answer the user's question using the supplied
  current evidence.

- Prefer Firecrawl-extracted content when a result
  contains "content".

- Use the original publisher in "source" as the
  evidence source.

- Firecrawl is a retrieval mechanism, not the
  publisher.

- DuckDuckGo is a discovery mechanism, not the
  publisher.

- Preserve publication dates when relevant.

- Do not use general model memory as evidence for
  current events.

- Do not invent events or developments that are
  absent from the supplied evidence.

- Public reporting is not automatically an
  independently verified fact.

- If several independent supplied publishers report
  the same development, you may note that multiple
  supplied sources report it.

- If the retrieved evidence is insufficient to answer
  part of the question, explicitly say so.

Provide a concise, useful response suitable for
Telegram or Discord.
"""


        response = (
            self.ollama.generate(
                prompt,
                model=Config.HERMES_MODEL
            )
        )


        model_response = response.get(
            "response",
            ""
        )


        if not isinstance(
            model_response,
            str
        ):

            model_response = ""


        model_response = (
            model_response.strip()
        )


        if not model_response:

            return {
                "status":
                    "completed",

                "response": (
                    "Current information was "
                    "retrieved, but the response "
                    "could not be generated."
                )
            }


        return {
            "status":
                "completed",

            "response":
                model_response,

            "live_sources":
                live_context.get(
                    "sources",
                    []
                )
        }