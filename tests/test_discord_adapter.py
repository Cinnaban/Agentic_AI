import sys
from pathlib import Path


ROOT_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

if str(ROOT_DIR) not in sys.path:
    sys.path.append(
        str(ROOT_DIR)
    )


from integrations.messaging.message_router import (
    MessageRouter
)

from integrations.messaging.discord_adapter import (
    DiscordAdapter
)


class MockHermes:

    pass


router = MessageRouter(
    MockHermes()
)

adapter = DiscordAdapter(
    router
)


print()
print("=" * 60)
print("DISCORD ADAPTER TEST")
print("=" * 60)


message = adapter.normalize(
    text="Analyze NVIDIA",
    user_id="user-123",
    channel_id="channel-456",
    message_id="message-789"
)


print(
    "Normalized:",
    message
)


assert (
    message["source"]
    == "discord"
)

assert (
    message["text"]
    == "Analyze NVIDIA"
)

assert (
    message["user_id"]
    == "user-123"
)

assert (
    message["channel_id"]
    == "channel-456"
)

assert (
    message["message_id"]
    == "message-789"
)

assert adapter.validate(
    message
)

assert (
    adapter.get_priority()
    == 10
)


print()
print(
    "DISCORD ADAPTER TEST PASSED"
)

print("=" * 60)