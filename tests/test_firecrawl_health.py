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


from data.providers.live.firecrawl_backend import (
    FirecrawlBackend
)


backend = FirecrawlBackend()


print()
print("=" * 60)
print("FIRECRAWL HEALTH TEST")
print("=" * 60)


print(
    "Configured:",
    backend.is_configured()
)


healthy = (
    backend.health_check()
)


print(
    "Healthy:",
    healthy
)


assert backend.is_configured()

assert healthy


print()
print(
    "FIRECRAWL HEALTH TEST PASSED"
)

print("=" * 60)