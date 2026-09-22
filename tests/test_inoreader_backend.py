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


from data.providers.live.inoreader_backend import (
    InoreaderBackend
)


backend = InoreaderBackend()


print()
print("=" * 60)
print("INOREADER BACKEND TEST")
print("=" * 60)


print(
    "Configured:",
    backend.is_configured()
)


results = backend.search(
    company={
        "name": "NVIDIA",
        "ticker": "NVDA"
    },

    query=(
        "What's the latest with Nvidia?"
    )
)


print(
    "Results:",
    len(
        results
    )
)


for result in results[:5]:

    print()
    print(
        result
    )


print("=" * 60)