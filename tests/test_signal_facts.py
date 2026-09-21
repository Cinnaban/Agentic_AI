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
from orchestrator.signal_fact_builder import (
    SignalFactBuilder
)


hermes = Hermes()

quant_agent = QuantAgent()

fact_builder = SignalFactBuilder()


work_package = hermes.build_workflow(
    "Analyze Nvidia"
)


quant_result = quant_agent.analyze(
    work_package
)


facts = fact_builder.build(
    quant_result
)


print()
print("=" * 60)
print("SIGNAL FACT TEST")
print("=" * 60)


print("DIRECTIONS:")

for field, data in (
    facts["directions"].items()
):
    print(
        field,
        "->",
        data
    )


print()
print("AGREEMENTS:")

for agreement in facts["agreements"]:
    print(
        agreement
    )


print()
print("CONFLICTS:")

for conflict in facts["conflicts"]:
    print(
        conflict
    )


print()
print("HORIZON DIFFERENCES:")

for difference in (
    facts["horizon_differences"]
):
    print(
        difference
    )


print("=" * 60)