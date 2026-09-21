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


from orchestrator.hermes import Hermes

from agents.quant_agent import (
    QuantAgent
)

from agents.research_agent import (
    ResearchAgent
)

from data.market_context_provider import (
    MarketContextProvider
)


hermes = Hermes()

quant_agent = QuantAgent()

research_agent = ResearchAgent()

provider = MarketContextProvider()


work_package = hermes.build_workflow(
    "Analyze Nvidia"
)


company = (
    work_package.companies[0]
)


quant_result = (
    quant_agent.analyze(
        work_package
    )
)


market_context = (
    provider.get_context(
        company=company,
        quant_data=quant_result
    )
)


print()
print("=" * 60)
print("EVIDENCE STATUS")
print("=" * 60)

print(
    market_context.get(
        "source_status"
    )
)


sec_facts = (
    market_context
    .get(
        "sec_facts",
        {}
    )
    .get(
        "facts",
        {}
    )
)


print()
print(
    "SEC facts:",
    list(
        sec_facts.keys()
    )
)


print()
print(
    "SEC filings:",
    len(
        market_context.get(
            "sec_filings",
            []
        )
    )
)


result = research_agent.analyze(
    company=company,
    market_context=market_context
)


print()
print("=" * 60)
print("SEC + FINANCIAL GROUNDED RESEARCH")
print("=" * 60)

print(result)

print("=" * 60)