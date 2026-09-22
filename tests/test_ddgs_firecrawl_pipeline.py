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


from data.providers.live.public_topic_news_backend import (
    PublicTopicNewsBackend
)

from data.providers.live.firecrawl_backend import (
    FirecrawlBackend
)


news_backend = (
    PublicTopicNewsBackend(
        max_results=5
    )
)


firecrawl = (
    FirecrawlBackend()
)


query = (
    "Pokemon latest news"
)


print()
print("=" * 60)
print("DDGS + FIRECRAWL PIPELINE TEST")
print("=" * 60)


results = news_backend.search(
    company=None,
    query=query
)


print(
    "DDGS results:",
    len(
        results
    )
)


assert results


scraped = None

selected_result = None


for result in results:

    url = result.get(
        "url"
    )

    if not url:

        continue


    print()
    print(
        "Trying:",
        url
    )


    scraped = firecrawl.retrieve(
        url
    )


    if scraped:

        selected_result = (
            result
        )

        break


print()
print(
    "Firecrawl success:",
    bool(
        scraped
    )
)


assert scraped

assert scraped.get(
    "markdown"
)


print(
    "News title:",
    selected_result.get(
        "title"
    )
)


print(
    "News source:",
    selected_result.get(
        "source"
    )
)


print(
    "Firecrawl title:",
    scraped.get(
        "title"
    )
)


print(
    "Content length:",
    len(
        scraped.get(
            "markdown",
            ""
        )
    )
)


print()
print(
    "CONTENT PREVIEW"
)

print("-" * 60)


print(
    scraped.get(
        "markdown",
        ""
    )[:1000]
)


print("-" * 60)


print()
print(
    "DDGS + FIRECRAWL PIPELINE TEST PASSED"
)

print("=" * 60)