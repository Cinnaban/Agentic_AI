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

job_id = "archive-test-001"


storage.create_job_record(
    job_id=job_id,
    data={
        "message": "Analyze Nvidia",
        "source": "test"
    }
)


storage.move_job(
    job_id=job_id,
    from_status="incoming",
    to_status="processing"
)


storage.move_job(
    job_id=job_id,
    from_status="processing",
    to_status="completed"
)


result = storage.archive_job(
    job_id
)


print(
    "Archived:",
    result
)