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


from data.providers.live_market_providers import (
    LiveMarketProvider
)


provider = LiveMarketProvider()


result = provider._normalize_result(
    title=(
        "NVIDIA Test Current Event"
    ),

    published_at=(
        "2026-09-21"
    ),

    source=(
        "TEST_SOURCE"
    ),

    summary=(
        "Synthetic live-market "
        "normalization test."
    ),

    url=(
        "https://example.com/test"
    )
)


print()
print("=" * 60)
print("LIVE MARKET PROVIDER TEST")
print("=" * 60)


print(
    result
)


assert result.get(
    "title"
)

assert (
    result.get(
        "source_type"
    )
    == "live_market"
)


print()
print(
    "LIVE MARKET PROVIDER TEST PASSED"
)

print("=" * 60)
