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


from agents.sentiment_agent import (
    SentimentAgent
)

from data.market_context_provider import (
    MarketContextProvider
)


agent = SentimentAgent()

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
print("GROUNDED SENTIMENT TEST")
print("=" * 60)

print(result)

print("=" * 60)