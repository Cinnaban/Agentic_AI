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


from data.market_context_provider import (
    MarketContextProvider
)


provider = MarketContextProvider()


company = {
    "name": "NVIDIA",
    "ticker": "NVDA"
}


context = provider.get_context(
    company=company
)


print()
print("=" * 60)
print("MARKET CONTEXT + SEC TEST")
print("=" * 60)


print(
    "SEC status:",
    context[
        "source_status"
    ].get(
        "sec_filings"
    )
)


filings = context.get(
    "sec_filings",
    []
)


print(
    "SEC filing count:",
    len(filings)
)


for filing in filings:

    print()

    print(
        "Form:",
        filing.get("form")
    )

    print(
        "Date:",
        filing.get(
            "filing_date"
        )
    )

    print(
        "Document:",
        filing.get(
            "primary_document"
        )
    )


print("=" * 60)
