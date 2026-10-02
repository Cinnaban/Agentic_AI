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
        str(
            ROOT_DIR
        )
    )


from orchestrator.generic_research_planner import (
    GenericResearchPlanner
)


planner = GenericResearchPlanner()


questions = [
    "What is Yrefy?",

    (
        "Is there a large potential for Yrefy "
        "compared to their competition?"
    ),

    "Who are Yrefy's competitors?",

    "How large is Yrefy?"
]


for question in questions:

    print()
    print("=" * 70)
    print(
        "QUESTION:",
        question
    )

    plan = planner.plan(
        message=question,
        active_topic="Yrefy"
    )


    print(
        "PLAN:",
        plan
    )


    assert plan.get(
        "queries"
    )


    assert len(
        plan[
            "queries"
        ]
    ) <= 5


print()
print(
    "GENERIC RESEARCH PLANNER TEST PASSED"
)
