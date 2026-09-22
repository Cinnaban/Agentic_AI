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


from orchestrator.hermes import (
    Hermes
)

from integrations.messaging.message_router import (
    MessageRouter
)

from integrations.messaging.telegram_adapter import (
    TelegramAdapter
)

from integrations.messaging.discord_adapter import (
    DiscordAdapter
)

from integrations.messaging.response_formatter import (
    ResponseFormatter
)


hermes = Hermes()

router = MessageRouter(
    hermes
)

telegram = TelegramAdapter(
    router
)

discord = DiscordAdapter(
    router
)

formatter = ResponseFormatter()

telegram_message = (
    telegram.normalize(
        text=(
            "Explain compound interest"
        ),
        user_id="test_user",
        channel_id="test_chat",
        message_id="telegram_1"
    )
)


telegram_result = (
    telegram.route(
        telegram_message
    )
)


telegram_response = (
    formatter.format(
        telegram_result
    )
)

discord_message = (
    discord.normalize(
        text=(
            "Explain compound interest "
            "in simple terms."
        ),
        user_id="discord_test_user",
        channel_id="discord_test_channel",
        message_id="discord_general_1"
    )
)


discord_result = (
    discord.route(
        discord_message
    )
)

discord_response = (
    formatter.format(
        discord_result
    )
)

print()
print("=" * 60)
print("GENERAL MESSAGING PIPELINE TEST")
print("=" * 60)


print(
    "Telegram priority:",
    telegram.get_priority()
)

print(
    "Telegram status:",
    telegram_result.get(
        "status"
    )
)

print(
    "Telegram response:",
    telegram_response
)


print()

print(
    "Discord priority:",
    discord.get_priority()
)

print(
    "Discord status:",
    discord_result.get(
        "status"
    )
)

print(
    "Discord response:",
    discord_response
)

assert (
    telegram_result.get(
        "status"
    )
    == "completed"
)


assert (
    discord_result.get(
        "status"
    )
    == "completed"
)


assert telegram_response

assert discord_response


assert (
    telegram.get_priority()
    <
    discord.get_priority()
)


print()
print(
    "GENERAL MESSAGING PIPELINE TEST PASSED"
)

print("=" * 60)