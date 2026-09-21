import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from agents.company_detection_agent import (
    CompanyDetectionAgent
)

agent = CompanyDetectionAgent()

result = agent.analyze(
    "Should I buy Nvidia?"
)

print(result)