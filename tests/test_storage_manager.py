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


job_id = "storage-test-001"


path = storage.create_job_record(
    job_id=job_id,
    data={
        "message":
            "Analyze Nvidia",

        "source":
            "test"
    }
)


print(
    "Created:",
    path
)


path = storage.move_job(
    job_id=job_id,
    from_status="incoming",
    to_status="processing",
    
)

path = storage.update_job_record(
    job_id=job_id,
    status="processing",
    updates={
        "companies": [
            {
                "name": "NVIDIA",
                "ticker": "NVDA"
            }
        ],
        "required_agents": {
            "research": True,
            "sentiment": True,
            "quant": True,
            "risk": False
        }
    }
)
print(
    "Processing:",
    path
)


path = storage.move_job(
    job_id=job_id,
    from_status="processing",
    to_status="completed"
)


print(
    "Completed:",
    path
)