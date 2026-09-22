import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from data.providers.live.public_topic_news_backend import PublicTopicNewsBackend

backend = PublicTopicNewsBackend()
queries = [
    "Pokemon latest news",
    "Data Science latest news",
    "AMD GPU latest news",
    "Magic the Gathering latest news",
]

print()
print("=" * 60)
print("PUBLIC TOPIC LIVE NEWS TEST")
print("=" * 60)

for query in queries:
    results = backend.search(company=None, query=query)
    print()
    print("Query:", query)
    print("Results:", len(results))
    for result in results[:3]:
        print(" -", result.get("published_at"), result.get("source"), result.get("title"))
    assert isinstance(results, list)

print()
print("PUBLIC TOPIC LIVE NEWS TEST PASSED")
print("=" * 60)
