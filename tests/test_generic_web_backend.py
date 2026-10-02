import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from data.providers.live.public_web_backend import PublicWebBackend

backend = PublicWebBackend(max_results=5)

results = backend.search(
    company={},
    query="What is Yrefy and what does it do?",
)

print("RESULT COUNT:", len(results))
assert results, (
    "PublicWebBackend returned no results"
)
for item in results:
    print(item)

assert isinstance(results, list)
for item in results:
    assert item.get("title")
    assert item.get("url")
    assert item.get("source_type") == "public_web"

print("GENERIC WEB BACKEND TEST PASSED")
