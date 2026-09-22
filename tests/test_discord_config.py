import os


token = os.getenv(
    "DISCORD_BOT_TOKEN"
)


print()
print("=" * 60)
print("DISCORD CONFIG TEST")
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
    "DISCORD CONFIG TEST PASSED"
)

print("=" * 60)