import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from data.providers.live.public_topic_news_backend import (
    PublicTopicNewsBackend
)

class LiveMarketProvider:

    def __init__(
        self
    ):
 
        self.backends = [
            PublicTopicNewsBackend()
        ]
        
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
                sources
        
        }
