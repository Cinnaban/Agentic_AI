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


provider = MacroProvider()


context = provider.get_context()


print()
print("=" * 60)
print("MACRO PROVIDER TEST")
print("=" * 60)


print(
    "Configured:",
    provider.is_configured()
)


for category in [
    "interest_rates",
    "inflation",
    "employment",
    "economic_growth"
]:

    print()

    print(
        category,
        "->",
        context.get(
            category
        )
    )


print()
print(
    "Source:",
    context.get(
        "source"
    )
)


print("=" * 60)