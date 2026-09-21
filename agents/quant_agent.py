import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from workers.gaming_pc_bridge import GamingPCBridge

class QuantAgent:

    def __init__(self):
        self.bridge = GamingPCBridge()

    def analyze(
        self,
        work_package
    ):

        result = self.bridge.submit_job(
            work_package
        )

        return result