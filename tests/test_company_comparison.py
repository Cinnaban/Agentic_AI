import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))
    
from orchestrator.hermes import (
    Hermes
)


hermes = Hermes()


result = hermes.process_request(
    message=(
        "Compare Nvidia, Intel and AMD"
    ),
    source="comparison_test"
)


print(
    "STATUS:",
    result.get(
        "status"
    )
)


print(
    "RESPONSE:",
    result.get(
        "response"
    )
)


assert (
    result.get(
        "status"
    )
    == "completed"
)


assert result.get(
    "response"
)


print(
    "COMPANY COMPARISON TEST PASSED"
)