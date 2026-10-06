from data.providers.social.reddit_provider import (
    RedditProvider
)
from data.providers.social.x_provider import (
    XProvider
)
from data.providers.social.social_query_builder import (
    SocialQueryBuilder
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
        self.query_builder = (
            SocialQueryBuilder()
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
        
        reddit_found = False
        x_found = False

        expanded_queries = (
            self.query_builder.build(
                ticker=query
            )
        )

        expanded_queries.extend(
            search_queries
        )

        expanded_queries = list(
            dict.fromkeys(
                expanded_queries
            )
        )

        for search_query in expanded_queries:

            reddit_results = (
                self.reddit.search(
                    query=search_query
                )
            )

            if reddit_results:
                reddit_found = True

            all_results.extend(
                reddit_results
            )

            x_results = (
                self.x.search(
                    query=search_query
                )
            )

            if x_results:
                x_found = True

            all_results.extend(
                x_results
            )


        if x_results:
            x_found = True

        all_results.extend(
            x_results
        )

        for search_query in search_queries:
        
            reddit_results = self.reddit.search(
                query=search_query
            )
            
            all_results.extend(
                reddit_results
            )
            
            x_results = self.x.search(
                query=search_query
            )
            
            all_results.extend(
                x_results
            )

        sources = []

        if reddit_found:
            sources.append("reddit")

        if x_found:
            sources.append("x")        
        
        print()
        print("=" * 50)
        print("SOCIAL SUMMARY")
        print("=" * 50)

        print(
            f"Queries={len(expanded_queries)}"
        )

        print(
            f"Sources={sources}"
        )

        print(
            f"Raw Results={len(all_results)}"
        )

        print(
            f"Deduped Results={len(deduped_results)}"
        )
        
        
        seen_urls = set()

        deduped_results = []

        for result in all_results:

            url = result.get("url")

            if url and url in seen_urls:
                continue

            if url:
                seen_urls.add(url)

            deduped_results.append(
                result
            )
            
        return {
            "available": bool(
                deduped_results
            ),
            "results": deduped_results,
            "sources": sources
        }
                