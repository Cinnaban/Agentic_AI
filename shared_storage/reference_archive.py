import hashlib
import json
import logging
import os
import sys
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from configs.config import Config


class PublicReferenceArchive:

    MAX_PAGE_BYTES = 2 * 1024 * 1024

    def __init__(self, directory=None):
        configured_directory = (
            directory or Config.PUBLIC_REFERENCE_ARCHIVE_DIRECTORY
        )
        self.directory = (
            Path(configured_directory)
            if configured_directory
            else None
        )
        self._lock = threading.RLock()
        self._available = self.directory is not None
        if self.directory is None:
            self.pages_directory = None
            self.queries_directory = None
            return

        self.pages_directory = self.directory / "pages"
        self.queries_directory = self.directory / "queries"
        try:
            if (
                sys.platform == "darwin"
                and self.directory.is_absolute()
                and len(self.directory.parts) > 2
                and self.directory.parts[1] == "Volumes"
            ):
                volume = Path("/Volumes") / self.directory.parts[2]
                if not volume.is_mount():
                    raise OSError(
                        f"Gaming PC volume is not mounted: {volume}"
                    )
            self.pages_directory.mkdir(parents=True, exist_ok=True)
            self.queries_directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            self._available = False
            logging.warning(
                "Public reference archive is unavailable at %s: %s",
                self.directory,
                error
            )

    @staticmethod
    def _normalize_url(url):
        if not isinstance(url, str):
            return None
        try:
            parsed = urlsplit(url.strip())
            if (
                parsed.scheme.lower() not in {"http", "https"}
                or not parsed.hostname
            ):
                return None
            return urlunsplit((
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path.rstrip("/"),
                "",
                ""
            ))
        except ValueError:
            return None

    @staticmethod
    def _digest(value):
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _page_path(self, url):
        normalized_url = self._normalize_url(url)
        if not normalized_url:
            return None
        return self.pages_directory / (
            self._digest(normalized_url) + ".json"
        )

    @classmethod
    def _query_key(cls, query, subject, evidence_depth):
        return json.dumps(
            {
                "query": " ".join(str(query or "").lower().split()),
                "subject": " ".join(str(subject or "").lower().split()),
                "evidence_depth": evidence_depth
            },
            sort_keys=True,
            separators=(",", ":")
        )

    def _atomic_write(self, path, record):
        if not self._available:
            return False
        temporary_path = None
        try:
            with self._lock:
                path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=path.parent,
                    prefix=".archive-write-",
                    suffix=".tmp",
                    delete=False
                ) as archive_file:
                    temporary_path = Path(archive_file.name)
                    json.dump(
                        record,
                        archive_file,
                        ensure_ascii=False,
                        allow_nan=False
                    )
                    archive_file.flush()
                    os.fsync(archive_file.fileno())
                os.replace(temporary_path, path)
            return True
        except (OSError, TypeError, ValueError) as error:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            logging.warning(
                "Could not write public reference archive record %s: %s",
                path.name,
                error
            )
            return False

    @staticmethod
    def _read_record(path):
        if not path.is_file():
            return None
        try:
            with path.open("r", encoding="utf-8") as archive_file:
                return json.load(archive_file)
        except (OSError, ValueError, TypeError) as error:
            logging.warning(
                "Could not read public reference archive record %s: %s",
                path.name,
                error
            )
            return None

    def store_page(self, page):
        if not self._available or not isinstance(page, dict):
            return False

        url = self._normalize_url(page.get("url"))
        content = page.get("content")
        if (
            not url
            or not isinstance(content, str)
            or not content.strip()
        ):
            return False

        fields = (
            "url",
            "title",
            "published_at",
            "source",
            "source_host",
            "source_role",
            "source_type",
            "page_kind",
            "evidence_level",
            "content",
            "summary"
        )
        archived_page = {
            field: page[field]
            for field in fields
            if field in page and isinstance(
                page[field],
                (str, int, float, bool, type(None))
            )
        }
        archived_page["url"] = url
        content_bytes = content.encode("utf-8")
        if len(content_bytes) > self.MAX_PAGE_BYTES:
            logging.warning(
                "Skipping oversized public reference page %s",
                url
            )
            return False

        now = datetime.now(timezone.utc).isoformat()
        record = {
            "schema_version": 1,
            "source_url": url,
            "retrieved_at": page.get(
                "content_retrieved_at",
                page.get("retrieved_at", now)
            ),
            "archived_at": now,
            "page": archived_page
        }
        return self._atomic_write(self._page_path(url), record)

    def get_page(self, url):
        if not self._available:
            return None
        path = self._page_path(url)
        if path is None or not path.is_file():
            return None
        record = self._read_record(path)
        if not isinstance(record, dict):
            return None
        page = record.get("page")
        if not isinstance(page, dict) or not page.get("content"):
            return None
        page = dict(page)
        page["archive_status"] = "reused"
        page["archived_at"] = record.get("archived_at")
        page["content_retrieved_at"] = record.get("retrieved_at")
        return page

    def store_query(self, query, subject, evidence_depth, results):
        if not self._available or not isinstance(results, list):
            return False
        source_urls = []
        for result in results:
            if not isinstance(result, dict):
                continue
            url = self._normalize_url(result.get("url"))
            if (
                url
                and isinstance(result.get("content"), str)
                and result["content"].strip()
                and self._page_path(url).is_file()
                and url not in source_urls
            ):
                source_urls.append(url)
        if not source_urls:
            return False

        archived_at = datetime.now(timezone.utc).isoformat()
        record = {
            "schema_version": 1,
            "source_urls": source_urls,
            "archived_at": archived_at
        }
        query_digest = self._digest(
            self._query_key(query, subject, evidence_depth)
        )
        return self._atomic_write(
            self.queries_directory / f"{query_digest}.json",
            record
        )

    def get_query(self, query, subject, evidence_depth):
        if not self._available:
            return None
        query_digest = self._digest(
            self._query_key(query, subject, evidence_depth)
        )
        record = self._read_record(
            self.queries_directory / f"{query_digest}.json"
        )
        if not isinstance(record, dict):
            return None

        results = []
        for url in record.get("source_urls", []):
            page = self.get_page(url)
            if page is None:
                return None
            results.append(page)
        if not results:
            return None
        return {
            "results": results,
            "archived_at": record.get("archived_at")
        }

    @staticmethod
    def is_recent(record, max_age_days):
        if not isinstance(record, dict):
            return False
        archived_at = record.get("archived_at")
        try:
            timestamp = datetime.fromisoformat(archived_at)
        except (TypeError, ValueError):
            return False
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - timestamp <= timedelta(
            days=max_age_days
        )
