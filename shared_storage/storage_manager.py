import json
import hashlib
import logging
import os
import re
import tempfile
import threading

from pathlib import Path
from configs.config import Config
from datetime import datetime, timedelta, timezone

class StorageManager:

    def __init__(self):

        self._cache_lock = threading.RLock()
        self.directories = {
            "incoming":
                Path(
                    Config.JOB_INCOMING_DIRECTORY
                ),

            "processing":
                Path(
                    Config.JOB_PROCESSING_DIRECTORY
                ),

            "completed":
                Path(
                    Config.JOB_COMPLETED_DIRECTORY
                ),

            "failed":
                Path(
                    Config.JOB_FAILED_DIRECTORY
                ),

            "archive":
                Path(
                    Config.JOB_ARCHIVE_DIRECTORY
                ),

            "temp":
                Path(
                    Config.JOB_TEMP_DIRECTORY
                ),
            "cache":
                Path(
                    Config.CACHE_DIRECTORY
                )
        }

        self._ensure_directories()
        self.cleanup_expired_cache()
        self._last_cache_cleanup = datetime.now(timezone.utc)

    def _ensure_directories(self):

        for directory in (
            self.directories.values()
        ):

            directory.mkdir(
                parents=True,
                exist_ok=True
            )
        self.directories["cache"].chmod(0o700)
    
    def create_job_record(
        self,
        job_id,
        data
    ):

        record = {
            "job_id": job_id,
            "status": "incoming",
            "created_at":
                datetime.now().isoformat(),
            "updated_at":
                datetime.now().isoformat(),
            "data": data
        }

        path = (
            self.directories["incoming"]
            / f"{job_id}.json"
        )

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                record,
                file,
                indent=2
            )

        return path

    def update_job_record(
        self,
        job_id,
        status,
        updates=None
    ):

        directory = self.directories.get(
            status
        )

        if directory is None:
            return None

        path = (
            directory
            / f"{job_id}.json"
        )

        if not path.exists():
            return None

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            record = json.load(
                file
            )

        record["status"] = status
        record["updated_at"] = (
            datetime.now().isoformat()
        )

        if updates:

            record["data"].update(
                updates
            )

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                record,
                file,
                indent=2
            )

        return path
    
    def move_job(
            self,
            job_id,
            from_status,
            to_status
        ):
    
            source = (
                self.directories[from_status]
                / f"{job_id}.json"
            )
    
            destination = (
                self.directories[to_status]
                / f"{job_id}.json"
            )
    
            if not source.exists():

                raise FileNotFoundError(
                    f"Job record not found in "
                    f"{from_status}: {job_id}"
                )    
    
            source.replace(
                destination
            )
            self.update_job_record(
                job_id=job_id,
                status=to_status
            )
    
            return destination
        
        
    def find_job(
        self,
        job_id
    ):

        search_statuses = [
            "incoming",
            "processing",
            "completed",
            "failed",
            "archive"
        ]

        for status in search_statuses:

            path = (
                self.directories[status]
                / f"{job_id}.json"
            )

            if path.exists():

                return {
                    "status": status,
                    "path": path
                }

        return None
    
    def fail_job(
        self,
        job_id,
        updates=None
    ):

        job = self.find_job(
            job_id
        )

        if job is None:
            return None

        current_status = job[
            "status"
        ]

        if updates:

            self.update_job_record(
                job_id=job_id,
                status=current_status,
                updates=updates
            )

        if current_status == "failed":

            return job["path"]

        return self.move_job(
            job_id=job_id,
            from_status=current_status,
            to_status="failed"
        )
        
    def archive_job(
        self,
        job_id
    ):

        job = self.find_job(
            job_id
        )

        if job is None:
            return None

        current_status = job[
            "status"
        ]

        if current_status == "archive":
            return job["path"]

        return self.move_job(
            job_id=job_id,
            from_status=current_status,
            to_status="archive"
        )
# Age Detection
    def is_older_than(
        self,
        path,
        days
    ):

        modified_time = (
            datetime.fromtimestamp(
                path.stat().st_mtime
            )
        )

        cutoff = (
            datetime.now()
            - timedelta(
                days=days
            )
        )

        return (
            modified_time < cutoff
        )
# LifeCycle Cleanup
    def cleanup_old_jobs(
        self
    ):

        if not Config.ENABLE_STORAGE_CLEANUP:
            return {
                "archived": 0,
                "deleted": 0
            }

        archived = 0
        deleted = 0
# Archive old completed jobs
        completed_directory = (
            self.directories["completed"]
        )

        for path in completed_directory.glob(
            "*.json"
        ):

            if self.is_older_than(
                path,
                Config.COMPLETED_JOB_RETENTION_DAYS
            ):

                result = self.archive_job(
                    path.stem
                )

                if result is not None:
                    archived += 1

# Archive old failed jobs
        failed_directory = (
            self.directories["failed"]
        )

        for path in failed_directory.glob(
            "*.json"
        ):

            if self.is_older_than(
                path,
                Config.FAILED_JOB_RETENTION_DAYS
            ):

                result = self.archive_job(
                    path.stem
                )

                if result is not None:
                    archived += 1
                    
# Delete expired archive records
        archive_directory = (
            self.directories["archive"]
        )

        for path in archive_directory.glob(
            "*.json"
        ):

            if self.is_older_than(
                path,
                Config.ARCHIVE_RETENTION_DAYS
            ):

                path.unlink()

                deleted += 1

# Delete expired temp files
        temp_directory = (
            self.directories["temp"]
        )

        for path in temp_directory.iterdir():

            if (
                path.is_file()
                and self.is_older_than(
                    path,
                    Config.TEMP_RETENTION_DAYS
                )
            ):

                path.unlink()

                deleted += 1
        
        return {
            "archived": archived,
            "deleted": deleted
        }

    @staticmethod
    def _cache_path(directory, namespace, key):
        if not isinstance(namespace, str) or not re.fullmatch(
            r"[a-z][a-z0-9_-]{0,63}",
            namespace
        ):
            raise ValueError("Cache namespace must be a lowercase identifier")
        if not isinstance(key, str) or not key:
            raise ValueError("Cache key must be a non-empty string")
        key_hash = hashlib.sha256(
            key.encode("utf-8")
        ).hexdigest()
        return directory / f"{namespace}-{key_hash}.json"

    @staticmethod
    def build_cache_key(value):
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str
        )

    def get_cached_data(self, namespace, key):
        self._maybe_cleanup_expired_cache()
        path = self._cache_path(
            self.directories["cache"],
            namespace,
            key
        )
        with self._cache_lock:
            if not path.is_file():
                return None
            try:
                with path.open("r", encoding="utf-8") as cache_file:
                    record = json.load(cache_file)
                expires_at = datetime.fromisoformat(
                    record["expires_at"]
                )
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
            except (OSError, ValueError, KeyError, TypeError) as error:
                logging.warning(
                    "Removing unreadable cache record %s: %s",
                    path.name,
                    error
                )
                path.unlink(missing_ok=True)
                return None

            if expires_at <= datetime.now(timezone.utc):
                path.unlink(missing_ok=True)
                return None
            return record.get("value")

    def set_cached_data(
        self,
        namespace,
        key,
        value,
        ttl_seconds
    ):
        self._maybe_cleanup_expired_cache()
        path = self._cache_path(
            self.directories["cache"],
            namespace,
            key
        )
        if (
            not isinstance(ttl_seconds, (int, float))
            or ttl_seconds <= 0
        ):
            raise ValueError("Cache TTL must be a positive number of seconds")
        max_ttl = (
            Config.CACHE_MAX_RETENTION_DAYS
            * 24
            * 60
            * 60
        )
        ttl_seconds = min(ttl_seconds, max_ttl)
        now = datetime.now(timezone.utc)
        record = {
            "namespace": namespace,
            "created_at": now.isoformat(),
            "expires_at": (
                now + timedelta(seconds=ttl_seconds)
            ).isoformat(),
            "value": value
        }

        with self._cache_lock:
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=path.parent,
                    prefix=".cache-write-",
                    suffix=".tmp",
                    delete=False
                ) as cache_file:
                    temp_path = Path(cache_file.name)
                    json.dump(
                        record,
                        cache_file,
                        ensure_ascii=False,
                        allow_nan=False
                    )
                    cache_file.flush()
                    os.fsync(cache_file.fileno())
                os.replace(temp_path, path)
            except (OSError, TypeError, ValueError):
                if temp_path is not None:
                    temp_path.unlink(missing_ok=True)
                raise
        return path

    def _maybe_cleanup_expired_cache(self):
        now = datetime.now(timezone.utc)
        last_cleanup = getattr(self, "_last_cache_cleanup", None)
        interval = timedelta(
            hours=Config.CACHE_CLEANUP_INTERVAL_HOURS
        )
        if last_cleanup is None or now - last_cleanup >= interval:
            self.cleanup_expired_cache()
            self._last_cache_cleanup = now

    def cleanup_expired_cache(self):
        cache_directory = self.directories["cache"]
        now = datetime.now(timezone.utc)
        deleted = 0
        with self._cache_lock:
            for path in cache_directory.iterdir():
                if not path.is_file():
                    continue
                if path.suffix == ".tmp":
                    if self.is_older_than(
                        path,
                        Config.TEMP_RETENTION_DAYS
                    ):
                        path.unlink()
                        deleted += 1
                    continue
                if path.suffix != ".json":
                    continue
                try:
                    with path.open("r", encoding="utf-8") as cache_file:
                        record = json.load(cache_file)
                    expires_at = datetime.fromisoformat(
                        record["expires_at"]
                    )
                    created_at = datetime.fromisoformat(
                        record["created_at"]
                    )
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(
                            tzinfo=timezone.utc
                        )
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(
                            tzinfo=timezone.utc
                        )
                except (OSError, ValueError, KeyError, TypeError) as error:
                    logging.warning(
                        "Removing unreadable cache record %s: %s",
                        path.name,
                        error
                    )
                    path.unlink(missing_ok=True)
                    deleted += 1
                    continue
                max_age = timedelta(
                    days=Config.CACHE_MAX_RETENTION_DAYS
                )
                if (
                    expires_at <= now
                    or created_at + max_age <= now
                ):
                    path.unlink()
                    deleted += 1
        return {"deleted": deleted}