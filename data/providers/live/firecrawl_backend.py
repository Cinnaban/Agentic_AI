import ipaddress
import os
import re
import socket
import time
from urllib.parse import urlsplit

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

    DIRECT_USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
    MAX_DIRECT_BYTES = 2_000_000

    def retrieve_page(self, url):
        """Firecrawl when it is up, otherwise a direct HTTP fetch."""
        now = time.time()
        cached = getattr(self, "_health_cache", None)
        if cached is None or now - cached[0] > 60:
            cached = (now, self.health_check())
            self._health_cache = cached
        if cached[1]:
            page = self.retrieve(url)
            if page:
                return page
        from data.providers.live.premium_sources import (
            Crawl4AIBackend, ExaBackend
        )
        if not hasattr(self, "_crawl4ai"):
            self._crawl4ai = Crawl4AIBackend()
            self._exa = ExaBackend()
        if self._crawl4ai.is_configured() and self._is_public_http_url(url.strip()):
            page = self._crawl4ai.retrieve(url.strip())
            if page:
                return page
        page = self.retrieve_direct(url)
        if page:
            return page
        if self._exa.is_configured() and self._is_public_http_url(url.strip()):
            return self._exa.retrieve(url.strip())
        return None

    @staticmethod
    def _is_public_http_url(url):
        try:
            parts = urlsplit(url)
            if parts.scheme not in ("http", "https") or not parts.hostname:
                return False
            for info in socket.getaddrinfo(parts.hostname, None):
                address = ipaddress.ip_address(info[4][0])
                if (
                    address.is_private
                    or address.is_loopback
                    or address.is_link_local
                    or address.is_reserved
                    or address.is_multicast
                ):
                    return False
            return True
        except (OSError, ValueError):
            return False

    def retrieve_direct(self, url):
        if not isinstance(url, str) or not self._is_public_http_url(url.strip()):
            return None
        url = url.strip()
        try:
            from bs4 import BeautifulSoup

            response = requests.get(
                url,
                headers={
                    "User-Agent": self.DIRECT_USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml"
                },
                timeout=8,
                stream=True
            )
            content_type = response.headers.get("Content-Type", "")
            if response.status_code != 200 or "html" not in content_type.lower():
                response.close()
                return None
            raw = response.raw.read(self.MAX_DIRECT_BYTES, decode_content=True)
            response.close()
            soup = BeautifulSoup(raw, "lxml")
        except Exception:
            return None

        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        description = ""
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            description = meta["content"].strip()
        for tag in soup([
            "script", "style", "noscript", "nav", "footer", "aside",
            "header", "form", "svg", "iframe"
        ]):
            tag.decompose()
        root = soup.find("main") or soup.find("article") or soup.body or soup
        lines = []
        for element in root.find_all(
            ["h1", "h2", "h3", "h4", "p", "li", "td", "th"]
        ):
            text = " ".join(element.get_text(" ", strip=True).split())
            if len(text) < 25 and element.name not in ("h1", "h2", "h3", "h4"):
                continue
            if element.name in ("h1", "h2", "h3", "h4"):
                text = "#" * int(element.name[1]) + " " + text
            elif element.name == "li":
                text = "- " + text
            if text and (not lines or lines[-1] != text):
                lines.append(text)
        markdown = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
        if len(markdown) < 200:
            return None
        return {
            "url": url,
            "title": title,
            "description": description,
            "markdown": markdown[:self.max_content_length],
            "metadata": {"title": title, "description": description},
            "source": "Direct fetch",
            "retrieved_by": "Direct fetch",
            "success": True
        }

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