from data.providers.social.reddit_provider import (
    RedditProvider
)
from data.providers.social.x_provider import (
    XProvider
)


class SocialEvidenceProvider:

    def __init__(
        self
    ):
        self.reddit = (
            RedditProvider()
        )
        self.x = (
            XProvider()
        )

    def get_context(
        self,
        query,
        search_queries=None
    ):
        if search_queries is None:
            search_queries = []

        if not isinstance(
            search_queries,
            list
        ):
            search_queries = []

        all_results = []

        reddit_results = (
            self.reddit.search(
                query=query
            )
        )

        all_results.extend(
            reddit_results
        )
        
        x_results = (
            self.x.search(
                query=query
            )
        )

        all_results.extend(
            x_results
        )

        for search_query in search_queries:

            results = (
                self.reddit.search(
                    query=search_query
                )
            )

            all_results.extend(
                results
            )

        return {
            "available":
                bool(
                    all_results
                ),

            "results":
                all_results,

            "sources": [
                "reddit"
            ]
        }