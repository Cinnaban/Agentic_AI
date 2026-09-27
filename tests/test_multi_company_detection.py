import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from agents.company_detection_agent import CompanyDetectionAgent
from orchestrator.hermes import Hermes

message = "Compare Nvidia, Intel and AMD"

agent = CompanyDetectionAgent()
hermes = Hermes()

print("=" * 70)
print("MULTI-COMPANY DETECTION TEST")
print("=" * 70)
print("Message:", message)

detection = agent.analyze(message)
print("Detection:", detection)

workflow = hermes.build_workflow(message)
print("Workflow type:", type(workflow).__name__)
print("Companies:", getattr(workflow, "companies", None))
print("Required agents:", getattr(workflow, "required_agents", None))

assert detection.get("is_company_request") is True
assert len(detection.get("companies", [])) >= 3
assert hasattr(workflow, "job_id")
assert len(workflow.companies) >= 3

print("MULTI-COMPANY DETECTION TEST PASSED")
