import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from orchestrator.hermes import Hermes
from workers.gaming_pc_bridge import (GamingPCBridge)


hermes = Hermes()

bridge = GamingPCBridge()

work_package = hermes.build_workflow(
    "Analyze Nvidia"
)

submission = bridge.submit_job(
    work_package
)

print(submission)