# job_queue/jobs.py

from dataclasses import dataclass
from typing import List


@dataclass
class Job:

    job_id: str

    source: str

    task_type: str

    companies: List[dict]

    priority: str = "normal"

    status: str = "queued"