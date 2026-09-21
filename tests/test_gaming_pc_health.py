import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from workers.gaming_pc_bridge import (
    GamingPCBridge
)


bridge = GamingPCBridge()

result = bridge.health_check()

print(result)