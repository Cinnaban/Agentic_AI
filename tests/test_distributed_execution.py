import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from orchestrator.hermes import Hermes
from workers.agent_executor import AgentExecutor


hermes = Hermes()

executor = AgentExecutor()


work_package = hermes.build_workflow(
    "Analyze Nvidia"
)


print("WORK PACKAGE:")
print(work_package)


results = executor.execute(
    work_package
)


print("EXECUTION RESULTS:")

print(results)