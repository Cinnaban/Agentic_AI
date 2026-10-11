import sys
import logging
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