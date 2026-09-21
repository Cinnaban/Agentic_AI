import json

from pathlib import Path
from configs.config import Config
from datetime import datetime, timedelta

class StorageManager:

    def __init__(self):

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
                )
        }

        self._ensure_directories()

    def _ensure_directories(self):

        for directory in (
            self.directories.values()
        ):

            directory.mkdir(
                parents=True,
                exist_ok=True
            )
    
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