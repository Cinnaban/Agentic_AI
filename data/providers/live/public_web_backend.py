from concurrent.futures import ThreadPoolExecutor

from ddgs import (
    DDGS
)


class PublicWebBackend:

    SOURCE = "Public Web Search"

    REGION = "us-en"

    BACKENDS = (
        "google",
        "yahoo",
        "bing"
    )


    def __init__(
        self,
        max_results=8
    ):

        self.max_results = (
            max_results
        )


    def _normalize(
        self,
        result
    ):

        if not isinstance(
            result,
            dict
        ):

            return None


        title = result.get(
            "title"
        )


        if not isinstance(
            title,
            str
        ):

            return None


        title = (
            title.strip()
        )


        if not title:

            return None


        summary = result.get(
            "body"
        )


        url = result.get(
            "href"
        )


        if not url:

            url = result.get(
                "url"
            )


        if isinstance(
            summary,
            str
        ):

            summary = (
                summary.strip()
            )


        if isinstance(
            url,
            str
        ):

            url = (
                url.strip()
            )


        if not url:

            return None


        return {
            "title":
                title,

            "published_at":
                None,

            "source":
                self.SOURCE,

            "summary":
                summary,

            "url":
                url,

            "source_type":
                "public_web"
        }


    def search(
        self,
        company,
        query
    ):

        if not isinstance(
            query,
            str
        ):

            return []


        query = (
            query.strip()
        )


        if not query:

            return []


        def fetch(backend):
            for attempt in range(2):
                try:
                    with DDGS() as ddgs:
                        return list(
                            ddgs.text(
                                query,
                                region=self.REGION,
                                max_results=self.max_results,
                                backend=backend
                            )
                        )
                except Exception as exc:
                    if attempt == 1 or "No results" in repr(exc):
                        print(
                            "PublicWebBackend "
                            f"{backend} error:",
                            repr(exc)
                        )
                        return []
            return []

        with ThreadPoolExecutor(
            max_workers=len(self.BACKENDS)
        ) as pool:
            per_backend = list(pool.map(fetch, self.BACKENDS))

        raw_results = []
        for rank in range(self.max_results):
            for backend_results in per_backend:
                if rank < len(backend_results):
                    raw_results.append(backend_results[rank])

        if not raw_results:

            return []

#Normalization Loop 
        results = []

        seen_urls = set()


        for raw_result in raw_results:

            normalized = (
                self._normalize(
                    raw_result
                )
            )


            if not normalized:

                continue


            url = normalized.get(
                "url"
            )


            if not url:

                continue


            if url in seen_urls:

                continue


            seen_urls.add(
                url
            )


            results.append(
                normalized
            )


            if len(
                results
            ) >= self.max_results:

                break


        return results