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

from data.providers.macro_provider import (
    MacroProvider
)

from data.providers.rss_news_provider import (
    RSSNewsProvider
)


company = {
    "name": "NVIDIA",
    "ticker": "NVDA"
}


sec = SECProvider()

macro = MacroProvider()

rss = RSSNewsProvider()


print()
print("=" * 60)
print("PUBLIC DATA PROVIDER TEST")
print("=" * 60)


print(
    "SEC company facts:",
    sec.get_company_facts(
        company
    )
)


print(
    "SEC recent filings:",
    sec.get_recent_filings(
        company
    )
)


print(
    "Macro context:",
    macro.get_context()
)


print(
    "RSS news:",
    rss.get_news(
        company
    )
)


print("=" * 60)