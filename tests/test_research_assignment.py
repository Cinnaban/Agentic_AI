import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))


from agents.research_assignment_agent import (
    ResearchAssignmentAgent
)

agent = ResearchAssignmentAgent()

result = agent.analyze(
    company_data=[
        {
            "name": "NVIDIA",
            "ticker": "NVDA"
        }
    ],
    user_message="What is Nvidia?"
)

print(result)