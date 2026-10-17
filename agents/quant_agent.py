import sys
import logging
from dataclasses import replace
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from workers.gaming_pc_bridge import GamingPCBridge
from configs.config import Config
from orchestrator.freshness_detector import FreshnessDetector
from shared_storage.storage_manager import StorageManager

class QuantAgent:

    def __init__(self):
        self.bridge = GamingPCBridge()
        self.storage = StorageManager()
        self.freshness_detector = FreshnessDetector()

    def analyze(
        self,
        work_package
    ):
        companies = getattr(work_package, "companies", [])
        if isinstance(companies, list) and len(companies) > 1:
            return self._analyze_each(work_package, companies)
        return self._analyze_single(work_package)

    def _analyze_each(self, work_package, companies):
        # One cached job per ticker, merged into a single package.
        results = []
        failed = []
        for company in companies:
            if not isinstance(company, dict) or not company.get("ticker"):
                continue
            sub_package = replace(work_package, companies=[company])
            outcome = self._analyze_single(sub_package)
            if not isinstance(outcome, dict):
                continue
            results.extend(outcome.get("results") or [])
            failed.extend(outcome.get("failed_companies") or [])
            if outcome.get("status") == "failed" and not outcome.get(
                "failed_companies"
            ):
                failed.append({
                    "company": company,
                    "ticker": company.get("ticker"),
                    "error": outcome.get("error", "Quant job failed")
                })
        if not results and failed:
            return {
                "job_id": work_package.job_id,
                "worker": self.bridge.worker_name,
                "status": "failed",
                "results": [],
                "failed_companies": failed,
                "error": "All Gaming PC quant requests failed: "
                + str(failed[0].get("error"))
            }
        return {
            "job_id": work_package.job_id,
            "worker": self.bridge.worker_name,
            "status": "partial" if failed else "completed",
            "results": results,
            "failed_companies": failed
        }

    def _analyze_single(
        self,
        work_package
    ):
        message = str(
            getattr(work_package, "original_message", "") or ""
        )
        fresh_request = self.freshness_detector.requires_live_data(message)
        cache_key = self.storage.build_cache_key({
            "companies": getattr(work_package, "companies", []),
            "required_agents": getattr(
                work_package,
                "required_agents",
                {}
            ),
            "request": " ".join(message.lower().split())
        })
        if not fresh_request:
            try:
                cached = self.storage.get_cached_data("quant", cache_key)
            except (OSError, ValueError, TypeError) as error:
                logging.warning("Quant cache read failed: %s", error)
            else:
                if cached is not None:
                    return cached

        result = self.bridge.submit_job(work_package)
        if (
            not fresh_request
            and isinstance(result, dict)
            and result.get("status") == "completed"
        ):
            ttl = (
                Config.QUANT_CACHE_TTL_HOURS
                * 60
                * 60
            )
            try:
                self.storage.set_cached_data(
                    "quant",
                    cache_key,
                    result,
                    ttl
                )
            except (OSError, ValueError, TypeError) as error:
                logging.warning("Quant cache write failed: %s", error)
        return result