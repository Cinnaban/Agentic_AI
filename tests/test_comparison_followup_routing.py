import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from orchestrator.hermes import Hermes

hermes = Hermes()
source = "telegram"
channel_id = "comparison_chat"
user_id = "comparison_user"

first_message = "Compare Nvidia, Intel and AMD"
followup_message = "Which has the strongest balance sheet?"

print("=" * 70)
print("COMPARISON FOLLOW-UP ROUTING TEST")
print("=" * 70)

first = hermes.process_request(
    message=first_message,
    source=source,
    channel_id=channel_id,
    user_id=user_id,
)
print("FIRST STATUS:", first.get("status"))

key = hermes.conversation_context.make_key(
    source=source,
    channel_id=channel_id,
    user_id=user_id,
)
state = hermes.conversation_context.get(key)
print("ACTIVE ENTITIES:", state.get("active_entities"))
print("LAST INTENT:", state.get("last_intent"))

resolver = hermes.followup_resolver.resolve(
    message=followup_message,
    context=state,
)
print("FOLLOW-UP RESOLUTION:", resolver)

assert resolver is not None
assert resolver.get("is_followup") is True
assert {e.get("ticker") for e in resolver.get("entities", [])} >= {"NVDA", "INTC", "AMD"}

print("COMPARISON FOLLOW-UP ROUTING TEST PASSED")
