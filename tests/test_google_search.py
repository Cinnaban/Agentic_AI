import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import google_search


class GoogleSearchTests(unittest.TestCase):

    def test_disabled_without_keys(self):
        with mock.patch.dict(os.environ, {"GOOGLE_SEARCH_API_KEY": "", "GOOGLE_SEARCH_ENGINE_ID": ""}):
            self.assertFalse(google_search.configured())
            self.assertEqual(google_search.search("WMT"), [])

    def test_extracts_only_explicit_quarter_eps(self):
        items = [
            {"title": "Walmart Q2", "snippet": "For the quarter ended July 31, 2025, diluted EPS of $0.68 rose."},
            {"title": "Vague", "snippet": "EPS beat expectations at $0.70."},
        ]
        self.assertEqual(google_search.extract_quarterly_eps(items), {"2025-07-31": 0.68})

    def test_search_caches_and_respects_quota(self):
        payload = {"items": [{"title": "t", "link": "https://x", "snippet": "s"}]}
        response = mock.Mock(json=lambda: payload, raise_for_status=lambda: None)
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(os.environ, {"GOOGLE_SEARCH_API_KEY": "k", "GOOGLE_SEARCH_ENGINE_ID": "c"}), \
                mock.patch.object(google_search, "CACHE_DIR", Path(tmp)), \
                mock.patch.object(google_search.requests, "get", return_value=response) as get:
            self.assertEqual(len(google_search.search("q")), 1)
            self.assertEqual(len(google_search.search("q")), 1)
            self.assertEqual(get.call_count, 1)
            with mock.patch.object(google_search, "DAILY_LIMIT", 1):
                self.assertEqual(google_search.search("other"), [])
                self.assertEqual(get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
