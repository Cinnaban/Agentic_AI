import os


required = [
    "DISCORD_BOT_TOKEN",
    "DISCORD_UPDATES_CHANNEL_ID",
    "GOOGLE_CREDENTIALS_FILE",
    "GOOGLE_SHEET_NAME",
    "GOOGLE_ASSET_TAB"
]


print()
print("=" * 60)
print("ETF UPDATE CONFIG TEST")
print("=" * 60)


for name in required:

    configured = bool(
        os.getenv(
            name
        )
    )

    print(
        f"{name}:",
        configured
    )

    assert configured, (
        f"Missing {name}"
    )


print()
print(
    "ETF UPDATE CONFIG TEST PASSED"
)

print("=" * 60)