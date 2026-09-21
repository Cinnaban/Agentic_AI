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

from configs.config import Config


storage = StorageManager()
job_id = "expiration-test-001"


storage.create_job_record(
    job_id=job_id,
    data={
        "message":
            "Archive expiration test",

        "source":
            "test"
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


archive_path = storage.archive_job(
    job_id
)


print(
    "Archive created:",
    archive_path
)
old_archive_time = (
    time.time()
    - (
        60
        * 60
        * 24
        * (
            Config.ARCHIVE_RETENTION_DAYS
            + 1
        )
    )
)
os.utime(
    archive_path,
    (
        old_archive_time,
        old_archive_time
    )
)
temp_path = (
    storage.directories["temp"]
    / "expiration-temp-test.txt"
)


temp_path.write_text(
    "Temporary Hermes data",
    encoding="utf-8"
)
old_temp_time = (
    time.time()
    - (
        60
        * 60
        * 24
        * (
            Config.TEMP_RETENTION_DAYS
            + 1
        )
    )
)


os.utime(
    temp_path,
    (
        old_temp_time,
        old_temp_time
    )
)
print(
    "Archive exists before cleanup:",
    archive_path.exists()
)


print(
    "Temp exists before cleanup:",
    temp_path.exists()
)
cleanup_result = (
    storage.cleanup_old_jobs()
)


print(
    "Cleanup result:",
    cleanup_result
)
print(
    "Archive exists after cleanup:",
    archive_path.exists()
)


print(
    "Temp exists after cleanup:",
    temp_path.exists()
)