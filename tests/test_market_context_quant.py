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

from data.market_context_provider import (
    MarketContextProvider
)


hermes = Hermes()

quant_agent = QuantAgent()

provider = MarketContextProvider()


work_package = hermes.build_workflow(
    "Analyze Nvidia"
)


quant_result = quant_agent.analyze(
    work_package
)


company = (
    work_package.companies[0]
)


context = provider.get_context(
    company=company,
    quant_data=quant_result
)


print()
print("=" * 60)
print("MARKET CONTEXT + QUANT TEST")
print("=" * 60)


print(
    "Financial data status:",
    context[
        "source_status"
    ][
        "financial_data"
    ]
)


financial_data = (
    context.get(
        "financial_data",
        {}
    )
)


print(
    "Ticker:",
    financial_data.get(
        "ticker"
    )
)


print(
    "Price:",
    financial_data.get(
        "price"
    )
)


print(
    "Beta:",
    financial_data.get(
        "beta"
    )
)


print(
    "Recommendation:",
    financial_data.get(
        "recommendation"
    )
)


print(
    "Forecast consensus:",
    financial_data.get(
        "forecast_consensus"
    )
)


print(
    "Financial fields:",
    len(
        financial_data
    )
)


print("=" * 60)