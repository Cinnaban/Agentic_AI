from ddgs import (
    DDGS
)


class PublicTopicNewsBackend:

    SOURCE = "DuckDuckGo News"


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


        title = title.strip()


        if not title:

            return None


        published_at = result.get(
            "date"
        )

        source = result.get(
            "source"
        )

        summary = result.get(
            "body"
        )

        url = result.get(
            "url"
        )


        if isinstance(
            published_at,
            str
        ):

            published_at = (
                published_at.strip()
            )


        if isinstance(
            source,
            str
        ):

            source = (
                source.strip()
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


        return {
            "title":
                title,

            "published_at":
                published_at,

            "source":
                (
                    source
                    or self.SOURCE
                ),

            "summary":
                summary,

            "url":
                url,

            "source_type":
                "live_market"
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


        query = query.strip()


        if not query:

            return []


        try:

            with DDGS() as ddgs:

                raw_results = list(
                    ddgs.news(
                        query,
                        max_results=(
                            self.max_results
                        )
                    )
                )

        except Exception:

            return []


        results = []


        for raw_result in raw_results:

            normalized = (
                self._normalize(
                    raw_result
                )
            )


            if normalized:

                results.append(
                    normalized
                )


        return results