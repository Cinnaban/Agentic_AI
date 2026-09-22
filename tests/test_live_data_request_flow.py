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

from orchestrator.freshness_detector import (
    FreshnessDetector
)


hermes = Hermes()

detector = FreshnessDetector()


normal_message = (
    "Analyze Nvidia"
)

live_message = (
    "What's the latest with Nvidia?"
)


normal_requires_live = (
    detector.requires_live_data(
        normal_message
    )
)


live_requires_live = (
    detector.requires_live_data(
        live_message
    )
)


print()
print("=" * 60)
print("LIVE DATA REQUEST FLOW TEST")
print("=" * 60)


print(
    "Normal request requires live data:",
    normal_requires_live
)


print(
    "Current request requires live data:",
    live_requires_live
)


assert (
    normal_requires_live
    is False
)


assert (
    live_requires_live
    is True
)


live_work_package = (
    hermes.build_workflow(
        live_message
    )
)


print(
    "Company:",
    live_work_package.companies[
        0
    ]
)


print(
    "Original message:",
    live_work_package.original_message
)


assert (
    live_work_package.original_message
    == live_message
)


print()
print(
    "LIVE DATA REQUEST FLOW TEST PASSED"
)

print("=" * 60)