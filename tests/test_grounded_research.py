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


from agents.research_agent import ResearchAgent
from data.market_context_provider import (
    MarketContextProvider
)


agent = ResearchAgent()

provider = MarketContextProvider()


company = {
    "name": "NVIDIA",
    "ticker": "NVDA"
}


context = provider.get_context(
    company
)


result = agent.analyze(
    company=company,
    market_context=context
)


print()
print("=" * 60)
print("GROUNDED RESEARCH TEST")
print("=" * 60)

print(result)

print("=" * 60)