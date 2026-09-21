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


cik = provider.resolve_cik(
    company
)


filings = provider.get_recent_filings(
    company
)


print()
print("=" * 60)
print("SEC IDENTITY TEST")
print("=" * 60)


print(
    "Configured:",
    provider.is_configured()
)


print(
    "CIK:",
    cik
)


print(
    "Filings returned:",
    bool(filings)
)


if isinstance(
    filings,
    dict
):

    print(
        "SEC company name:",
        filings.get(
            "company_name"
        )
    )

    recent_filings = filings.get(
        "filings",
        {}
    )

    if isinstance(
        recent_filings,
        dict
    ):

        forms = recent_filings.get(
            "form",
            []
        )

        dates = recent_filings.get(
            "filingDate",
            []
        )

        print(
            "Recent filing records:",
            len(forms)
        )

        print()
        print("FIRST FIVE FILINGS")

        for index in range(
            min(
                5,
                len(forms)
            )
        ):

            filing_date = (
                dates[index]
                if index < len(dates)
                else None
            )

            print(
                filing_date,
                forms[index]
            )


print("=" * 60)