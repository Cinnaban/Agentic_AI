import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))


from orchestrator.followup_resolver import (
    FollowUpResolver
)


resolver = FollowUpResolver()


context = {
    "active_entities": [
        {
            "name": "NVIDIA",
            "ticker": "NVDA"
        },

        {
            "name": "Intel",
            "ticker": "INTC"
        },

        {
            "name": "AMD",
            "ticker": "AMD"
        }
    ],

    "last_intent":
        "company_comparison"
}


result = resolver.resolve(
    message=(
        "Which has the strongest balance sheet?"
    ),
    context=context
)


print(
    result
)


assert result

assert (
    result[
        "is_followup"
    ]
    is True
)


assert (
    result[
        "intent"
    ]
    == "company_comparison"
)


tickers = {
    entity[
        "ticker"
    ]
    for entity
    in result[
        "entities"
    ]
}


assert tickers == {
    "NVDA",
    "INTC",
    "AMD"
}


print(
    "FOLLOW-UP RESOLVER TEST PASSED"
)