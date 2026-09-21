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


from agents.risk_agent import RiskAgent


agent = RiskAgent()


company = {
    "name": "NVIDIA",
    "ticker": "NVDA"
}


result = agent.analyze(
    company
)


print()
print("=" * 60)
print("RISK AGENT TEST")
print("=" * 60)

print(result)

print("=" * 60)