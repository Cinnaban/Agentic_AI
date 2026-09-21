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


from data.news_provider import (
    NewsProvider
)

provider = NewsProvider()


company = {
    "name": "NVIDIA",
    "ticker": "NVDA"
}

news = provider.get_news(
    company
)


print()
print("=" * 60)
print("NEWS PROVIDER TEST")
print("=" * 60)

print(
    "News count:",
    len(news)
)

print(
    "News:",
    news
)

print("=" * 60)