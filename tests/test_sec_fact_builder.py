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


from data.providers.sec_provider import (
    SECProvider
)

from data.providers.sec_fact_builder import (
    SECFactBuilder
)


provider = SECProvider()

builder = SECFactBuilder()


company = {
    "name": "NVIDIA",
    "ticker": "NVDA"
}


company_facts = (
    provider.get_company_facts(
        company
    )
)


result = builder.build(
    company_facts
)


print()
print("=" * 60)
print("SEC FACT BUILDER TEST")
print("=" * 60)


print(
    "Entity:",
    result.get(
        "entity_name"
    )
)


print(
    "CIK:",
    result.get(
        "cik"
    )
)


facts = result.get(
    "facts",
    {}
)


print(
    "Selected facts:",
    len(facts)
)


for name, fact in facts.items():

    print()
    print(
        name
    )

    print(
        "  Concept:",
        fact.get(
            "concept"
        )
    )

    print(
        "  Value:",
        fact.get(
            "value"
        )
    )

    print(
        "  Unit:",
        fact.get(
            "unit"
        )
    )

    print(
        "  Filed:",
        fact.get(
            "filed"
        )
    )

    print(
        "  Form:",
        fact.get(
            "form"
        )
    )


print("=" * 60)