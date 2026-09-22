import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from data.providers.live_market_providers import LiveMarketProvider

provider = LiveMarketProvider()

queries = [
    "Pokemon latest news",
    "Pokemon news today",
    "Pokemon news this week",
]

print()
print("=" * 60)
print("RECENCY POLICY TEST")
print("=" * 60)

for query in queries:
    context = provider.get_context(company={}, query=query)
    print()
    print("Query:", query)
    print("Available:", context.get("available"))
    for item in context.get("results", []):
        print(
            " -",
            item.get("published_at"),
            item.get("source"),
            item.get("title")
        )

print()
print("RECENCY POLICY TEST COMPLETE")
print("=" * 60)
