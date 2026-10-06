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


from orchestrator.hermes import (
    Hermes
)

hermes = Hermes.__new__(
    Hermes
)

execution_results = {

    "market_context": {

        "source_status": {

            "financial_data":
                "available",

            "sec_facts":
                "available",

            "sec_filings":
                "available",

            "macro":
                "available",

            "news":
                "unavailable",

            "live_market_context":
                "available",

            "social":
                "available"
        }
    }
}

section = (
    hermes._build_evidence_section(
        execution_results
    )
)

print(section)

assert (
    "Evidence Availability"
    in section
)

assert (
    "financial_data: available"
    in section
)

assert (
    "social: available"
    in section
)

print(
    "EVIDENCE SECTION TEST PASSED"
)