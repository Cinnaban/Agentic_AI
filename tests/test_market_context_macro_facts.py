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


from data.market_context_provider import (
    MarketContextProvider
)


provider = MarketContextProvider()


company = {
    "name": "NVIDIA",
    "ticker": "NVDA"
}


context = provider.get_context(
    company=company
)


print()
print("=" * 60)
print("MARKET CONTEXT + MACRO FACTS TEST")
print("=" * 60)


print(
    "Macro status:",
    context[
        "source_status"
    ].get(
        "macro"
    )
)


macro_facts = context.get(
    "macro_facts",
    {}
)


print(
    "Macro fact count:",
    len(macro_facts)
)


for name, fact in (
    macro_facts.items()
):

    print()

    print(
        name,
        "->",
        fact
    )


print("=" * 60)