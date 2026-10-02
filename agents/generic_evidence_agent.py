import json

from agents.ollama_client import (
    OllamaClient
)

from configs.config import (
    Config
)


class GenericEvidenceAgent:

    def __init__(
        self
    ):

        self.ollama = (
            OllamaClient()
        )


    def analyze(
        self,
        message,
        evidence,
        research_plan=None
    ):

        if not isinstance(
            research_plan,
            dict
        ):

            research_plan = {}


        if not isinstance(
            evidence,
            dict
        ):

            evidence = {}


        results = evidence.get(
            "results",
            []
        )


        if not results:

            return {
                "status":
                    "completed",

                "response":
                    (
                        "I couldn't find enough "
                        "public information to give "
                        "a useful answer."
                    )
            }


        prompt = f"""
You are answering a general informational question.

USER QUESTION:

{message}

RESEARCH PLAN:

{json.dumps(
    research_plan,
    indent=2,
    default=str
)}

RETRIEVED PUBLIC EVIDENCE:

{json.dumps(
    evidence,
    indent=2,
    default=str
)}

RESEARCH-PLAN RULES:

- Answer the user's original question, not the search
  queries.

- Search queries describe evidence needs and are not
  factual claims.

- Use requested_dimensions to understand which aspects
  of the question should receive the most attention.

- Synthesize across different retrieved pages.

- If the evidence supports only a qualitative comparison,
  provide a qualitative answer instead of inventing
  precise rankings.

- If exact size, revenue, market share, employee count,
  or other values cannot be verified, state that
  limitation briefly.
  
RESEARCH COVERAGE RULES:

- Review evidence from every planned search query
  before concluding that a requested research
  dimension is unavailable.

- Do not judge evidence availability only from the
  first few retrieved webpages.

- For each requested_dimension, inspect evidence
  associated with relevant search_query values.

- Distinguish between:

  1. no evidence discovered,
  2. search-result evidence discovered but full page
     retrieval unavailable,
  3. full Firecrawl content retrieved.

- Search-result titles and summaries may support
  cautious discovery-level observations, but they
  are not verified precise facts.

- Give Firecrawl-extracted page content greater
  evidentiary weight than a short search-result
  snippet.

- Do not say competitor, market, growth, funding,
  customer, or industry information was unavailable
  when supplied evidence actually discusses that
  dimension.

- If relevant evidence exists but is insufficient
  for a precise numerical conclusion, summarize the
  qualitative evidence and clearly state that the
  exact figure could not be verified.
  
EVIDENCE INTERPRETATION RULES:

- Inspect the supplied evidence before describing
  what information is unavailable.

- Never state that a source, company website, homepage,
  or webpage was unavailable when it appears in the
  supplied evidence.

- A result whose URL belongs to the organization being
  discussed should be treated as direct organization
  evidence when the page content was successfully
  retrieved.

- Prefer direct organization webpages for describing
  what the organization says it does.

- Use independent reporting or reference sources when
  evaluating claims about reputation, controversy,
  competitors, scale, or external assessments.

- Never describe DuckDuckGo, Bing, Google, or Firecrawl
  as the original publisher of a claim.

- Search engines are discovery mechanisms.

- Firecrawl is a retrieval mechanism.

- Attribute claims to the webpage or publisher from
  which the content originated.

- Before saying information is unavailable, verify that
  the requested information does not appear anywhere in
  the supplied evidence.

SOURCE PRIORITY FOR DESCRIPTIVE QUESTIONS:

1. Direct organization website
2. Government or regulatory material
3. Established reporting
4. Industry/reference sources
5. Other public webpages
6. Search-result snippets when full content is unavailable

EVIDENCE WEIGHTING:

For describing what an organization does:

1. Direct organization webpages
2. Government or regulatory material
3. Established independent reporting
4. Industry or reference sources
5. Other public webpages
6. Search-result snippets

For competition, market position, scale, reputation,
or growth potential:

1. Government or regulatory evidence
2. Established independent reporting
3. Multiple independent industry/reference sources
4. Direct organization claims
5. Other public webpages
6. Search-result snippets

Do not treat estimated values from company-profile,
directory, aggregator, or secondary webpages as
audited financial facts.

When evidence sources disagree, describe the
disagreement rather than silently choosing the
stronger-looking claim.

RULES:

- Answer the user's actual question directly.

- Use the retrieved evidence as the factual basis
  for specific claims when possible.

- This is a general-information route, not a strict
  financial-analysis route.

- Official organization pages, public webpages,
  reference pages, and public reporting may be used
  for ordinary descriptive claims.

- Prefer Firecrawl-extracted page content when it is
  supplied.

- Keep source attribution attached to the original
  publisher or webpage.

- DuckDuckGo is a discovery mechanism.

- Firecrawl is a retrieval mechanism.

- Do not invent precise revenue, valuation,
  employee-count, or other financial figures when
  those figures are not supplied.

- When evidence is incomplete, qualify the answer.

- Do not present an unverified public claim as an
  audited or independently verified fact.

- Be concise and useful for Telegram or Discord.
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


        if not isinstance(
            text,
            str
        ):

            text = ""


        text = (
            text.strip()
        )


        if not text:

            text = (
                "Public information was retrieved, "
                "but I couldn't generate a useful "
                "summary."
            )


        return {
            "status":
                "completed",

            "response":
                text,

            "sources":
                evidence.get(
                    "sources",
                    []
                )
        }