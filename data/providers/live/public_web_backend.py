from ddgs import (
    DDGS
)


class PublicWebBackend:

    SOURCE = "Public Web Search"

    BACKENDS = (
        "bing",
        "google"
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


        raw_results = []

        for backend in self.BACKENDS:

            try:

                with DDGS() as ddgs:

                    backend_results = list(
                        ddgs.text(
                            query,

                            max_results=(
                                self.max_results
                            ),

                            backend=backend
                        )
                    )


                if backend_results:

                    raw_results.extend(
                        backend_results
                    )


                if len(
                    raw_results
                ) >= self.max_results:

                    break


            except Exception as exc:

                print(
                    "PublicWebBackend "
                    f"{backend} error:",
                    repr(
                        exc
                    )
                )


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