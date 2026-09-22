import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))


from data.providers.live_market_providers import LiveMarketProvider

provider = LiveMarketProvider()
context = provider.get_context(
    company={},
    query="Pokemon latest news"
)

print()
print("=" * 60)
print("LIVE MARKET ENRICHMENT TEST")
print("=" * 60)
print("Available:", context.get("available"))
print("Results:", len(context.get("results", [])))
print("Sources:", context.get("sources", []))

enriched = [
    item for item in context.get("results", [])
    if item.get("content")
]

print("Enriched results:", len(enriched))

for item in enriched[:3]:
    print()
    print("Title:", item.get("title"))
    print("Source:", item.get("source"))
    print("Retrieved by:", item.get("content_retrieved_by"))
    print("Content length:", len(item.get("content", "")))

assert context.get("available") is True
assert context.get("results")
assert enriched

print()
print("LIVE MARKET ENRICHMENT TEST PASSED")
print("=" * 60)
