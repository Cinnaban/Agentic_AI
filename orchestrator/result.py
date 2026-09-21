from dataclasses import dataclass


@dataclass
class AnalysisResult:

    job_id: str

    status: str

    payload: dict