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


from orchestrator.comparison_intent import (
    ComparisonIntent
)


detector = ComparisonIntent()


companies = [
    {
        "ticker": "NVDA"
    },

    {
        "ticker": "INTC"
    },

    {
        "ticker": "AMD"
    }
]


assert detector.is_comparison(
    "Compare Nvidia, Intel and AMD",
    companies
)


assert detector.is_comparison(
    "Which has the strongest growth?",
    companies
)


assert not detector.is_comparison(
    "Analyze Nvidia",
    [
        {
            "ticker": "NVDA"
        }
    ]
)


print(
    "COMPARISON INTENT TEST PASSED"
)