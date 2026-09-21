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


from data.news_feeds import (
    NEWS_FEEDS
)

from data.providers.rss_news_provider import (
    RSSNewsProvider
)


provider = RSSNewsProvider()


print()
print("=" * 60)
print("NEWS FEED HEALTH TEST")
print("=" * 60)


if not NEWS_FEEDS:

    print(
        "No production feeds configured."
    )


for feed in NEWS_FEEDS:

    result = provider.test_feed(
        feed
    )

    print()

    print(
        "Source:",
        feed.get(
            "source"
        )
    )

    print(
        result
    )


print("=" * 60)