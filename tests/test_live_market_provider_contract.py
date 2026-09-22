import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from data.providers.live_market_providers import LiveMarketProvider

provider = LiveMarketProvider()
company = {"name": "NVIDIA", "ticker": "NVDA"}
context = provider.get_context(company, "What's the latest with Nvidia?")

print()
print("=" * 60)
print("LIVE MARKET PROVIDER CONTRACT TEST")
print("=" * 60)
print("Available:", context.get("available"))
print("Results:", len(context.get("results", [])))
print("Sources:", context.get("sources", []))

assert isinstance(context, dict)
assert "available" in context
assert isinstance(context.get("results"), list)
assert isinstance(context.get("sources"), list)

print()
print("LIVE MARKET PROVIDER CONTRACT TEST PASSED")
print("=" * 60)
