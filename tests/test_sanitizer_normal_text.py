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


from security.sanitizer import (
    SecuritySanitizer
)


sanitizer = SecuritySanitizer()


tests = [
    "completed",
    "failed",
    "Hello world",
    "Compound interest is simple.",
    "This is a normal response.",
    "NVIDIA",
    "95",
    "192.168.50.1",
    r"D:\Agentic_AI\data.json",
    "/Users/example/Agentic_AI/data.json"
]


for value in tests:

    result = sanitizer.sanitize(
        value
    )

    print(
        repr(value),
        "->",
        repr(result)
    )