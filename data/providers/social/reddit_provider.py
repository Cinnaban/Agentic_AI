import sys
import traceback
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from data.providers.social.social_record_normalizer import (
    SocialRecordNormalizer
)
from data.providers.live.firecrawl_backend import (
    FirecrawlBackend
)
from configs.config import (
    Config
)
class RedditProvider:

    def __init__(
        self
    ):
        self.normalizer = (
            SocialRecordNormalizer()
        )
        self.firecrawl = (
            FirecrawlBackend()
        )

    def search(
        self,
        query,
        limit=None
    ):
        if not Config.ENABLE_SOCIAL:
            return []

        if not Config.ENABLE_REDDIT:
            return []
        
        if not isinstance(
            query,
            str
        ):
            return []

        query = query.strip()

        if not query:
            return []

        raw_results = (
            self._fetch_results(
                query=query,
                limit=limit
            )
        )

        records = []

        for result in raw_results:

            normalized = (
                self.normalizer
                .normalize_reddit(
                    result
                )
            )

            if normalized:
                records.append(
                    normalized
                )

        return records

    def _build_reddit_urls(
        self,
        query
    ):
        query = query.strip()

        return [
            (
                "https://www.reddit.com/search/?q="
                + query.replace(
                    " ",
                    "%20"
                )
            )
        ]

    def _fetch_results(
        self,
        query,
        limit
    ):
        
        if Config.DEBUG:

            print()
            print("=" * 50)
            print("REDDIT SEARCH")
            print("=" * 50)
            print(
                "QUERY:",
                query
            )
            
        if not self.firecrawl.health_check():
            print("[REDDIT] Firecrawl health check failed")
            return []   

        urls = (
            self._build_reddit_urls(
                query
            )
        )

        results = []

        for url in urls:

            scraped = (
                self.firecrawl.retrieve(
                    url
                )
            )
            print(
                f"[REDDIT] URL={url} "
                f"SCRAPED={scraped is not None}"
            )

            if not scraped:
                continue

            markdown = scraped.get(
                "markdown",
                ""
            )
            
            print(
                f"[REDDIT] Markdown Length="
                f"{len(markdown)}"
            )

            if not markdown:
                continue

            results.append(
                {
                    "title":
                        f"Reddit Discussion: {query}",

                    "content":
                        markdown,

                    "author":
                        "reddit",

                    "timestamp":
                        None,

                    "url":
                        url,

                    "score":
                        None,

                    "comments":
                        None,

                    "query":
                        query
                }
            )
            
        if Config.DEBUG:
            print(
                "RESULTS:",
                len(results)
            )

        return results