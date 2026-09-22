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


from data.providers.live.public_news_backend import (
    PublicNewsBackend
)


backend = PublicNewsBackend()


company = {
    "name": "NVIDIA",
    "ticker": "NVDA"
}


results = backend.search(
    company=company,
    query="What's the latest with Nvidia?"
)


print()
print("=" * 60)
print("LIVE MARKET BACKEND TEST")
print("=" * 60)


print(
    "Source:",
    backend.SOURCE
)


print(
    "Results:",
    results
)


assert (
    backend.SOURCE
    == "public_news"
)

assert isinstance(
    results,
    list
)


print()
print(
    "LIVE MARKET BACKEND TEST PASSED"
)

print("=" * 60)