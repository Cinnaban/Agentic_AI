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

from memory.workflow_state import (
    WorkflowState,
    WorkflowStatus
)


state = WorkflowState()


job = state.register_job(
    job_id="test-job-001",
    original_message="Analyze Nvidia"
)


print("CREATED:")
print(job)


state.update_status(
    "test-job-001",
    WorkflowStatus.PLANNING
)


print()
print("PLANNING:")
print(
    state.get_job(
        "test-job-001"
    )
)


state.update_status(
    "test-job-001",
    WorkflowStatus.EXECUTING
)


print()
print("EXECUTING:")
print(
    state.get_job(
        "test-job-001"
    )
)


state.update_status(
    "test-job-001",
    WorkflowStatus.COMPLETED
)


print()
print("COMPLETED:")
print(
    state.get_job(
        "test-job-001"
    )
)

state.register_job(
    job_id="test-job-002",
    original_message="Analyze Microsoft"
)


state.set_error(
    "test-job-002",
    "Gaming PC unavailable"
)


print()
print("FAILED JOB:")
print(
    state.get_job(
        "test-job-002"
    )
)