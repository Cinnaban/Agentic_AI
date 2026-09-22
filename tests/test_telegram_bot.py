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


from integrations.messaging.telegram_bot import (
    TelegramBot
)


print()
print("=" * 60)
print("TELEGRAM BOT TEST")
print("=" * 60)


bot = TelegramBot()


print(
    "TelegramBot created:",
    isinstance(
        bot,
        TelegramBot
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


print(
    "Formatter configured:",
    bot.formatter is not None
)


assert bot.token

assert bot.router

assert bot.adapter

assert bot.formatter


print()
print(
    "TELEGRAM BOT TEST PASSED"
)

print("=" * 60)