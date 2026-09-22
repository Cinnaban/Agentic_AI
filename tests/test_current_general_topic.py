import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from orchestrator.hermes import Hermes

hermes = Hermes()
message = "What's new with Pokemon?"

print()
print("=" * 60)
print("CURRENT GENERAL TOPIC TEST")
print("=" * 60)
print("Message:", message)

result = hermes.process_request(
    message=message,
    source="test_current_general"
)

print("Status:", result.get("status"))
print("Response available:", bool(result.get("response")))

response = result.get("response", "")
if isinstance(response, str):
    print()
    print(response[:5000])

assert result.get("status") == "completed"
assert result.get("response")

print()
print("CURRENT GENERAL TOPIC TEST PASSED")
print("=" * 60)
