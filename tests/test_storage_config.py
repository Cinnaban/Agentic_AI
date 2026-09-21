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


from configs.config import Config


print(
    "Storage root:",
    Config.SHARED_STORAGE_DIRECTORY
)

print(
    "Incoming:",
    Config.JOB_INCOMING_DIRECTORY
)

print(
    "Processing:",
    Config.JOB_PROCESSING_DIRECTORY
)

print(
    "Completed:",
    Config.JOB_COMPLETED_DIRECTORY
)