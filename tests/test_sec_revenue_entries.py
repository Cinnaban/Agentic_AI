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


provider = SECProvider()


company = {
    "name": "NVIDIA",
    "ticker": "NVDA"
}


company_facts = (
    provider.get_company_facts(
        company
    )
)


facts = company_facts.get(
    "facts",
    {}
)


us_gaap = facts.get(
    "us-gaap",
    {}
)


print()
print("=" * 60)
print("SEC REVENUE CONCEPT INSPECTION")
print("=" * 60)


for concept, fact in us_gaap.items():

    concept_lower = (
        concept.lower()
    )

    if (
        "revenue" not in concept_lower
        and "sales" not in concept_lower
    ):
        continue

    print()
    print(
        "CONCEPT:",
        concept
    )

    print(
        "LABEL:",
        fact.get(
            "label"
        )
    )

    units = fact.get(
        "units",
        {}
    )

    if not isinstance(
        units,
        dict
    ):
        continue

    for unit, entries in units.items():

        if not isinstance(
            entries,
            list
        ):
            continue

        relevant_entries = [
            entry
            for entry in entries
            if (
                isinstance(
                    entry,
                    dict
                )
                and entry.get(
                    "form"
                ) in {
                    "10-K",
                    "10-Q"
                }
            )
        ]

        relevant_entries.sort(
            key=lambda entry:
                entry.get(
                    "filed",
                    ""
                ),
            reverse=True
        )

        print(
            "UNIT:",
            unit
        )

        for entry in relevant_entries[:5]:

            print(
                {
                    "value":
                        entry.get(
                            "val"
                        ),

                    "filed":
                        entry.get(
                            "filed"
                        ),

                    "form":
                        entry.get(
                            "form"
                        ),

                    "period_start":
                        entry.get(
                            "start"
                        ),

                    "period_end":
                        entry.get(
                           "end"
                        ),

                    "fiscal_year":
                        entry.get(
                            "fy"
                        ),

                    "fiscal_period":
                        entry.get(
                            "fp"
                        )
                }
            )


print()
print("=" * 60)