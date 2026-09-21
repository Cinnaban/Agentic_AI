import sys
import json

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from orchestrator.result_aggregator import (
    ResultAggregator
)

from orchestrator.final_response_builder import (
    FinalResponseBuilder
)

aggregator = ResultAggregator()

builder = FinalResponseBuilder()

execution_results = {
    "research": "Research Complete",
    "sentiment": "Bullish",
    "risk": {
        "risk": "Medium"
    },
    "quant": {
        "signal": "BUY"
    }
}

quality_review = {
    "approved": True,
    "confidence": 95,
    "issues": []
}

aggregated = aggregator.aggregate(
    execution_results,
    quality_review
)

final_response = builder.build(
    aggregated
)

print(final_response)