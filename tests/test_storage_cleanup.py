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


from shared_storage.storage_manager import (
    StorageManager
)


storage = StorageManager()


result = storage.cleanup_old_jobs()


print(
    "Cleanup result:",
    result
)