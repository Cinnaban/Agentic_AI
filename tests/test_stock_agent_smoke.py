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


from orchestrator.hermes import Hermes


hermes = Hermes()


message = "Analyze Nvidia"


print()
print("=" * 60)
print("HERMES PROCESS REQUEST TEST")
print("=" * 60)

print(
    "Message:",
    message
)


result = hermes.process_request(
    message=message,
    source="test"
)

print()
print("=" * 60)
print("STOCK AGENT SMOKE TEST")
print("=" * 60)


assert isinstance(
    result,
    dict
)


assert result.get(
    "status"
) == "completed"


assert result.get(
    "approved"
) is True


assert result.get(
    "job_id"
)


print(
    "Status:",
    result.get(
        "status"
    )
)

print(
    "Approved:",
    result.get(
        "approved"
    )
)

print(
    "Confidence:",
    result.get(
        "confidence"
    )
)

print(
    "Job ID:",
    result.get(
        "job_id"
    )
)


print()
print("SMOKE TEST PASSED")
print("=" * 60)