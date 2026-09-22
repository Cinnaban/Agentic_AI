import os
import requests


class FirecrawlBackend:

    SOURCE = "Firecrawl"


    def __init__(self):

        self.base_url = (
            os.getenv(
                "FIRECRAWL_BASE_URL",
                "http://localhost:3002"
            )
            .rstrip("/")
        )
        
        self.max_content_length = (
            12000
        )

    def is_configured(self):

        return bool(self.base_url)


    def health_check(self):

        try:
            response = requests.get(
                f"{self.base_url}/v0/health/liveness",
                timeout=10
            )
        except requests.RequestException:
            return False

        return response.status_code == 200


    def retrieve(
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

            response = requests.post(
                f"{self.base_url}/v2/scrape",

                json={
                    "url":
                        url,

                    "formats":
                        [
                            "markdown"
                        ]
                },

                timeout=90
            )

        except requests.RequestException:

            return None


        if response.status_code != 200:

            return None


        try:

            payload = response.json()

        except ValueError:

            return None


        if not isinstance(
            payload,
            dict
        ):

            return None


        if not payload.get(
            "success"
        ):

            return None


        data = payload.get(
            "data"
        )


        if not isinstance(
            data,
            dict
        ):

            return None


        markdown = data.get(
            "markdown"
        )


        metadata = data.get(
            "metadata",
            {}
        )


        if not isinstance(
            metadata,
            dict
        ):

            metadata = {}


        if not isinstance(
            markdown,
            str
        ):

            markdown = ""


        markdown = (
            markdown.strip()
        )


        if not markdown:

            return None


        if len(
            markdown
        ) > self.max_content_length:

            markdown = (
                markdown[
                    :self.max_content_length
                ]
            )


        return {
            "url":
                url,

            "title":
                metadata.get(
                    "title"
                ),

            "description":
                metadata.get(
                    "description"
                ),

            "markdown":
                markdown,

            "metadata":
                metadata,

            "source":
                self.SOURCE,

            "retrieved_by":
                "Firecrawl",

            "success":
                True
        }