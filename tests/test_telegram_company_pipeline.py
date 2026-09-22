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


hermes = Hermes()

router = MessageRouter(
    hermes
)

telegram = TelegramAdapter(
    router
)


message = (
    telegram.normalize(
        text="Analyze Nvidia",
        user_id="telegram_test_user",
        channel_id="telegram_test_chat",
        message_id="telegram_company_1"
    )
)


result = telegram.route(
    message
)


print()
print("=" * 60)
print("TELEGRAM COMPANY PIPELINE TEST")
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
) == "telegram"


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
    "TELEGRAM COMPANY PIPELINE TEST PASSED"
)

print("=" * 60)