import sys
import traceback
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from orchestrator.hermes import Hermes

hermes = Hermes()

queries = [
    "Tell me the latest about INTC",
    "Tell me about i9 14900KS",
    "Tell me about Steam Deck",
    "What is the Steam Deck",
]

print()
print("=" * 70)
print("FAILURE TRACE TEST")
print("=" * 70)

for query in queries:
    print()
    print("QUERY:", query)
    print("-" * 70)

    try:
        result = hermes.process_request(
            message=query,
            source="test_failure_trace"
        )

        print("RESULT TYPE:", type(result).__name__)
        print("STATUS:", result.get("status") if isinstance(result, dict) else None)
        print("ERROR:", result.get("error") if isinstance(result, dict) else None)
        print("RESPONSE AVAILABLE:", bool(result.get("response")) if isinstance(result, dict) else False)
        print("FULL RESULT:", result)

    except Exception as exc:
        print("EXCEPTION TYPE:", type(exc).__name__)
        print("EXCEPTION:", repr(exc))
        traceback.print_exc()

print()
print("=" * 70)
