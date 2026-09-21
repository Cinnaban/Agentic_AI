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
from workers.agent_executor import AgentExecutor


hermes = Hermes()
executor = AgentExecutor()


work_package = hermes.build_workflow(
    "Analyze Nvidia"
)
work_package.required_agents["quant"] = True
work_package.required_agents["risk"] = True

print(
    "TEST REQUIRED AGENTS:",
    work_package.required_agents
)

results = executor.execute(
    work_package
)

print()
print("=" * 60)
print("GROUNDED RISK TEST")
print("=" * 60)

print(
    results.get(
        "risk"
    )
)

print("=" * 60)