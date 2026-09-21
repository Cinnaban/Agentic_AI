from dataclasses import dataclass, asdict
from typing import List, Dict, Any


@dataclass
class ComputeRequest:

    job_id: str
    companies: List[Dict[str, Any]]
    original_message: str
    requested_tasks: List[str]
    source: str

    def to_dict(self):
        return asdict(self)