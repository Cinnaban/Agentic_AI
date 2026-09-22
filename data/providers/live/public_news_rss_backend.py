import requests

import xml.etree.ElementTree as ET

from urllib.parse import (
    quote_plus
)


class PublicNewsRSSBackend:

    SOURCE = "public_news_rss"


    def _normalize(
        self,
        title,
        published_at,
        summary,
        url
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

            result = (
                self._normalize(
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
            )


            if result:

                results.append(
                    result
                )


        return results