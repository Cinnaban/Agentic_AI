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


history = context.get(
    "history",
    {}
)


print()
print("=" * 60)
print("MACRO HISTORY TEST")
print("=" * 60)


for name, observations in (
    history.items()
):

    print()

    print(
        name,
        "observations:",
        len(observations)
    )

    for observation in (
        observations[:3]
    ):

        print(
            observation
        )


print("=" * 60)