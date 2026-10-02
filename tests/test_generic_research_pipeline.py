import sys

from pathlib import Path


ROOT_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)


if str(ROOT_DIR) not in sys.path:

    sys.path.append(
        str(ROOT_DIR)
    )


from orchestrator.generic_research_planner import (
    GenericResearchPlanner
)

from data.providers.generic_evidence_provider import (
    GenericEvidenceProvider
)


question = (
    "Is there a large potential for Yrefy "
    "compared to their competition?"
)


planner = (
    GenericResearchPlanner()
)


provider = (
    GenericEvidenceProvider()
)


plan = planner.plan(
    message=question,
    active_topic="Yrefy"
)


print()
print("=" * 70)
print("RESEARCH PLAN")
print("=" * 70)

print(
    plan
)


context = provider.get_context(
    query=question,

    search_queries=(
        plan.get(
            "queries",
            []
        )
    ),

    research_plan=plan
)


print()
print("=" * 70)
print("RETRIEVED EVIDENCE")
print("=" * 70)


print(
    "AVAILABLE:",
    context.get(
        "available"
    )
)


print(
    "SEARCH QUERIES:",
    context.get(
        "search_queries"
    )
)


print(
    "RESULT COUNT:",
    len(
        context.get(
            "results",
            []
        )
    )
)


for item in context.get(
    "results",
    []
)[:10]:

    print()
    print(
        "SEARCH:",
        item.get(
            "search_query"
        )
    )

    print(
        "TITLE:",
        item.get(
            "title"
        )
    )

    print(
        "URL:",
        item.get(
            "url"
        )
    )

    print(
        "SOURCE TYPE:",
        item.get(
            "source_type"
        )
    )

    print(
        "FIRECRAWL:",
        bool(
            item.get(
                "content"
            )
        )
    )


assert context.get(
    "available"
)


assert context.get(
    "results"
)


assert len(
    context.get(
        "search_queries",
        []
    )
) >= 2


print()
print(
    "GENERIC RESEARCH PIPELINE TEST PASSED"
)
