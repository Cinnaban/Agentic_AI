import requests
import xml.etree.ElementTree as ET

from datetime import (
    datetime,
    timezone,
    timedelta
)

from email.utils import (
    parsedate_to_datetime
)

class RSSNewsProvider:

    def _parse_feed(
        self,
        content,
        source,
        source_type="news"
    ):
        try:
            root = ET.fromstring(
                content
            )
        except ET.ParseError:
            return []
        articles = []
        for item in root.findall(
            ".//item"
        ):
            normalized = (
                self._normalize_entry(
                    {
                        "title":
                            item.findtext(
                                "title"
                            ),
                        "published_at":
                            item.findtext(
                                "pubDate"
                            ),
                        "summary":
                            item.findtext(
                                "description"
                            ),
                        "url":
                            item.findtext(
                                "link"
                            )
                    },
                    source,
                    source_type
                )
            )
            if normalized:
                articles.append(
                    normalized
                )
        return self._deduplicate(
            articles
        )

    def _fetch_feed(
        self,
        url,
        source,
        source_type="news"
    ):
        try:
            response = requests.get(
                url,
                timeout=15,
                headers={
                    "User-Agent":
                        "HermesMarketResearch/1.0"
                }
            )

        except requests.RequestException:
            return []

        if response.status_code != 200:
            return []

        return self._parse_feed(
            response.content,
            source,
            source_type
        )
        
    def test_feed(
        self,
        feed
    ):

        result = {
            "configured": False,
            "reachable": False,
            "articles_found": 0
        }

        if not isinstance(
            feed,
            dict
        ):
            return result

        url = feed.get(
            "url"
        )

        source = feed.get(
            "source"
        )

        source_type = feed.get(
            "source_type",
            "news"
        )

        if not url or not source:
            return result

        result[
            "configured"
        ] = True

        try:

            response = requests.get(
                url,
                timeout=15,
                headers={
                    "User-Agent":
                        "HermesMarketResearch/1.0"
                }
            )

        except requests.RequestException:

            return result

        if response.status_code != 200:
            return result

        result[
            "reachable"
        ] = True

        articles = self._parse_feed(
            response.content,
            source,
            source_type
        )

        result[
            "articles_found"
        ] = len(
            articles
        )

        return result

    def get_news(
        self,
        company,
        feeds=None
    ):

        if not feeds:
            return []

        articles = []

        for feed in feeds:

            if not isinstance(
                feed,
                dict
            ):
                continue

            url = feed.get(
                "url"
            )

            source = feed.get(
                "source"
            )
            source_type = feed.get(
                "source_type",
                "news"
            )

            if not url or not source:
                continue

            articles.extend(
                self._fetch_feed(
                    url,
                    source,
                    source_type
                )
            )

        relevant_articles = [
            article
            for article
            in articles
            if self._is_relevant(
                article,
                company
            )
        ]


        fresh_articles = [
            article
            for article
            in relevant_articles
            if self._is_fresh(
                article
            )
        ]


        return self._deduplicate(
            fresh_articles
        )
    
    def _deduplicate(
        self,
        articles
    ):

        results = []

        seen = set()

        for article in articles:

            if not isinstance(
                article,
                dict
            ):
                continue

            key = (
                article.get(
                    "url"
                )
                or article.get(
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

            results.append(
                article
            )
        return results
    
    def _is_relevant(
        self,
        article,
        company
    ):

        if not isinstance(
            article,
            dict
        ):
            return False

        if not isinstance(
            company,
            dict
        ):
            return False

        company_name = str(
            company.get(
                "name",
                ""
            )
        ).strip().lower()

        ticker = str(
            company.get(
                "ticker",
                ""
            )
        ).strip().lower()

        title = str(
            article.get(
                "title",
                ""
            )
        ).lower()

        summary = str(
            article.get(
                "summary",
                ""
            )
        ).lower()

        searchable_text = (
            title
            + " "
            + summary
        )

        if (
            company_name
            and company_name
            in searchable_text
        ):

            return True

        if (
            ticker
            and ticker
            in searchable_text
        ):

            return True

        return False

    def _is_fresh(
        self,
        article,
        max_age_days=7
    ):

        if not isinstance(
            article,
            dict
        ):
            return False

        published_at = article.get(
            "published_at"
        )

        if not published_at:
            return False

        try:

            published_date = (
                parsedate_to_datetime(
                    published_at
                )
            )

        except (
            TypeError,
            ValueError
        ):

            return False

        if published_date.tzinfo is None:

            published_date = (
                published_date.replace(
                    tzinfo=timezone.utc
                )
            )

        now = datetime.now(
            timezone.utc
        )

        cutoff = (
            now
            - timedelta(
                days=max_age_days
            )
        )

        return (
            published_date
            >= cutoff
        )

    def _normalize_entry(
        self,
        entry,
        source,
        source_type="news"
    ):

        if not isinstance(
            entry,
            dict
        ):

            return None

        title = entry.get(
            "title"
        )
        if isinstance(
            title,
            str
        ):

            title = title.strip()
        if not title:

            return None
        published_at = entry.get(
            "published_at"
        )

        summary = entry.get(
            "summary"
        )

        url = entry.get(
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
                source,

            "summary":
                summary,

            "url":
                url,

            "source_type":
                source_type
        }