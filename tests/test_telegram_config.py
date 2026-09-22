import os


token = os.getenv(
    "TELEGRAM_BOT_TOKEN"
)


print()
print("=" * 60)
print("TELEGRAM CONFIG TEST")
print("=" * 60)


configured = bool(
    token
)


print(
    "Configured:",
    configured
)


assert configured


print()
print(
    "TELEGRAM CONFIG TEST PASSED"
)

print("=" * 60)
