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


from integrations.messaging.discord_bot import (
    DiscordBot
)


print()
print("=" * 60)
print("DISCORD BOT TEST")
print("=" * 60)


bot = DiscordBot()


print(
    "Token configured:",
    bool(
        bot.token
    )
)


print(
    "Questions channel:",
    bool(
        bot.questions_channel_id
    )
)


print(
    "Router configured:",
    bot.router is not None
)


print(
    "Adapter configured:",
    bot.adapter is not None
)


assert bot.token

assert bot.questions_channel_id

assert bot.router

assert bot.adapter


print()
print(
    "DISCORD BOT TEST PASSED"
)

print("=" * 60)