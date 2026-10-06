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

    "research":
        "Research content",

    "challenger": {

        "status":
            "completed",

        "agreement":
            "partial",

        "summary":
            "The thesis is reasonable but "
            "there are competitive risks."
    }
}

section = (
    hermes._build_challenger_section(
        execution_results
    )
)

print(section)

assert (
    "Independent Review"
    in section
)

assert (
    "Agreement: partial"
    in section
)

assert (
    "competitive risks"
    in section
)

print(
    "CHALLENGER SECTION TEST PASSED"
)