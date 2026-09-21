import sys
from pathlib import Path
from datetime import (
    datetime,
    timezone,
    timedelta
)
from email.utils import (
    format_datetime
)


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


from data.providers.rss_news_provider import (
    RSSNewsProvider
)


provider = RSSNewsProvider()


now = datetime.now(
    timezone.utc
)


fresh_article = {
    "title":
        "NVIDIA Fresh Article",

    "published_at":
        format_datetime(
            now
            - timedelta(
                days=1
            )
        ),

    "source":
        "TEST_SOURCE",

    "summary":
        "Current NVIDIA test article.",

    "url":
        "https://example.com/fresh",

    "source_type":
        "news"
}


stale_article = {
    "title":
        "NVIDIA Old Article",

    "published_at":
        format_datetime(
            now
            - timedelta(
                days=30
            )
        ),

    "source":
        "TEST_SOURCE",

    "summary":
        "Older NVIDIA test article.",

    "url":
        "https://example.com/old",

    "source_type":
        "news"
}


print()
print("=" * 60)
print("NEWS FRESHNESS TEST")
print("=" * 60)


print(
    "Fresh article:",
    provider._is_fresh(
        fresh_article
    )
)


print(
    "Old article:",
    provider._is_fresh(
        stale_article
    )
)


print("=" * 60)