from dataclasses import dataclass


@dataclass
class WorkPackage:

    job_id: str

    companies: list

    required_agents: dict

    original_message: str

    source: str

    status: str = "queued"
