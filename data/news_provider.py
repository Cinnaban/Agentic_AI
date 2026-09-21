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

from data.news_feeds import (
    NEWS_FEEDS
)

class NewsProvider:

    def __init__(
        self
    ):

        self.rss_provider = (
            RSSNewsProvider()
        )

    def get_news(
        self,
        company
    ):

        news = (
            self.rss_provider.get_news(
                company=company,
                feeds=NEWS_FEEDS
            )
        )

        return news