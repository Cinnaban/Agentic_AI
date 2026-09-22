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


from data.providers.live.firecrawl_backend import (
    FirecrawlBackend
)


backend = FirecrawlBackend()


url = (
    "https://example.com"
)


print()
print("=" * 60)
print("FIRECRAWL SCRAPE TEST")
print("=" * 60)


print(
    "Healthy:",
    backend.health_check()
)


result = backend.retrieve(
    url
)


print(
    "Result type:",
    type(
        result
    ).__name__
)


if isinstance(
    result,
    dict
):

    print(
        "Keys:",
        list(
            result.keys()
        )
    )

    print(
        "Title:",
        result.get(
            "title"
        )
    )

    print(
        "Markdown available:",
        bool(
            result.get(
                "markdown"
            )
        )
    )

    print(
        "Markdown preview:",
        (
            result.get(
                "markdown",
                ""
            )[:500]
        )
    )


assert backend.health_check()


assert isinstance(
    result,
    dict
)


assert result.get(
    "success"
) is True


assert result.get(
    "markdown"
)


print()
print(
    "FIRECRAWL SCRAPE TEST PASSED"
)

print("=" * 60)