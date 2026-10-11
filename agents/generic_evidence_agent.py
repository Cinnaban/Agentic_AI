import re
import json

from agents.ollama_client import (
    OllamaClient
)

from configs.config import (
    Config
)


class GenericEvidenceAgent:

    DIRECT_FACTUAL_REQUEST = re.compile(
        r"\b(?:what\s+is|who\s+is|tell\s+me\s+about|"
        r"what\s+can\s+you\s+tell\s+me\s+about|"
        r"describe|give\s+me\s+(?:an?\s+)?overview\s+of)\b",
        re.IGNORECASE
    )

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
        social_summary = (
            evidence.get(
                "social_summary",
                {}
            )
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

        if self.DIRECT_FACTUAL_REQUEST.search(
            str(message or "")
        ):
            return self._build_direct_factual_response(
                message,
                evidence,
                results
            )


        prompt = f"""
You are answering a general informational question.

OVERRIDING ACCURACY RULES:

- Answer the exact subject and question in USER QUESTION.
- Do not reinterpret it as a question about a subreddit,
  community, discussion, or another topic unless the user
  explicitly asks about that topic.
- Do not use conversation history or social discussion as
  factual evidence for this answer.
- Use only factual claims supported by the supplied webpage
  content, clearly attributed reference sources, or search
  summaries when page content is unavailable.
- Prefer retrieved pages from a subject's own website for
  what the subject says about itself. Prefer Wikipedia,
  government/academic pages, and independent reporting for
  corroboration. A search result labeled "official" is only a
  candidate until its URL and retrieved content support that.
- Present a claim from an official page as the organization's
  own description unless an independent source corroborates it.
- For dates, locations, ownership, achievements, and other
  specific claims, prefer agreement between independent sources.
  If only one secondary source supports a detail, qualify it
  and attribute it; omit it if the evidence is unclear.
- Treat a single search snippet as unverified. Do not state
  specific facts from it as certain.
- For an important factual statement, cite a supplied source
  ID such as [S1]. Never invent a source ID or URL.
- If reliable sources disagree, explain the discrepancy and
  attribute each version. Do not merge incompatible claims.
- If the evidence does not establish a fact, say it could not
  be verified. Do not fill gaps from model memory.
- Keep the answer direct. Do not force an "interpreted
  question" or assessment format onto a simple factual request.

USER QUESTION:

{message}

DIRECT FACTUAL REQUESTS:

If the user asks:

- What is X?
- Who is X?
- Tell me about X
- What can you tell me about X?
- Describe X

DO NOT rewrite the question.

DO NOT generate an interpreted question.

Retrieve evidence and summarize only the
retrieved evidence.

RESEARCH PLAN:

{json.dumps(
    research_plan,
    indent=2,
    default=str
)}

RETRIEVED PUBLIC EVIDENCE:

SOCIAL SUMMARY:

The evidence may contain:
- social_results
- social_summary

When social_summary exists:
- prefer it over individual posts
- summarize recurring themes
- avoid repeating every post
- identify major discussion topics
``

{json.dumps(
    evidence,
    indent=2,
    default=str
)}

SOCIAL EVIDENCE:

The evidence may contain:

social_results
social_summary

When social_summary exists,
use it as the primary source
for discussion signals rather
than repeating every individual
post.

SOCIAL DISCUSSION SUMMARY:

{json.dumps(
    social_summary,
    indent=2,
    default=str
)}

PUBLIC DISCUSSION PREFERENCE:

- Use discussion_themes when available.
- Use top_keywords as supporting context.
- Use sample_posts only as examples.
- Do not treat discussion patterns as verified facts.
- Clearly separate discussion signals from evidence.
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
  
- The research plan describes what evidence was sought.

- Use requested_dimensions to determine whether the
retrieved evidence adequately covers the user's
question.

- If several requested dimensions lack meaningful
evidence, lower the confidence of the Assessment
rather than inventing conclusions.
  
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

LOW-CONFIDENCE RESPONSE RULES:

If the evidence does not support a confident direct
answer, do not fall back to phrases such as:

- "I don't know"
- "my knowledge is limited"
- "you would need to research this"
- "I cannot analyze this"

when useful retrieved evidence exists.

Instead:

1. Briefly state how the user's question was
   interpreted.

2. Give a one-word Assessment based only on the
   supplied evidence.

3. Explain what the evidence supports.

4. Explain what important evidence is missing.

Allowed Assessment labels should be short and
appropriate to the question, for example:

- Strong
- Moderate
- Limited
- Potential
- Unclear
- Unknown

Use "Unknown" when the evidence genuinely cannot
support even a qualitative assessment.

Use "Unclear" when relevant evidence exists but points
to an incomplete or inconclusive answer.

Never manufacture certainty merely to produce an
Assessment.

RESPONSE FORMAT FOR AMBIGUOUS OR LOW-CONFIDENCE
QUESTIONS:

Interpreted question:
"<brief descriptive rewording of the user's question>"

Assessment: <one-word assessment>

Then answer in 2-4 short sections using the retrieved
evidence.

Conclude with one brief limitation when important
information could not be verified.

For simple factual questions that are directly answered
by the evidence, do not force this format.

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

SOCIAL EVIDENCE RULES:

- Reddit and X represent public discussion.
- Public discussion is not verified fact.
- Public discussion may be used to identify:
  - recurring themes
  - user experiences
  - developer opinions
  - public concerns
  - community reactions

- Public discussion must not be treated as:
  - audited financial information
  - official company statements
  - scientific proof
  - regulatory findings
  - verified market data

- When social evidence is used:
  clearly distinguish discussion
  from verified evidence.

- If public discussion conflicts with
  authoritative evidence, authoritative
  evidence takes priority.

- Do not present rumors, speculation,
  or unsupported claims as facts.

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

CONTENT PRIORITY:

When both a search-result summary and Firecrawl
content exist for the same result:

1. Use the Firecrawl-retrieved webpage content to
   understand the source.
2. Use the search-result title/summary only as
   discovery context.
3. Do not repeat search-engine wording when the
   underlying page provides clearer information.

FINAL RESPONSE STRUCTURE:

Always anchor the response to the user's original
question.

For research-backed generic questions, prefer:

Question:
"<the user's question or a concise faithful rewording>"

Answer:
Give the direct answer first in 1-3 sentences.

Context:
Provide only the supporting public evidence needed
to understand the answer.

Evidence limitations:
Include this only when an important part of the
answer could not be verified.

Do not begin with a long discussion of research
methodology.

Do not list every search result.

Do not describe Firecrawl, Bing, Google or DDGS as
the factual source of a claim.

The underlying webpage or publisher is the source.

When Firecrawl content is supplied, use that page
content to understand and summarize the source.

Keep the response concise unless the research plan
requested deep evidence.

FINAL CHECK BEFORE RESPONDING:

Verify that the answer names the subject asked about, that
every factual statement is supported by the supplied evidence,
and that citations use only the supplied source IDs. Do not
include social discussion unless the user explicitly requested
social or community discussion.
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

        sources = evidence.get("sources", [])
        source_lines = []
        if isinstance(sources, list):
            for source in sources:
                if not isinstance(source, dict):
                    continue
                source_id = source.get("source_id")
                title = source.get("title")
                url = source.get("url")
                publisher = source.get("publisher")
                if not all(
                    isinstance(value, str) and value.strip()
                    for value in (source_id, title, url)
                ):
                    continue
                attribution = (
                    f" ({publisher})"
                    if isinstance(publisher, str) and publisher
                    else ""
                )
                source_lines.append(
                    f"- [{source_id}] {title}{attribution}: {url}"
                )

        if source_lines:
            text = (
                text.rstrip()
                + "\n\nSources:\n"
                + "\n".join(source_lines)
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

    @staticmethod
    def _retrieved_sentences(content):
        if not isinstance(content, str) or not content.strip():
            return []

        text = re.sub(
            r"\[([^\]]+)\]\((?:https?://[^)]+)\)",
            r"\1",
            content
        )
        text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
        text = re.sub(r"`{1,3}", "", text)
        text = re.sub(r"\*\*|__|[*_]", "", text)
        text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
        text = re.sub(r"\\?\[\d+\\?\]", "", text)

        sentences = []
        for paragraph in re.split(r"\n\s*\n", text):
            paragraph = re.sub(r"\s+", " ", paragraph).strip(" -|")
            if not paragraph or paragraph.lower().startswith(
                ("contents", "from wikipedia", "jump to", "navigation menu")
            ):
                continue
            for sentence in re.split(
                r"(?<=[.!?])\s+(?=[A-Z0-9])",
                paragraph
            ):
                sentence = sentence.strip()
                if (
                    50 <= len(sentence) <= 360
                    and sentence[-1] in ".!?"
                    and sentence not in sentences
                ):
                    sentences.append(sentence)
        return sentences

    @staticmethod
    def _sentence_highlight_type(sentence):
        text = sentence.lower()
        achievement_terms = (
            "award", "awarded", "won ", "winner", "nominated",
            "recognition", "recognized", "acclaimed", "best-selling",
            "bestselling", "oldest", "first "
        )
        project_terms = (
            "game", "games", "project", "projects", "title", "titles",
            "franchise", "series", "developed", "co-developed",
            "developing", "in development", "published", "released",
            "created", "worked on", "contributed to", "developer of"
        )
        if any(term in text for term in achievement_terms):
            return "achievement"
        if any(term in text for term in project_terms):
            return "project"
        return None

    @staticmethod
    def _is_current_project_statement(sentence):
        return bool(re.search(
            r"\b(?:currently\s+(?:developing|working\s+on|producing)|"
            r"(?:is|are)\s+(?:currently\s+)?"
            r"(?:developing|working\s+on|producing)|"
            r"(?:is|are|was|were)\s+in\s+development|"
            r"upcoming|under\s+development|"
            r"next\s+(?:game|project|title)|"
            r"active\s+development)\b",
            sentence,
            re.IGNORECASE
        ))

    @staticmethod
    def _subject_terms(subject):
        ignored = {
            "about", "company", "corporation", "corp", "inc",
            "incorporated", "limited", "llc", "ltd", "organization",
            "what", "who"
        }
        return [
            term
            for term in re.findall(r"[a-z0-9]+", str(subject or "").lower())
            if term not in ignored
        ]

    @classmethod
    def _content_matches_subject(cls, content, subject):
        terms = cls._subject_terms(subject)
        if not terms:
            return True
        introductory_text = " ".join(
            cls._retrieved_sentences(content)[:5]
        ).lower()
        return all(term in introductory_text for term in terms)

    @classmethod
    def _build_direct_factual_response(
        cls,
        message,
        evidence,
        results
    ):
        subject = evidence.get("subject") or evidence.get("query") or ""
        sources = evidence.get("sources", [])
        source_by_id = {
            source.get("source_id"): source
            for source in sources
            if (
                isinstance(source, dict)
                and isinstance(source.get("source_id"), str)
            )
        } if isinstance(sources, list) else {}

        pages = []
        seen_source_ids = set()
        for result in results:
            if not isinstance(result, dict):
                continue
            if result.get("evidence_level") not in {
                "retrieved_webpage",
                "retrieved_reference"
            }:
                continue
            if result.get("source_role") not in {
                "official_candidate",
                "reference",
                "government_or_academic",
                "independent_or_other"
            }:
                continue

            source_id = result.get("source_id")
            if (
                not isinstance(source_id, str)
                or source_id not in source_by_id
                or source_id in seen_source_ids
            ):
                continue
            source = source_by_id.get(source_id, {})
            url = result.get("url") or source.get("url")
            if not isinstance(url, str) or not url.startswith(
                ("https://", "http://")
            ):
                continue
            sentences = cls._retrieved_sentences(result.get("content"))
            if not sentences or not cls._content_matches_subject(
                result.get("content"),
                subject
            ):
                continue
            pages.append({
                "source_id": source_id,
                "title": (
                    result.get("title")
                    or source.get("title")
                    or result.get("source_host")
                    or "Retrieved webpage"
                ),
                "publisher": (
                    source.get("publisher")
                    or result.get("source_host")
                    or result.get("source")
                ),
                "url": url,
                "sentences": sentences
            })
            seen_source_ids.add(source_id)
            if len(pages) >= 3:
                break

        if not pages:
            return {
                "status": "completed",
                "response": (
                    "I couldn't verify a factual summary from readable, "
                    "subject-matched source pages. Search-result snippets "
                    "alone are not enough to support a reliable answer."
                ),
                "sources": []
            }

        overview_terms = (
            " is a ", " is an ", " is the ", " was founded ",
            " was established ", " based in "
        )
        overview = None
        highlights = []
        for page in pages:
            for sentence in page["sentences"]:
                tagged = {
                    "sentence": sentence,
                    "source_id": page["source_id"],
                    "type": cls._sentence_highlight_type(sentence)
                }
                if (
                    overview is None
                    and any(term in sentence.lower() for term in overview_terms)
                ):
                    overview = tagged
                if tagged["type"]:
                    highlights.append(tagged)

        achievement_highlights = [
            item for item in highlights
            if item["type"] == "achievement"
        ]
        project_highlights = [
            item for item in highlights
            if item["type"] == "project"
        ]
        current_projects = [
            item for item in project_highlights
            if cls._is_current_project_statement(item["sentence"])
        ][:3]
        past_highlights = [
            item for item in achievement_highlights + project_highlights
            if item not in current_projects
        ][:max(0, 5 - len(current_projects))]
        selected_highlights = current_projects + past_highlights
        unique_highlights = []
        seen_sentences = set()
        for item in selected_highlights:
            normalized_sentence = item["sentence"].casefold()
            if normalized_sentence in seen_sentences:
                continue
            seen_sentences.add(normalized_sentence)
            unique_highlights.append(item)
        current_projects = [
            item for item in unique_highlights
            if item in current_projects
        ]
        past_highlights = [
            item for item in unique_highlights
            if item not in current_projects
        ]
        selected_items = (
            ([overview] if overview else [])
            + current_projects
            + past_highlights
        )
        used_source_ids = {
            item["source_id"] for item in selected_items
        }

        lines = [
            f"Source-grounded summary: {subject or message.strip()}",
            "Each point below is an unrewritten statement from a retrieved "
            "page; the source is identified beside it."
        ]
        if overview:
            lines.extend([
                "",
                "**About:**",
                (
                    f"- {overview['sentence']} "
                    f"[{overview['source_id']}]"
                )
            ])
        lines.extend([
            "",
            "**Current projects stated by the sources:**"
        ])
        if current_projects:
            lines.extend(
                f"- {item['sentence']} [{item['source_id']}]"
                for item in current_projects
            )
        else:
            lines.append(
                "- The retrieved sources did not verify a project "
                "currently in development or identified as upcoming."
            )
        if past_highlights:
            lines.extend([
                "",
                "**Notable games, projects, and achievements stated by "
                "the sources:**"
            ])
            lines.extend(
                f"- {item['sentence']} [{item['source_id']}]"
                for item in past_highlights
            )
        elif not current_projects:
            lines.extend([
                "",
                "The retrieved readable pages did not provide a complete "
                "sentence supporting a specific game, project, or "
                "achievement."
            ])

        source_lines = ["", "Sources:"]
        for page in pages:
            if page["source_id"] not in used_source_ids:
                continue
            source_lines.append(
                f"- [{page['source_id']}] {page['title']} "
                f"({page['publisher']}): {page['url']}"
            )

        return {
            "status": "completed",
            "response": "\n".join(lines + source_lines),
            "sources": [
                source_by_id[page["source_id"]]
                for page in pages
                if page["source_id"] in used_source_ids
            ]
        }
