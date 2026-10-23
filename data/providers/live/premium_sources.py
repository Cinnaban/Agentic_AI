"""Optional premium web sources (SerpAPI, Exa, Brave Search, Crawl4AI). Each stays disabled until configured."""
import os
import threading
import time

import requests

MAX_CONTENT = 12000


class _Budget:
    """Per-process daily call cap so paid APIs cannot run away."""

    def __init__(self):
        self._lock = threading.Lock()
        self._day = None
        self._counts = {}

    def take(self, name):
        limit = int(os.getenv("WEB_PREMIUM_DAILY_LIMIT", "200"))
        today = time.strftime("%Y-%m-%d")
        with self._lock:
            if self._day != today:
                self._day, self._counts = today, {}
            if self._counts.get(name, 0) >= limit:
                return False
            self._counts[name] = self._counts.get(name, 0) + 1
            return True


BUDGET = _Budget()


def _result(title, url, summary, source, published=None, content=None):
    if not (isinstance(title, str) and title.strip() and isinstance(url, str) and url.strip()):
        return None
    item = {
        "title": title.strip(),
        "published_at": published,
        "source": source,
        "summary": (summary or "").strip() if isinstance(summary, str) else None,
        "url": url.strip(),
        "source_type": "public_web",
    }
    if content:
        item["content"] = content[:MAX_CONTENT]
        item["content_retrieved_by"] = source
    return item


class SerpApiBackend:
    SOURCE = "SerpAPI"

    def __init__(self, max_results=8):
        self.api_key = os.getenv("SERPAPI_API_KEY", "").strip()
        self.max_results = max_results

    def is_configured(self):
        return bool(self.api_key)

    def search(self, query, news=False):
        if not self.is_configured() or not BUDGET.take("serpapi"):
            return []
        params = {
            "engine": "google",
            "q": query,
            "api_key": self.api_key,
            "num": self.max_results,
            "hl": "en",
            "gl": "us",
        }
        if news:
            params["tbm"] = "nws"
        try:
            response = requests.get("https://serpapi.com/search.json", params=params, timeout=20)
            data = response.json() if response.status_code == 200 else {}
        except (requests.RequestException, ValueError):
            return []
        rows = []
        for item in (data.get("news_results") if news else data.get("organic_results")) or []:
            rows.append(_result(
                item.get("title"),
                item.get("link"),
                item.get("snippet"),
                self.SOURCE,
                item.get("date"),
            ))
        graph = data.get("answer_box") or {}
        answer = graph.get("answer") or graph.get("snippet")
        if answer and rows:
            rows[0]["summary"] = f"{answer} {rows[0].get('summary') or ''}".strip()
        return [r for r in rows if r][: self.max_results]


class BraveSearchBackend:
    """Read-only Brave Search web/news API."""
    SOURCE = "Brave Search"

    def __init__(self, max_results=8):
        self.api_key = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
        self.max_results = max_results

    def is_configured(self):
        return bool(self.api_key)

    def search(self, query, news=False):
        if not self.is_configured() or not BUDGET.take("brave"):
            return []
        endpoint = "news" if news else "web"
        try:
            response = requests.get(
                f"https://api.search.brave.com/res/v1/{endpoint}/search",
                params={"q": query, "count": min(self.max_results, 20), "country": "us"},
                headers={"X-Subscription-Token": self.api_key, "Accept": "application/json"},
                timeout=20,
            )
            data = response.json() if response.status_code == 200 else {}
        except (requests.RequestException, ValueError):
            return []
        items = data.get("results") if news else (data.get("web") or {}).get("results")
        rows = [
            _result(
                item.get("title"),
                item.get("url"),
                item.get("description"),
                self.SOURCE,
                item.get("page_age") or item.get("age"),
            )
            for item in items or []
        ]
        return [r for r in rows if r][: self.max_results]


class ExaBackend:
    SOURCE = "Exa"
    BASE = "https://api.exa.ai"

    def __init__(self, max_results=8):
        self.api_key = os.getenv("EXA_API_KEY", "").strip()
        self.max_results = max_results

    def is_configured(self):
        return bool(self.api_key)

    def _post(self, path, payload):
        if not BUDGET.take("exa"):
            return {}
        try:
            response = requests.post(
                self.BASE + path,
                json=payload,
                headers={"x-api-key": self.api_key, "Content-Type": "application/json"},
                timeout=30,
            )
            return response.json() if response.status_code == 200 else {}
        except (requests.RequestException, ValueError):
            return {}

    def search(self, query):
        if not self.is_configured():
            return []
        data = self._post("/search", {
            "query": query,
            "numResults": self.max_results,
            "type": "auto",
            "contents": {"text": {"maxCharacters": 4000}, "highlights": {"numSentences": 3}},
        })
        rows = []
        for item in data.get("results") or []:
            highlights = item.get("highlights") or []
            rows.append(_result(
                item.get("title"),
                item.get("url"),
                " ".join(highlights) or (item.get("text") or "")[:300],
                self.SOURCE,
                item.get("publishedDate"),
                item.get("text"),
            ))
        return [r for r in rows if r][: self.max_results]

    def retrieve(self, url):
        if not self.is_configured():
            return None
        data = self._post("/contents", {"urls": [url], "text": {"maxCharacters": MAX_CONTENT}})
        for item in data.get("results") or []:
            text = (item.get("text") or "").strip()
            if len(text) >= 200:
                return {
                    "url": url, "title": item.get("title"), "description": None,
                    "markdown": text[:MAX_CONTENT], "metadata": {"title": item.get("title")},
                    "source": self.SOURCE, "retrieved_by": self.SOURCE, "success": True,
                }
        return None


class Crawl4AIBackend:
    """Talks to a Crawl4AI Docker server (default http://localhost:11235)."""
    SOURCE = "Crawl4AI"

    def __init__(self):
        self.base_url = os.getenv("CRAWL4AI_BASE_URL", "").strip().rstrip("/")
        self.token = os.getenv("CRAWL4AI_API_TOKEN", "").strip()
        self._health = (0.0, False)

    def is_configured(self):
        return bool(self.base_url)

    def healthy(self):
        if not self.is_configured():
            return False
        now = time.time()
        if now - self._health[0] > 60:
            try:
                ok = requests.get(f"{self.base_url}/health", timeout=5).status_code == 200
            except requests.RequestException:
                ok = False
            self._health = (now, ok)
        return self._health[1]

    def retrieve(self, url):
        if not self.healthy():
            return None
        headers = {"Authorization": "Bearer " + self.token} if self.token else {}
        try:
            response = requests.post(
                f"{self.base_url}/crawl",
                json={"urls": [url], "browser_config": {}, "crawler_config": {}},
                headers=headers,
                timeout=90,
            )
            if response.status_code != 200:
                return None
            results = (response.json() or {}).get("results") or []
        except (requests.RequestException, ValueError):
            return None
        if not results or not results[0].get("success", True):
            return None
        page = results[0]
        markdown = page.get("markdown")
        if isinstance(markdown, dict):
            markdown = markdown.get("fit_markdown") or markdown.get("raw_markdown")
        markdown = (markdown or "").strip()
        if len(markdown) < 200:
            return None
        meta = page.get("metadata") or {}
        return {
            "url": url, "title": meta.get("title"), "description": meta.get("description"),
            "markdown": markdown[:MAX_CONTENT], "metadata": meta,
            "source": self.SOURCE, "retrieved_by": self.SOURCE, "success": True,
        }
