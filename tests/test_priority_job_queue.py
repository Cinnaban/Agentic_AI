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


from job_queue.job_factory import (
    JobFactory
)

from job_queue.priority_job_queue import (
    PriorityJobQueue
)


print()
print("=" * 60)
print("PRIORITY JOB QUEUE TEST")
print("=" * 60)


factory = JobFactory()
queue = PriorityJobQueue()


# ---------------------------------------------------------
# Create jobs
# ---------------------------------------------------------

discord_job_1 = factory.create_work_package(
    companies=[
        {
            "name": "NVIDIA",
            "ticker": "NVDA"
        }
    ],
    required_agents={},
    original_message="Discord question 1",
    source="discord",
    priority=10
)


discord_job_2 = factory.create_work_package(
    companies=[
        {
            "name": "Microsoft",
            "ticker": "MSFT"
        }
    ],
    required_agents={},
    original_message="Discord question 2",
    source="discord",
    priority=10
)


telegram_job_1 = factory.create_work_package(
    companies=[
        {
            "name": "NVIDIA",
            "ticker": "NVDA"
        }
    ],
    required_agents={},
    original_message="Telegram question 1",
    source="telegram",
    priority=0
)


telegram_job_2 = factory.create_work_package(
    companies=[
        {
            "name": "Microsoft",
            "ticker": "MSFT"
        }
    ],
    required_agents={},
    original_message="Telegram question 2",
    source="telegram",
    priority=0
)


# ---------------------------------------------------------
# TEST 1
# Telegram should beat Discord while jobs are waiting.
# ---------------------------------------------------------

queue.put(
    discord_job_1
)

queue.put(
    telegram_job_1
)


first = queue.get()
second = queue.get()


assert (
    first.source
    == "telegram"
)

assert (
    second.source
    == "discord"
)


print(
    "Priority ordering: PASSED"
)


# ---------------------------------------------------------
# TEST 2
# Telegram jobs should retain FIFO ordering.
# ---------------------------------------------------------

queue.put(
    telegram_job_1
)

queue.put(
    telegram_job_2
)


first = queue.get()
second = queue.get()


assert (
    first.original_message
    == "Telegram question 1"
)

assert (
    second.original_message
    == "Telegram question 2"
)


print(
    "FIFO ordering: PASSED"
)


# ---------------------------------------------------------
# TEST 3
# Active Discord processing must NOT be preempted.
# ---------------------------------------------------------

queue.put(
    discord_job_1
)


active_job = queue.get()


assert (
    active_job.source
    == "discord"
)


print(
    "Active:",
    active_job.original_message
)


# Telegram arrives while Discord is already active.

queue.put(
    telegram_job_1
)

queue.put(
    discord_job_2
)


# active_job remains Discord.
assert (
    active_job.original_message
    == "Discord question 1"
)


# Simulate Discord completing.
active_job.status = "completed"


# Now select the next waiting job.

next_job = queue.get()


assert (
    next_job.source
    == "telegram"
)


assert (
    next_job.original_message
    == "Telegram question 1"
)


final_job = queue.get()


assert (
    final_job.source
    == "discord"
)


assert (
    final_job.original_message
    == "Discord question 2"
)


print(
    "Non-preemptive processing: PASSED"
)


# ---------------------------------------------------------
# TEST 4
# Queue should now be empty.
# ---------------------------------------------------------

assert queue.empty()


print(
    "Queue empty: PASSED"
)


print()
print(
    "PRIORITY JOB QUEUE TEST PASSED"
)

print("=" * 60)