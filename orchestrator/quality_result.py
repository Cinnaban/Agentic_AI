from dataclasses import dataclass

@dataclass
class QualityResult:

    approved: bool

    confidence: int

    issues: list