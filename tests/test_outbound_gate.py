import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from security.outbound_gate import (
    OutboundResponseGate
)


gate = OutboundResponseGate()


response = {
    "summary": "NVIDIA analysis completed.",
    "internal_server": "192.168.50.1",
    "internal_path":
        r"D:\Agentic_AI\DiscordETF\data.json",
    "analysis": {
        "ticker": "NVDA",
        "score": 95
    }
}


safe_response = gate.prepare(
    response
)


print(safe_response)