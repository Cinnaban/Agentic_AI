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


rss_content = b"""
<rss version="2.0">
    <channel>

        <title>Hermes Test Feed</title>

        <item>
            <title>
                NVIDIA Test Article
            </title>

            <link>
                https://example.com/nvidia-test
            </link>

            <description>
                Test article for RSS normalization.
            </description>

            <pubDate>
                Mon, 21 Sep 2026 12:00:00 GMT
            </pubDate>
        </item>

        <item>
            <title>
                Second Test Article
            </title>

            <link>
                https://example.com/second-test
            </link>

            <description>
                Second RSS test article.
            </description>

            <pubDate>
                Mon, 21 Sep 2026 13:00:00 GMT
            </pubDate>
        </item>

        <item>
            <title>
                Unrelated Company Test Article
            </title>

            <link>
                https://example.com/unrelated-test
            </link>

            <description>
                Article about an unrelated business.
            </description>

            <pubDate>
                Mon, 21 Sep 2026 14:00:00 GMT
            </pubDate>
        </item>

    </channel>
</rss>
"""
company = {
    "name": "NVIDIA",
    "ticker": "NVDA"
}

articles = provider._parse_feed(
    rss_content,
    "TEST_SOURCE"
)

relevant_articles = [
    article
    for article
    in articles
    if provider._is_relevant(
        article,
        company
    )
]

print()
print("=" * 60)
print("RSS PARSER TEST")
print("=" * 60)


print(
    "Articles:",
    len(
        articles
    )
)
print(
    "Relevant articles:",
    len(
        relevant_articles
    )
)

for article in articles:

    print()
    print(article)


print("=" * 60)