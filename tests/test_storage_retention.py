import sys
import os
import time

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

job_id = "retention-test-001"


storage.create_job_record(
    job_id=job_id,
    data={
        "message": "Retention test",
        "source": "test"
    }
)


storage.move_job(
    job_id=job_id,
    from_status="incoming",
    to_status="processing"
)


completed_path = storage.move_job(
    job_id=job_id,
    from_status="processing",
    to_status="completed"
)

old_time = time.time() - (
    60 * 60 * 24 * 31
)

os.utime(
    completed_path,
    (
        old_time,
        old_time
    )
)

print(
    "Old completed job:",
    storage.is_older_than(
        completed_path,
        30
    )
)

result = storage.cleanup_old_jobs()


print(
    "Cleanup result:",
    result
)

job = storage.find_job(
    job_id
)


print(
    "Job after cleanup:",
    job
)