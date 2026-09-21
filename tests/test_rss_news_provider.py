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


from data.providers.rss_news_provider import (
    RSSNewsProvider
)


provider = RSSNewsProvider()


company = {
    "name": "NVIDIA",
    "ticker": "NVDA"
}


feeds = [
    {
        "source":
            "TEST_SOURCE",

        "url":
            "REPLACE_WITH_PUBLIC_RSS_URL"
    }
]


articles = provider.get_news(
    company=company,
    feeds=feeds
)


print()
print("=" * 60)
print("RSS NEWS PROVIDER TEST")
print("=" * 60)


print(
    "Articles:",
    len(
        articles
    )
)


for article in articles[:5]:

    print()

    print(
        "Title:",
        article.get(
            "title"
        )
    )

    print(
        "Published:",
        article.get(
            "published_at"
        )
    )

    print(
        "Source:",
        article.get(
            "source"
        )
    )

    print(
        "URL:",
        article.get(
            "url"
        )
    )


print("=" * 60)