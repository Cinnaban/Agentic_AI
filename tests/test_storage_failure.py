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


job_id = "failure-test-001"


storage.create_job_record(
    job_id=job_id,
    data={
        "message": "Analyze Nvidia",
        "source": "test"
    }
)


result = storage.fail_job(
    job_id=job_id,
    updates={
        "final_status": "failed",
        "failure_stage": "planning"
    }
)


print(
    "Failed job:",
    result
)