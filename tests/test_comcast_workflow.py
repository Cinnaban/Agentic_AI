import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))
    
from orchestrator.hermes import (
    Hermes
)
hermes = Hermes()

workflow = hermes.build_workflow(
    "Analyze Comcast"
)

print(type(workflow))
print(workflow)

if hasattr(workflow, "job_id"):
    print("SUCCESS")
    print(workflow.job_id)
else:
    print("FAILED ROUTING")