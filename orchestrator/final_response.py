from dataclasses import dataclass


@dataclass
class FinalResponse:

    approved: bool

    confidence: int

    summary: str

    results: dict