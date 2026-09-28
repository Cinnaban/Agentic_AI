import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from memory.conversation_context import ConversationContext

context = ConversationContext()
key = context.make_key(
    source="telegram",
    channel_id="trace_chat",
    user_id="trace_user",
)

context.set_active_entities(
    key,
    [
        {"name": "NVIDIA", "ticker": "NVDA"},
        {"name": "Intel", "ticker": "INTC"},
        {"name": "AMD", "ticker": "AMD"},
    ],
    intent="company_comparison",
    request="Compare Nvidia, Intel and AMD",
)

state = context.get(key)
print("Key:", key)
print("State:", state)

assert [item["ticker"] for item in state["active_entities"]] == ["NVDA", "INTC", "AMD"]
assert state["last_intent"] == "company_comparison"
assert state["last_request"] == "Compare Nvidia, Intel and AMD"

context.add_message(key, "user", "Which has the strongest balance sheet?")
state = context.get(key)
assert state["recent_messages"][-1]["content"] == "Which has the strongest balance sheet?"

print("CONVERSATION CONTEXT TEST PASSED")
