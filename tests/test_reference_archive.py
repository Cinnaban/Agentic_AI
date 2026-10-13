import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from data.providers.generic_evidence_provider import GenericEvidenceProvider
from orchestrator.freshness_detector import FreshnessDetector
from shared_storage.reference_archive import PublicReferenceArchive


class PublicReferenceArchiveTests(unittest.TestCase):

    QUERY = "What is Example Research?"
    SUBJECT = "Example Research"
    PAGE = {
        "title": "Example Research",
        "source": "example.org",
        "source_host": "example.org",
        "source_role": "reference",
        "evidence_level": "retrieved_webpage",
        "content": "Example Research publishes public reference material.",
        "url": "https://example.org/about"
    }

    def test_public_pages_and_query_references_are_reused_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = PublicReferenceArchive(directory)
            self.assertTrue(archive.store_page(self.PAGE))
            self.assertTrue(archive.store_query(
                self.QUERY,
                self.SUBJECT,
                "standard",
                [self.PAGE]
            ))

            cached = archive.get_query(
                self.QUERY,
                self.SUBJECT,
                "standard"
            )

            self.assertEqual(len(cached["results"]), 1)
            self.assertEqual(
                cached["results"][0]["content"],
                self.PAGE["content"]
            )
            self.assertEqual(
                cached["results"][0]["archive_status"],
                "reused"
            )
            self.assertTrue(archive.is_recent(cached, 30))

            archive_files = list(Path(directory).rglob("*.json"))
            serialized = "\n".join(
                path.read_text(encoding="utf-8")
                for path in archive_files
            )
            self.assertNotIn(self.QUERY, serialized)
            self.assertNotIn("search_query", serialized)

    def test_archive_rejects_non_public_urls_and_snippet_only_records(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = PublicReferenceArchive(directory)

            self.assertFalse(archive.store_page({
                **self.PAGE,
                "url": "file:///private/data"
            }))
            self.assertFalse(archive.store_page({
                key: value
                for key, value in self.PAGE.items()
                if key != "content"
            }))
            self.assertIsNone(archive.get_page("file:///private/data"))

    def test_stale_archive_remains_available_but_is_not_fresh(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = PublicReferenceArchive(directory)
            archive.store_page(self.PAGE)
            archive.store_query(
                self.QUERY,
                self.SUBJECT,
                "standard",
                [self.PAGE]
            )
            query_path = next(
                (Path(directory) / "queries").glob("*.json")
            )
            record = json.loads(query_path.read_text(encoding="utf-8"))
            record["archived_at"] = "2020-01-01T00:00:00+00:00"
            query_path.write_text(json.dumps(record), encoding="utf-8")

            cached = archive.get_query(
                self.QUERY,
                self.SUBJECT,
                "standard"
            )

            self.assertIsNotNone(cached)
            self.assertFalse(archive.is_recent(cached, 30))

    def test_exact_query_archive_hit_avoids_search_and_scrape(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = PublicReferenceArchive(directory)
            archive.store_page(self.PAGE)
            archive.store_query(
                self.QUERY,
                self.SUBJECT,
                "standard",
                [self.PAGE]
            )
            provider = GenericEvidenceProvider.__new__(
                GenericEvidenceProvider
            )
            provider.reference_archive = archive
            provider.freshness_detector = FreshnessDetector()
            provider.max_pages = 15
            provider.max_search_queries = 5
            provider.web = Mock()
            provider.firecrawl = Mock()
            provider.social = Mock()
            provider.social_summary_builder = Mock()

            evidence = provider.get_context(
                self.QUERY,
                subject=self.SUBJECT
            )

            provider.web.search.assert_not_called()
            provider.firecrawl.health_check.assert_not_called()
            self.assertEqual(evidence["archive_mode"], "offline_reuse")
            self.assertTrue(evidence["archive_reused"])
            self.assertEqual(
                evidence["results"][0]["content"],
                self.PAGE["content"]
            )

    def test_current_query_never_uses_the_reference_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = PublicReferenceArchive(directory)
            archive.get_query = Mock(return_value={
                "results": [self.PAGE],
                "archived_at": "2026-10-01T00:00:00+00:00"
            })
            provider = GenericEvidenceProvider.__new__(
                GenericEvidenceProvider
            )
            provider.reference_archive = archive
            provider.freshness_detector = FreshnessDetector()
            provider.max_pages = 15
            provider.max_search_queries = 5
            provider.web = SimpleNamespace(search=lambda company, query: [])
            provider.firecrawl = SimpleNamespace(
                health_check=lambda: False
            )
            provider.social = SimpleNamespace(
                get_context=lambda **kwargs: {"results": [], "sources": []}
            )
            provider.social_summary_builder = SimpleNamespace(
                build=lambda results: {}
            )

            with patch.object(
                GenericEvidenceProvider,
                "_get_wikipedia_evidence",
                return_value=(None, {"status": "unavailable"})
            ):
                provider.get_context(
                    "What is the latest about Example Research?",
                    subject=self.SUBJECT
                )

            archive.get_query.assert_not_called()

    def test_old_snapshot_is_fallback_when_live_lookup_has_no_content(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = PublicReferenceArchive(directory)
            archive.store_page(self.PAGE)
            archive.store_query(
                self.QUERY,
                self.SUBJECT,
                "standard",
                [self.PAGE]
            )
            query_path = next(
                (Path(directory) / "queries").glob("*.json")
            )
            record = json.loads(query_path.read_text(encoding="utf-8"))
            record["archived_at"] = "2020-01-01T00:00:00+00:00"
            query_path.write_text(json.dumps(record), encoding="utf-8")

            provider = GenericEvidenceProvider.__new__(
                GenericEvidenceProvider
            )
            provider.reference_archive = archive
            provider.freshness_detector = FreshnessDetector()
            provider.max_pages = 15
            provider.max_search_queries = 5
            provider.web = SimpleNamespace(search=lambda company, query: [])
            provider.firecrawl = SimpleNamespace(
                health_check=lambda: False
            )
            provider.social = SimpleNamespace(
                get_context=lambda **kwargs: {"results": [], "sources": []}
            )
            provider.social_summary_builder = SimpleNamespace(
                build=lambda results: {}
            )

            with patch.object(
                GenericEvidenceProvider,
                "_get_wikipedia_evidence",
                return_value=(None, {"status": "unavailable"})
            ):
                evidence = provider.get_context(
                    self.QUERY,
                    subject=self.SUBJECT
                )

            self.assertEqual(evidence["archive_mode"], "offline_reuse")
            self.assertTrue(evidence["archive_reused"])
            self.assertEqual(
                evidence["results"][0]["content"],
                self.PAGE["content"]
            )


if __name__ == "__main__":
    unittest.main()
