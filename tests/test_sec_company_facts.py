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


result = provider.get_company_facts(
    company
)


print()
print("=" * 60)
print("SEC COMPANY FACTS TEST")
print("=" * 60)


print(
    "CIK:",
    result.get(
        "cik"
    )
)


print(
    "Entity:",
    result.get(
        "entity_name"
    )
)


facts = result.get(
    "facts",
    {}
)


print(
    "Fact namespaces:",
    list(
        facts.keys()
    )
)


us_gaap = facts.get(
    "us-gaap",
    {}
)


print(
    "US GAAP fact count:",
    len(
        us_gaap
    )
)


print(
    "Example fact names:"
)


for name in list(
    us_gaap.keys()
)[:10]:

    print(
        " -",
        name
    )


print("=" * 60)