import os
import sys
from pathlib import Path
from datetime import (
    datetime,
    timezone,
    timedelta
)

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from data.providers.live.public_topic_news_backend import (
    PublicTopicNewsBackend
)
from data.providers.live.firecrawl_backend import (
    FirecrawlBackend
)


class LiveMarketProvider:

    def _parse_published_at(
        self,
        value
    ):

        if not isinstance(
            value,
            str
        ):

            return None


        value = value.strip()


        if not value:

            return None


        try:

            parsed = datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00"
                )
            )

        except ValueError:

            return None


        if parsed.tzinfo is None:

            parsed = parsed.replace(
                tzinfo=timezone.utc
            )
        return parsed

    def _get_max_age_days(
        self,
        query
    ):

        if not isinstance(
            query,
            str
        ):

            return 7


        normalized = (
            query
            .strip()
            .lower()
        )


        if (
            "today" in normalized
            or "now" in normalized
        ):

            return 1


        if (
            "this week" in normalized
            or "latest" in normalized
            or "recent" in normalized
            or "recently" in normalized
            or "current" in normalized
            or "currently" in normalized
        ):

            return 7

        if "this month" in normalized:

            return 31

        return 7

    def _filter_recent_results(
        self,
        results,
        query
    ):

        if not isinstance(
            results,
            list
        ):

            return []


        max_age_days = (
            self._get_max_age_days(
                query
            )
        )


        cutoff = (
            datetime.now(
                timezone.utc
            )
            - timedelta(
                days=max_age_days
            )
        )


        filtered = []


        for result in results:

            if not isinstance(
                result,
                dict
            ):

                continue

            published_at = (
                self._parse_published_at(
                    result.get(
                        "published_at"
                    )
                )
            )

            if published_at is None:

                continue

            if published_at < cutoff:

                continue

            filtered.append(
                result
            )

        filtered.sort(
            key=lambda item: (
                self._parse_published_at(
                    item.get(
                        "published_at"
                    )
                )
                or datetime.min.replace(
                    tzinfo=timezone.utc
                )
            ),
            reverse=True
        )

        return filtered

    def __init__(
        self
    ):

        self.backends = [
            PublicTopicNewsBackend()
        ]

        self.firecrawl = (
            FirecrawlBackend()
        )

        self.max_firecrawl_pages = 5
        
    def _enrich_results(
        self,
        results
    ):

        if not isinstance(
            results,
            list
        ):

            return []


        if not self.firecrawl.health_check():

            return results


        enriched_count = 0


        for result in results:

            if enriched_count >= (
                self.max_firecrawl_pages
            ):

                break


            if not isinstance(
                result,
                dict
            ):

                continue


            url = result.get(
                "url"
            )


            if not url:

                continue


            scraped = (
                self.firecrawl.retrieve(
                    url
                )
            )


            if not scraped:

                continue


            content = scraped.get(
                "markdown"
            )


            if not content:

                continue


            result[
                "content"
            ] = content


            result[
                "content_retrieved_by"
            ] = "Firecrawl"


            firecrawl_title = (
                scraped.get(
                    "title"
                )
            )


            if firecrawl_title:

                result[
                    "retrieved_title"
                ] = firecrawl_title


            enriched_count += 1
        return results

    def _collect_results(
        self,
        company,
        query
    ):

        results = []
        sources = []

        for backend in self.backends:

            try:

                backend_results = (
                    backend.search(
                        company=company,
                        query=query
                    )
                )

            except Exception:

                continue

            if not isinstance(
                backend_results,
                list
            ):

                continue

            for result in backend_results:

                if not isinstance(
                    result,
                    dict
                ):
                    continue

                title = result.get(
                    "title"
                )

                if not title:
                    continue

                results.append(
                    result
                )

            source_name = getattr(
                backend,
                "SOURCE",
                None
            )

            if (
                source_name
                and source_name not in sources
            ):

                sources.append(
                    source_name
                )


        deduplicated = []

        seen = set()


        for result in results:

            key = (
                result.get(
                    "url"
                )
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
            
        return (
            deduplicated,
            sources
        )
        
    def _empty_context(
        self,
        company,
        query
    ):

        return {
            "available":
                False,

            "query":
                query,

            "company":
                company,

            "results":
                [],

            "sources":
                []
        }


    def _normalize_result(
        self,
        title=None,
        published_at=None,
        source=None,
        summary=None,
        url=None
    ):

        if not title:
            return None

        return {
            "title":
                title,

            "published_at":
                published_at,

            "source":
                source,

            "summary":
                summary,

            "url":
                url,

            "source_type":
                "live_market"
        }


    def get_context(
        self,
        company,
        query
    ):

        if not isinstance(
            company,
            dict
        ):

            return self._empty_context(
                company,
                query
            )

        if not isinstance(
            query,
            str
        ):

            return self._empty_context(
                company,
                query
            )

        query = query.strip()

        if not query:

            return self._empty_context(
                company,
                query
            )

        results, sources = (
            self._collect_results(
                company=company,
                query=query
            )
        )


        results = (
            self._filter_recent_results(
                results,
                query
            )
        )


        results = (
            self._enrich_results(
                results
            )
        )


        return {
            "available":
                bool(results),

            "query":
                query,

            "company":
                company,

            "results":
                results,

            "sources":
                sources,
            
            "recency_policy": {
                "max_age_days":
                    self._get_max_age_days(
                        query
                    )
            },
                
        
        }
