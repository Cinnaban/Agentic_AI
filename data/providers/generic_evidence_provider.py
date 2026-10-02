from data.providers.live.public_web_backend import (
    PublicWebBackend
)

from data.providers.live.public_topic_news_backend import (
    PublicTopicNewsBackend
)

from data.providers.live.firecrawl_backend import (
    FirecrawlBackend
)

from urllib.parse import (
    urlsplit,
    urlunsplit
)

class GenericEvidenceProvider:

    def __init__(
        self
    ):

        self.web = (
            PublicWebBackend()
        )

        self.news = (
            PublicTopicNewsBackend()
        )

        self.firecrawl = (
            FirecrawlBackend()
        )

        self.max_pages = 15

    def _normalize_url(
        self,
        url
    ):

        if not isinstance(
            url,
            str
        ):

            return None


        url = url.strip()


        if not url:

            return None


        try:

            parsed = urlsplit(
                url
            )


            normalized = (
                urlunsplit(
                    (
                        parsed.scheme.lower(),
                        parsed.netloc.lower(),
                        parsed.path.rstrip("/"),
                        "",
                        ""
                    )
                )
            )


        except Exception:

            return url


        return normalized

    def get_context(
        self,
        query,
        search_queries=None,
        research_plan=None
    ):
        if not isinstance(
            search_queries,
            list
        ):

            search_queries = []

        cleaned_queries = []

        for search_query in search_queries:

            if not isinstance(
                search_query,
                str
            ):

                continue

            search_query = (
                search_query.strip()
            )

            if (
                search_query
                and search_query
                not in cleaned_queries
            ):

                cleaned_queries.append(
                    search_query
                )

        if not cleaned_queries:

            cleaned_queries = [
                query
            ]

        results = []

        for search_query in (
            cleaned_queries
        ):

            web_results = (
                self.web.search(
                    company={},
                    query=search_query
                )
            )


            for result in web_results:

                if isinstance(
                    result,
                    dict
                ):

                    result[
                        "search_query"
                    ] = search_query


            results.extend(
                web_results
            )


        deduplicated = []

        seen = set()


        for result in results:

            if not isinstance(
                result,
                dict
            ):

                continue


            url = result.get(
                "url"
            )


            normalized_url = (
                self._normalize_url(
                    url
                )
            )

            key = (
                normalized_url
                or result.get(
                    "title"
                )
            )

            if not key:

                continue

            if key in seen:

                continue


            seen.add(
                key
            )

            deduplicated.append(
                result
            )


        enriched = (
            self._enrich(
                deduplicated
            )
        )


        sources = []


        for result in enriched:

            source = result.get(
                "source"
            )


            if (
                source
                and source not in sources
            ):

                sources.append(
                    source
                )


        return {
            "available":
                bool(
                    enriched
                ),

            "query":
                query,

            "results":
                enriched,

            "search_queries":
                cleaned_queries,

            "research_plan":
                research_plan,
            
            "sources":
                sources
        }


    def _enrich(
        self,
        results
    ):

        if not self.firecrawl.health_check():

            return results


        results_by_query = {}


        for result in results:

            if not isinstance(
                result,
                dict
            ):

                continue


            search_query = result.get(
                "search_query",
                "default"
            )


            results_by_query.setdefault(
                search_query,
                []
            ).append(
                result
            )


        enriched_count = 0

        index = 0


        while (
            enriched_count
            < self.max_pages
        ):

            found_candidate = False


            for query_results in (
                results_by_query.values()
            ):

                if index >= len(
                    query_results
                ):

                    continue


                result = query_results[
                    index
                ]


                url = result.get(
                    "url"
                )


                if not url:

                    continue


                found_candidate = True


                scraped = (
                    self.firecrawl.retrieve(
                        url
                    )
                )


                if not scraped:

                    continue


                markdown = scraped.get(
                    "markdown"
                )


                if not markdown:

                    continue


                result[
                    "content"
                ] = markdown


                result[
                    "content_retrieved_by"
                ] = "Firecrawl"


                enriched_count += 1


                if enriched_count >= (
                    self.max_pages
                ):

                    break


            if not found_candidate:

                break


            index += 1


        return results