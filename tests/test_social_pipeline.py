import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from data.providers.social.reddit_provider import (
    RedditProvider
)

from data.providers.social.social_evidence_provider import (
    SocialEvidenceProvider
)

from data.providers.social.social_summary_builder import (
    SocialSummaryBuilder
)

from data.providers.generic_evidence_provider import (
    GenericEvidenceProvider
)


def print_header(title):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def test_reddit_provider():

    print_header(
        "TEST: Reddit Provider"
    )

    provider = RedditProvider()

    results = provider.search(
        "local ai models"
    )

    print(
        f"Results returned: {len(results)}"
    )

    if results:

        print()
        print("First Result:")
        print(
            json.dumps(
                results[0],
                indent=2,
                default=str
            )
        )

    return results


def test_social_provider():

    print_header(
        "TEST: Social Evidence Provider"
    )

    provider = (
        SocialEvidenceProvider()
    )

    context = (
        provider.get_context(
            query="local ai models"
        )
    )

    print(
        json.dumps(
            context,
            indent=2,
            default=str
        )
    )

    return context


def test_social_summary():

    print_header(
        "TEST: Social Summary"
    )

    builder = (
        SocialSummaryBuilder()
    )

    summary = builder.build(
        [
            {
                "platform": "reddit",
                "author": "user1",
                "content": (
                    "local models improve privacy "
                    "and local inference performance"
                ),
                "url": "test1"
            },
            {
                "platform": "reddit",
                "author": "user2",
                "content": (
                    "local inference requires "
                    "more memory"
                ),
                "url": "test2"
            }
        ]
    )

    print(
        json.dumps(
            summary,
            indent=2,
            default=str
        )
    )

    return summary


def test_generic_provider():

    print_header(
        "TEST: Generic Evidence Provider"
    )

    provider = (
        GenericEvidenceProvider()
    )

    context = (
        provider.get_context(
            query="local ai coding tools"
        )
    )

    print()
    print("Returned Keys:")

    for key in context.keys():
        print(
            f" - {key}"
        )

    print()

    print(
        json.dumps(
            context.get(
                "social_summary",
                {}
            ),
            indent=2,
            default=str
        )
    )

    return context


if __name__ == "__main__":

    test_reddit_provider()

    test_social_provider()

    test_social_summary()

    test_generic_provider()

    print()
    print(
        "SOCIAL PIPELINE TEST COMPLETE"
    )