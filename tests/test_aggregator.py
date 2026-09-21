import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from orchestrator.result_aggregator import (
    ResultAggregator
)

aggregator = ResultAggregator()

results = {
    "research": "Research Result",
    "sentiment": "Sentiment Result",
    "quant": {
        "signal": "BUY"
    },
    "risk": {
        "risk": "MEDIUM"
    }
}

final_results = aggregator.aggregate(
    results
)

print(final_results)