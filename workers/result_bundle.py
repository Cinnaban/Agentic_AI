from dataclasses import dataclass


@dataclass
class ResultBundle:

    job_id: str

    companies: list

    results: dict

    status: str
