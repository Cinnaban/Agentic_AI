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


company = {
    "name": "NVIDIA",
    "ticker": "NVDA"
}


filings = (
    provider.normalize_recent_filings(
        company=company,
        limit=5
    )
)


print()
print("=" * 60)
print("SEC NORMALIZED FILINGS TEST")
print("=" * 60)


print(
    "Filings returned:",
    len(filings)
)


for filing in filings:

    print()
    print(
        filing
    )


print("=" * 60)