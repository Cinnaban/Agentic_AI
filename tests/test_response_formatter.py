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


from integrations.messaging.response_formatter import (
    ResponseFormatter
)


formatter = ResponseFormatter()


general_result = {
    "status": "completed",
    "response":
        "Compound interest allows "
        "interest to earn interest."
}


failed_result = {
    "status": "failed",
    "error":
        "Unable to process request."
}


general_message = formatter.format(
    general_result
)


failed_message = formatter.format(
    failed_result
)


print()
print("=" * 60)
print("RESPONSE FORMATTER TEST")
print("=" * 60)


print(
    "General:",
    general_message
)


print(
    "Failed:",
    failed_message
)


assert general_message

assert failed_message


print()
print(
    "RESPONSE FORMATTER TEST PASSED"
)

print("=" * 60)