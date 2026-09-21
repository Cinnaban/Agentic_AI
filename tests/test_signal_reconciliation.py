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
from agents.quant_agent import QuantAgent
from agents.signal_reconciliation_agent import (
    SignalReconciliationAgent
)


hermes = Hermes()

quant_agent = QuantAgent()

reconciler = SignalReconciliationAgent()


work_package = hermes.build_workflow(
    "Analyze Nvidia"
)


quant_result = quant_agent.analyze(
    work_package
)


result = reconciler.analyze(
    quant_result
)


print()
print("=" * 60)
print("SIGNAL RECONCILIATION TEST")
print("=" * 60)

print(result)

print("=" * 60)