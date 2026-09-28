import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from orchestrator.hermes import Hermes

hermes = Hermes()

source = "telegram"
channel_id = "context_test_chat"
user_id = "context_test_user"

first = hermes.process_request(
    message="Compare Nvidia, Intel and AMD",
    source=source,
    channel_id=channel_id,
    user_id=user_id,
)

key = hermes.conversation_context.make_key(
    source=source,
    channel_id=channel_id,
    user_id=user_id,
)
state = hermes.conversation_context.get(key)

print("FIRST STATUS:", first.get("status"))
print("ACTIVE ENTITIES:", state.get("active_entities"))
print("LAST INTENT:", state.get("last_intent"))
print("RECENT MESSAGE COUNT:", len(state.get("recent_messages", [])))

assert {e.get("ticker") for e in state.get("active_entities", [])} >= {"NVDA", "INTC", "AMD"}
assert state.get("last_intent") == "company_comparison"

print("FOLLOW-UP CONTEXT STORAGE TEST PASSED")
