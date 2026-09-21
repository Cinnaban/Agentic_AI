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


candidate_feed = {
    "source":
        "CANDIDATE_SOURCE",

    "url":
        "PASTE_VERIFIED_RSS_URL_HERE",

    "source_type":
        "news"
}


result = provider.test_feed(
    candidate_feed
)


print()
print("=" * 60)
print("CANDIDATE NEWS FEED TEST")
print("=" * 60)


print(
    "Configured:",
    result.get(
        "configured"
    )
)


print(
    "Reachable:",
    result.get(
        "reachable"
    )
)


print(
    "Articles found:",
    result.get(
        "articles_found"
    )
)


print("=" * 60)