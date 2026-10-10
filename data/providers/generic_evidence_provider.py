from datetime import datetime, timezone
from urllib.parse import (
    urlsplit,
    urlunsplit
)

from data.providers.live.public_web_backend import (
    PublicWebBackend
)

from data.providers.live.public_topic_news_backend import (
    PublicTopicNewsBackend
)

from data.providers.live.firecrawl_backend import (
    FirecrawlBackend
)

from data.providers.social.social_evidence_provider import (
    SocialEvidenceProvider
)

from data.providers.social.social_summary_builder import (
    SocialSummaryBuilder
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

        self.social = (
            SocialEvidenceProvider()
        )
        
        self.social_summary_builder = (
            SocialSummaryBuilder()
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
            research_plan,
            dict
        ):

            research_plan = {}


        evidence_depth = (
            research_plan.get(
                "evidence_depth",
                "standard"
            )
        )


        if evidence_depth not in {
            "summary",
            "standard",
            "deep"
        }:

            evidence_depth = (
                "standard"
            )


        if evidence_depth == "summary":

            page_limit = 2


        elif evidence_depth == "deep":

            page_limit = (
                self.max_pages
            )


        else:

            page_limit = min(
                6,
                self.max_pages
            )


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
                deduplicated,
                page_limit=page_limit
            )
        )
        social_context = (
            self.social.get_context(
                query=query,
                search_queries=cleaned_queries
            )
        )
        social_summary = (
            self.social_summary_builder
            .build(
                social_context.get(
                    "results",
                    []
                )
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

        social_sources = (
            social_context.get(
                "sources",
                []
            )
        )

        for source in social_sources:

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
                    or social_context.get(
                        "results"
                    )
                ),

            "query":
                query,

            "results":
                enriched,
                
            "social_results":
                social_context.get(
                    "results",
                    []
                ),
                
            "social_summary":
                social_summary,

            "search_queries":
                cleaned_queries,

            "research_plan":
                research_plan,

            "evidence_depth":
                evidence_depth,

            "page_limit":
                page_limit,

            "sources":
                sources,

            "retrieved_at":
                datetime.now(timezone.utc).isoformat()
        }

    def _enrich(
        self,
        results,
        page_limit=None
    ):


        if not isinstance(
            page_limit,
            int
        ):

            page_limit = (
                self.max_pages
            )

        if page_limit < 0:

            page_limit = 0
            
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
            < page_limit
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
                    page_limit
                ):

                    break


            if not found_candidate:

                break


            index += 1


        return results