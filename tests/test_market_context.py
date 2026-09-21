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
    company
)


print()
print("=" * 60)
print("MARKET CONTEXT TEST")
print("=" * 60)

print(context)

print("=" * 60)