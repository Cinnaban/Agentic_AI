import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from agents.qwen_manager import (
    QwenManager
)

manager = QwenManager()

results = {
    "research": "NVIDIA develops GPUs",
    "sentiment": "Mostly bullish",
    "risk": {
        "risk_level": "medium"
    },
    "quant": {
        "quant_status": "pending"
    }
}

review = manager.review(
    results
)

print(review)