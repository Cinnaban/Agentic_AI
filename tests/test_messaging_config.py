import os


telegram_token = os.getenv(
    "TELEGRAM_BOT_TOKEN"
)

discord_token = os.getenv(
    "DISCORD_BOT_TOKEN"
)


print()
print("=" * 60)
print("MESSAGING CONFIG TEST")
print("=" * 60)


print(
    "Telegram configured:",
    bool(
        telegram_token
    )
)

print(
    "Discord configured:",
    bool(
        discord_token
    )
)


assert telegram_token

assert discord_token


print()
print(
    "MESSAGING CONFIG TEST PASSED"
)

print("=" * 60)