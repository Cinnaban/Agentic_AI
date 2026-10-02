import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from orchestrator.hermes import Hermes

hermes = Hermes()

queries = [
    "Can you compare Amazon, Walmart and Target?",
    "Which of Amazon, Walmart and Target has the strongest profitability?",
    "Which of Amazon, Walmart and Target has the strongest balance sheet?",
]

for query in queries:
    print("\n" + "=" * 70)
    print("QUERY:", query)
    result = hermes.process_request(
        message=query,
        source="comparison_question_test",
        channel_id="comparison_question_chat",
        user_id="comparison_question_user",
    )
    print("STATUS:", result.get("status"))
    print("HAS RESPONSE:", bool(result.get("response")))
    print("RESPONSE PREVIEW:", result.get("response", "")[:2500])
    assert result.get("status") == "completed"
    assert result.get("response")

print("\nQUESTION-AWARE COMPARISON TEST PASSED")
