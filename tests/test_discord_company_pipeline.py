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

from integrations.messaging.discord_adapter import (
    DiscordAdapter
)


hermes = Hermes()

router = MessageRouter(
    hermes
)

discord = DiscordAdapter(
    router
)


message = (
    discord.normalize(
        text="Analyze Nvidia",
        user_id="discord_test_user",
        channel_id="discord_test_chat",
        message_id="discord_company_1"
    )
)


result = discord.route(
    message
)


print()
print("=" * 60)
print("discord COMPANY PIPELINE TEST")
print("=" * 60)


print(
    "Source:",
    result.get(
        "source"
    )
)

print(
    "Status:",
    result.get(
        "status"
    )
)

print(
    "Approved:",
    result.get(
        "approved"
    )
)

print(
    "Confidence:",
    result.get(
        "confidence"
    )
)

print(
    "Job ID:",
    result.get(
        "job_id"
    )
)


assert result.get(
    "source"
) == "discord"


assert result.get(
    "status"
) == "completed"


assert result.get(
    "approved"
) is True


assert result.get(
    "job_id"
)


print()
print(
    "discord COMPANY PIPELINE TEST PASSED"
)

print("=" * 60)