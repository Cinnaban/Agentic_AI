import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from orchestrator.hermes import Hermes
from integrations.messaging.message_router import MessageRouter
from integrations.messaging.discord_adapter import DiscordAdapter
from integrations.messaging.response_formatter import ResponseFormatter

hermes = Hermes()
router = MessageRouter(hermes)
adapter = DiscordAdapter(router)
formatter = ResponseFormatter()

queries = [
    "What is the Steam Deck",
    "Tell me about Nvidia",
    "Tell me the latest about INTC",
]

for query in queries:
    print("\n" + "=" * 70)
    print("QUERY:", query)
    normalized = adapter.normalize(
        text=query,
        user_id="trace_user",
        channel_id="trace_channel",
        message_id="trace_message",
    )
    print("NORMALIZED:", normalized)
    result = adapter.route(normalized)
    print("RESULT:", result)
    print("FORMATTED:", formatter.format(result))

