import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from orchestrator.hermes import Hermes

hermes = Hermes()
queries = [
    "Evaluate the current state of SCHD",
    "What is SCHD described",
    "Analyze Nvidia",
]

print()
print("=" * 60)
print("ETF / COMPANY ROUTING TEST")
print("=" * 60)

for query in queries:
    print()
    print("Query:", query)
    try:
        workflow = hermes.build_workflow(query)
        print("Workflow type:", type(workflow).__name__)
        print("Workflow:", workflow)
    except Exception as exc:
        print("ERROR:", repr(exc))

print()
print("=" * 60)
