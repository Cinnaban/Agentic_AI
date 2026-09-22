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


from orchestrator.freshness_detector import (
    FreshnessDetector
)


detector = FreshnessDetector()


tests = {
    "Analyze Nvidia":
        False,

    "What is Nvidia doing today?":
        True,

    "What's the latest with Nvidia?":
        True,

    "Give me recent Nvidia information":
        True,

    "Analyze Nvidia this week":
        True
}


print()
print("=" * 60)
print("FRESHNESS DETECTOR TEST")
print("=" * 60)


for message, expected in tests.items():

    result = detector.requires_live_data(
        message
    )

    print(
        message,
        "->",
        result
    )

    assert result == expected


print()
print(
    "FRESHNESS DETECTOR TEST PASSED"
)

print("=" * 60)