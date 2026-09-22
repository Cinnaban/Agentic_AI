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


from integrations.messaging.message_router import (
    MessageRouter
)

from job_queue.job_factory import (
    JobFactory
)

from job_queue.priority_job_queue import (
    PriorityJobQueue
)

from job_queue.queue_coordinator import (
    QueueCoordinator
)


class MockHermes:

    pass


router = MessageRouter(
    MockHermes()
)

factory = JobFactory()

queue = PriorityJobQueue()


coordinator = QueueCoordinator(
    router=router,
    job_factory=factory,
    job_queue=queue
)


print()
print("=" * 60)
print("QUEUE COORDINATOR TEST")
print("=" * 60)


# ---------------------------------------------------------
# Submit Discord first.
# ---------------------------------------------------------

discord_job = coordinator.submit(
    source="discord",
    original_message="Analyze Microsoft",
    companies=[
        {
            "name": "Microsoft",
            "ticker": "MSFT"
        }
    ]
)


assert (
    discord_job.source
    == "discord"
)

assert (
    discord_job.priority
    == 10
)


print(
    "Discord priority assignment: PASSED"
)


# ---------------------------------------------------------
# Submit Telegram second.
# ---------------------------------------------------------

telegram_job = coordinator.submit(
    source="telegram",
    original_message="Analyze NVIDIA",
    companies=[
        {
            "name": "NVIDIA",
            "ticker": "NVDA"
        }
    ]
)


assert (
    telegram_job.source
    == "telegram"
)

assert (
    telegram_job.priority
    == 0
)


print(
    "Telegram priority assignment: PASSED"
)


# ---------------------------------------------------------
# There should be two waiting jobs.
# ---------------------------------------------------------

assert (
    coordinator.queue_size()
    == 2
)


print(
    "Queue submission: PASSED"
)


# ---------------------------------------------------------
# Telegram should be selected first despite arriving second.
# ---------------------------------------------------------

first = coordinator.get_next()


assert (
    first.source
    == "telegram"
)

assert (
    first.original_message
    == "Analyze NVIDIA"
)


print(
    "Telegram-first routing: PASSED"
)


# ---------------------------------------------------------
# Discord should remain.
# ---------------------------------------------------------

second = coordinator.get_next()


assert (
    second.source
    == "discord"
)

assert (
    second.original_message
    == "Analyze Microsoft"
)


print(
    "Discord fallback routing: PASSED"
)


assert (
    not coordinator.has_work()
)


print(
    "Queue completion: PASSED"
)


print()
print(
    "QUEUE COORDINATOR TEST PASSED"
)

print("=" * 60)