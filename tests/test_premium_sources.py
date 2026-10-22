import os
import unittest
from unittest.mock import MagicMock, patch

from data.providers.live import premium_sources as ps
from data.providers.live.firecrawl_backend import FirecrawlBackend
from data.providers.live.public_web_backend import PublicWebBackend


def resp(payload, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload
    return r


class PremiumSourceTests(unittest.TestCase):

    def test_disabled_without_keys(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(ps.SerpApiBackend().is_configured())
            self.assertFalse(ps.ExaBackend().is_configured())
            self.assertFalse(ps.Crawl4AIBackend().is_configured())
            self.assertEqual(ps.ExaBackend().search("x"), [])

    def test_serpapi_parses_organic_results(self):
        with patch.dict(os.environ, {"SERPAPI_API_KEY": "k"}):
            backend = ps.SerpApiBackend()
        payload = {"organic_results": [
            {"title": "TSMC competitors", "link": "https://a.com/x", "snippet": "Samsung, Intel"}]}
        with patch.object(ps.requests, "get", return_value=resp(payload)):
            out = backend.search("TSMC competitors")
        self.assertEqual(out[0]["url"], "https://a.com/x")
        self.assertEqual(out[0]["source"], "SerpAPI")

    def test_exa_search_and_contents(self):
        with patch.dict(os.environ, {"EXA_API_KEY": "k"}):
            backend = ps.ExaBackend()
        search = {"results": [{"title": "T", "url": "https://b.com", "text": "body " * 50, "highlights": ["h"]}]}
        with patch.object(ps.requests, "post", return_value=resp(search)):
            out = backend.search("q")
            page = backend.retrieve("https://b.com")
        self.assertEqual(out[0]["summary"], "h")
        self.assertTrue(page["markdown"])

    def test_crawl4ai_markdown(self):
        with patch.dict(os.environ, {"CRAWL4AI_BASE_URL": "http://localhost:11235"}):
            backend = ps.Crawl4AIBackend()
        crawl = {"results": [{"success": True, "markdown": {"raw_markdown": "word " * 100}, "metadata": {"title": "t"}}]}
        with patch.object(ps.requests, "get", return_value=resp({}, 200)), \
                patch.object(ps.requests, "post", return_value=resp(crawl)):
            page = backend.retrieve("https://c.com")
        self.assertEqual(page["retrieved_by"], "Crawl4AI")

    def test_daily_budget_caps_calls(self):
        with patch.dict(os.environ, {"WEB_PREMIUM_DAILY_LIMIT": "1"}):
            budget = ps._Budget()
            self.assertTrue(budget.take("x"))
            self.assertFalse(budget.take("x"))

    def test_search_merges_premium_results(self):
        with patch.dict(os.environ, {"EXA_API_KEY": "k"}):
            backend = PublicWebBackend(max_results=4)
        premium = [{"title": "Exa hit", "url": "https://e.com", "summary": "s",
                    "source": "Exa", "source_type": "public_web", "published_at": None}]
        with patch.object(backend.exa, "search", return_value=premium), \
                patch("data.providers.live.public_web_backend.DDGS", side_effect=RuntimeError("down")):
            out = backend.search({}, "query")
        self.assertEqual(out[0]["source"], "Exa")

    def test_page_chain_falls_through_to_crawl4ai(self):
        backend = FirecrawlBackend()
        backend._health_cache = (9e12, False)
        fake = MagicMock()
        fake.is_configured.return_value = True
        fake.retrieve.return_value = {"markdown": "x" * 300, "retrieved_by": "Crawl4AI"}
        backend._crawl4ai = fake
        backend._exa = MagicMock(is_configured=lambda: False)
        with patch.object(FirecrawlBackend, "_is_public_http_url", return_value=True):
            self.assertEqual(backend.retrieve_page("https://x.com")["retrieved_by"], "Crawl4AI")


if __name__ == "__main__":
    unittest.main()
