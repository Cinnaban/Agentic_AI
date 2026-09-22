import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from data.providers.live.yahoo_finance_backend import YahooFinanceBackend

backend = YahooFinanceBackend()
company = {"name": "NVIDIA", "ticker": "NVDA"}
results = backend.search(company=company, query="What's the latest with Nvidia?")

print()
print("=" * 60)
print("YAHOO FINANCE BACKEND TEST")
print("=" * 60)
print("Source:", backend.SOURCE)
print("Results:", len(results))
for result in results[:5]:
    print()
    print(result)
assert isinstance(results, list)
print()
print("YAHOO FINANCE BACKEND TEST PASSED")
print("=" * 60)
