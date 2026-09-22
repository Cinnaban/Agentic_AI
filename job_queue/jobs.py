from dataclasses import dataclass
from typing import List


@dataclass
class Job:

    job_id: str
    source: str
    task_type: str
    companies: List[dict]

    priority: int = 100
    status: str = "queued"