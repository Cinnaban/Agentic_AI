import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from orchestrator.hermes import Hermes
from integrations.messaging.message_router import MessageRouter
from integrations.messaging.telegram_adapter import TelegramAdapter
from integrations.messaging.discord_adapter import DiscordAdapter
from integrations.messaging.response_formatter import ResponseFormatter

hermes = Hermes()
router = MessageRouter(hermes)
formatter = ResponseFormatter()

for adapter_name, adapter, kwargs in [
    ("telegram", TelegramAdapter(router), {"user_id": "trace_user", "channel_id": "trace_chat", "message_id": "trace_message"}),
    ("discord", DiscordAdapter(router), {"user_id": "trace_user", "channel_id": "trace_channel", "message_id": "trace_message"}),
]:
    print("\n" + "=" * 70)
    print("ADAPTER:", adapter_name)
    normalized = adapter.normalize(text="AMZN", **kwargs)
    print("NORMALIZED:", normalized)
    result = adapter.route(normalized)
    print("STATUS:", result.get("status"))
    print("APPROVED:", result.get("approved"))
    print("CONFIDENCE:", result.get("confidence"))
    print("HAS RESPONSE:", bool(result.get("response")))
    print("QUALITY:", result.get("results", {}).get("quality_review") if isinstance(result.get("results"), dict) else None)
    print("FORMATTED PREVIEW:", formatter.format(result)[:1000])
