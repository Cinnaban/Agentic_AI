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


router = MessageRouter(
    hermes=None
)


telegram_message = (
    router.normalize_message(
        source="telegram",
        text="Analyze Nvidia",
        user_id="telegram_user",
        channel_id="telegram_chat",
        message_id="1"
    )
)


discord_message = (
    router.normalize_message(
        source="discord",
        text="Explain compound interest",
        user_id="discord_user",
        channel_id="discord_channel",
        message_id="2"
    )
)


print()
print("=" * 60)
print("MESSAGE ROUTER TEST")
print("=" * 60)


print(
    "Telegram valid:",
    router.validate_message(
        telegram_message
    )
)


print(
    "Telegram priority:",
    router.get_priority(
        telegram_message[
            "source"
        ]
    )
)


print(
    "Discord valid:",
    router.validate_message(
        discord_message
    )
)


print(
    "Discord priority:",
    router.get_priority(
        discord_message[
            "source"
        ]
    )
)


assert router.validate_message(
    telegram_message
)


assert router.validate_message(
    discord_message
)


assert (
    router.get_priority(
        "telegram"
    )
    <
    router.get_priority(
        "discord"
    )
)


print()
print(
    "MESSAGE ROUTER TEST PASSED"
)

print("=" * 60)