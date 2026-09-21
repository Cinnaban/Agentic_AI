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
message = (
    "Explain compound interest in simple terms."
)
result = hermes.process_request(
    message=message,
    source="test"
)
print()
print("=" * 60)
print("GENERAL REQUEST TEST")
print("=" * 60)

print(
    "Status:",
    result.get("status")
)

print()

print(
    "Response:"
)

print(
    result.get("response")
)

print("=" * 60)