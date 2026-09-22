import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))


questions_channel_id = os.getenv(
    "DISCORD_QUESTIONS_CHANNEL_ID"
)

updates_channel_id = os.getenv(
    "DISCORD_UPDATES_CHANNEL_ID"
)


print()
print("=" * 60)
print("DISCORD CHANNEL CONFIG TEST")
print("=" * 60)


print(
    "Questions channel configured:",
    bool(
        questions_channel_id
    )
)

print(
    "Updates channel configured:",
    bool(
        updates_channel_id
    )
)


assert questions_channel_id

assert updates_channel_id


print()
print(
    "DISCORD CHANNEL CONFIG TEST PASSED"
)

print("=" * 60)