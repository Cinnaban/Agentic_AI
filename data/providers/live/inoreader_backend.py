import os

import requests

import xml.etree.ElementTree as ET


class InoreaderBackend:

    SOURCE = "Inoreader"


    def __init__(
        self
    ):

        self.feed_url = os.getenv(
            "INOREADER_FINANCE_LIVE_FEED_URL"
        )       
        

    def is_configured(
        self
    ):

        return bool(
            self.feed_url
        )
    
    def _normalize(
        self,
        title=None,
        published_at=None,
        summary=None,
        url=None
    ):

        if not isinstance(
            title,
            str
        ):
            return None

        title = title.strip()

        if not title:
            return None


        if isinstance(
            published_at,
            str
        ):
            published_at = (
                published_at.strip()
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
                self.SOURCE,

            "summary":
                summary,

            "url":
                url,

            "source_type":
                "live_market"
        }
    def _parse(
        self,
        content
    ):

        try:

            root = ET.fromstring(
                content
            )

        except ET.ParseError:

            return []


        results = []


        for item in root.findall(
            ".//item"
        ):

            result = self._normalize(
                title=(
                    item.findtext(
                        "title"
                    )
                ),

                published_at=(
                    item.findtext(
                        "pubDate"
                    )
                ),

                summary=(
                    item.findtext(
                        "description"
                    )
                ),

                url=(
                    item.findtext(
                        "link"
                    )
                )
            )


            if result:

                results.append(
                    result
                )
            return results

    def search(
        self,
        company,
        query
    ):

        if not self.is_configured():

            return []


        try:

            response = requests.get(
                self.feed_url,
                timeout=15,
                headers={
                    "User-Agent":
                        "StockAgent/1.0"
                }
            )

        except requests.RequestException:

            return []


        if response.status_code != 200:

            return []


        return self._parse(
            response.content
        )