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


from data.providers.macro_provider import (
    MacroProvider
)

from data.providers.macro_fact_builder import (
    MacroFactBuilder
)


provider = MacroProvider()

builder = MacroFactBuilder()


macro_context = (
    provider.get_context()
)


facts = builder.build(
    macro_context
)


print()
print("=" * 60)
print("MACRO FACT BUILDER TEST")
print("=" * 60)


for name, fact in facts.items():

    print()

    print(
        name,
        "->",
        fact
    )


print()
print("=" * 60)