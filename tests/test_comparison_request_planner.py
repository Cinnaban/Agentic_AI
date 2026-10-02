import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from orchestrator.comparison_request_planner import ComparisonRequestPlanner

planner = ComparisonRequestPlanner()

cases = {
    "Can you compare Amazon, Walmart and Target?": {"needs_quant": True, "needs_risk": True},
    "Which has the strongest profitability?": {"dimensions": ["profitability"], "needs_quant": True},
    "Which has the strongest balance sheet?": {"dimensions": ["financial_strength"], "needs_quant": True},
    "Which is the least risky?": {"dimensions": ["risk"], "needs_quant": True, "needs_risk": True},
    "What is the latest outlook?": {"needs_live": True},
}

for message, expected in cases.items():
    plan = planner.plan(message)
    print("\nMESSAGE:", message)
    print("PLAN:", plan)
    for key, value in expected.items():
        if key == "dimensions":
            for dimension in value:
                assert dimension in plan["dimensions"]
        else:
            assert plan[key] == value

print("\nCOMPARISON REQUEST PLANNER TEST PASSED")
