import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from data.providers.live_market_providers import LiveMarketProvider

provider = LiveMarketProvider()
query = "Pokemon latest news"
context = provider.get_context(company={}, query=query)

print()
print("=" * 60)
print("LIVE EVIDENCE DATE TEST")
print("=" * 60)
print("Available:", context.get("available"))

results = context.get("results", [])
for item in results:
    print()
    print("Published:", item.get("published_at"))
    print("Source:", item.get("source"))
    print("Title:", item.get("title"))
    print("Enriched:", bool(item.get("content")))

assert isinstance(results, list)
print()
print("LIVE EVIDENCE DATE TEST PASSED")
print("=" * 60)
