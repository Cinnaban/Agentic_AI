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
    company=company,

    original_message=(
        "What's the latest with Nvidia?"
    ),

    requires_live_data=True
)


print()
print("=" * 60)
print("LIVE MARKET CONTEXT TEST")
print("=" * 60)


print(
    "Live status:",
    context[
        "source_status"
    ].get(
        "live_market_context"
    )
)


print(
    "Live context:",
    context.get(
        "live_market_context"
    )
)


assert (
    context[
        "source_status"
    ][
        "live_market_context"
    ]
    == "unavailable"
)


print()
print(
    "LIVE MARKET CONTEXT TEST PASSED"
)

print("=" * 60)