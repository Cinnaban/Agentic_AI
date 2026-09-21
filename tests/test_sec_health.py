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


result = provider.health_check()


print()
print("=" * 60)
print("SEC PROVIDER HEALTH TEST")
print("=" * 60)

print(
    "Configured:",
    result.get(
        "configured"
    )
)

print(
    "Reachable:",
    result.get(
        "reachable"
    )
)

print("=" * 60)