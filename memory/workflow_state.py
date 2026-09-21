from enum import Enum
from datetime import datetime


class WorkflowStatus(str, Enum):

    CREATED = "created"
    PLANNING = "planning"
    EXECUTING = "executing"
    WAITING_FOR_COMPUTE = "waiting_for_compute"
    EVALUATING = "evaluating"
    QUALITY_REVIEW = "quality_review"
    SANITIZING = "sanitizing"

    COMPLETED = "completed"

    PARTIAL = "partial"
    FAILED = "failed"
    COMPUTE_UNAVAILABLE = "compute_unavailable"
    QUALITY_REJECTED = "quality_rejected"


class WorkflowState:

    def __init__(self):

        self.active_jobs = {}

    def register_job(
        self,
        job_id,
        original_message
    ):

        self.active_jobs[job_id] = {
            "job_id": job_id,
            "original_message": original_message,
            "status": WorkflowStatus.CREATED.value,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "error": None
        }

        return self.active_jobs[job_id]

    def update_status(
        self,
        job_id,
        status
    ):

        job = self.active_jobs.get(
            job_id
        )

        if job is None:
            return None

        if isinstance(
            status,
            WorkflowStatus
        ):
            status = status.value

        job["status"] = status

        job["updated_at"] = (
            datetime.now().isoformat()
        )

        return job

    def set_error(
        self,
        job_id,
        error
    ):

        job = self.active_jobs.get(
            job_id
        )

        if job is None:
            return None

        job["status"] = (
            WorkflowStatus.FAILED.value
        )

        job["error"] = str(error)

        job["updated_at"] = (
            datetime.now().isoformat()
        )

        return job

    def get_job(
        self,
        job_id
    ):

        return self.active_jobs.get(
            job_id
        )