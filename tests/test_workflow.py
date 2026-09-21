import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))


from orchestrator.hermes import (
    Hermes
)

hermes = Hermes()

result = hermes.build_workflow(
    "Analyze Nvidia"
)

print(result)