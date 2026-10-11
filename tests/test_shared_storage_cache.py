import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from agents.quant_agent import QuantAgent
from configs.config import Config
from data.market_context_provider import MarketContextProvider
from data.providers.portfolio_context_provider import PortfolioContextProvider
from shared_storage.storage_manager import StorageManager


class SharedStorageCacheTests(unittest.TestCase):

    def make_storage(self, directory):
        storage = StorageManager.__new__(StorageManager)
        storage._cache_lock = threading.RLock()
        storage.directories = {"cache": Path(directory)}
        Path(directory).mkdir(parents=True, exist_ok=True)
        return storage

    def test_cache_is_namespaced_and_expires_by_ttl(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = self.make_storage(directory)
            storage.set_cached_data(
                "quant",
                "NVDA",
                {"score": 5},
                3600
            )

            self.assertEqual(
                storage.get_cached_data("quant", "NVDA"),
                {"score": 5}
            )
            self.assertIsNone(
                storage.get_cached_data("financial", "NVDA")
            )

            cache_path = next(Path(directory).glob("quant-*.json"))
            record = json.loads(cache_path.read_text(encoding="utf-8"))
            record["expires_at"] = (
                datetime.now(timezone.utc) - timedelta(seconds=1)
            ).isoformat()
            cache_path.write_text(
                json.dumps(record),
                encoding="utf-8"
            )

            self.assertIsNone(
                storage.get_cached_data("quant", "NVDA")
            )
            self.assertFalse(cache_path.exists())

    def test_cleanup_removes_expired_entries_but_preserves_live_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = self.make_storage(directory)
            storage.set_cached_data(
                "portfolio",
                "live",
                {"holdings": 2},
                3600
            )
            storage.set_cached_data(
                "portfolio",
                "expired",
                {"holdings": 1},
                3600
            )
            expired_path = StorageManager._cache_path(
                Path(directory),
                "portfolio",
                "expired"
            )
            record = json.loads(expired_path.read_text(encoding="utf-8"))
            record["expires_at"] = (
                datetime.now(timezone.utc) - timedelta(days=1)
            ).isoformat()
            expired_path.write_text(json.dumps(record), encoding="utf-8")

            result = storage.cleanup_expired_cache()

            self.assertEqual(result["deleted"], 1)
            self.assertFalse(expired_path.exists())
            self.assertEqual(
                storage.get_cached_data("portfolio", "live"),
                {"holdings": 2}
            )

    def test_cache_ttl_is_capped_at_three_months(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = self.make_storage(directory)
            storage.set_cached_data(
                "financial",
                "NVDA",
                {"price": 1},
                365 * 24 * 60 * 60
            )
            cache_path = next(Path(directory).glob("financial-*.json"))
            record = json.loads(cache_path.read_text(encoding="utf-8"))
            created = datetime.fromisoformat(record["created_at"])
            expires = datetime.fromisoformat(record["expires_at"])

            self.assertLessEqual(
                expires - created,
                timedelta(days=Config.CACHE_MAX_RETENTION_DAYS)
            )

    def test_cleanup_enforces_max_age_even_for_long_expiration(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = self.make_storage(directory)
            storage.set_cached_data(
                "financial",
                "NVDA",
                {"price": 1},
                3600
            )
            cache_path = next(Path(directory).glob("financial-*.json"))
            record = json.loads(cache_path.read_text(encoding="utf-8"))
            record["created_at"] = (
                datetime.now(timezone.utc)
                - timedelta(days=Config.CACHE_MAX_RETENTION_DAYS + 1)
            ).isoformat()
            record["expires_at"] = (
                datetime.now(timezone.utc) + timedelta(days=30)
            ).isoformat()
            cache_path.write_text(json.dumps(record), encoding="utf-8")

            result = storage.cleanup_expired_cache()

            self.assertEqual(result["deleted"], 1)
            self.assertFalse(cache_path.exists())

    def test_expiration_sweep_runs_periodically_during_long_lived_process(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = self.make_storage(directory)
            storage._last_cache_cleanup = (
                datetime.now(timezone.utc)
                - timedelta(
                    hours=Config.CACHE_CLEANUP_INTERVAL_HOURS + 1
                )
            )
            storage.cleanup_expired_cache = Mock(
                return_value={"deleted": 1}
            )

            storage._maybe_cleanup_expired_cache()

            storage.cleanup_expired_cache.assert_called_once()
            self.assertLess(
                datetime.now(timezone.utc) - storage._last_cache_cleanup,
                timedelta(seconds=1)
            )

    def test_quant_results_are_reused_but_live_requests_bypass_cache(self):
        agent = QuantAgent.__new__(QuantAgent)
        agent.storage = SimpleNamespace(
            build_cache_key=StorageManager.build_cache_key,
            get_cached_data=Mock(return_value={"cached": True}),
            set_cached_data=Mock()
        )
        agent.bridge = SimpleNamespace(submit_job=Mock(
            return_value={"fresh": True}
        ))
        agent.freshness_detector = SimpleNamespace(
            requires_live_data=lambda message: "today" in message.lower()
        )
        package = SimpleNamespace(
            companies=[{"ticker": "NVDA", "entity_type": "stock"}],
            required_agents={"quant": True},
            original_message="Analyze Nvidia"
        )

        cached_result = agent.analyze(package)
        self.assertEqual(cached_result, {"cached": True})
        agent.bridge.submit_job.assert_not_called()

        package.original_message = "Analyze Nvidia today"
        fresh_result = agent.analyze(package)
        self.assertEqual(fresh_result, {"fresh": True})
        agent.bridge.submit_job.assert_called_once_with(package)
        agent.storage.set_cached_data.assert_not_called()

    def test_financial_and_portfolio_context_use_shared_cache(self):
        cache = {}

        def cache_get(namespace, key):
            return cache.get((namespace, key))

        def cache_set(namespace, key, value, ttl):
            cache[(namespace, key)] = value

        storage = SimpleNamespace(
            build_cache_key=StorageManager.build_cache_key,
            get_cached_data=cache_get,
            set_cached_data=cache_set
        )

        market = MarketContextProvider.__new__(MarketContextProvider)
        market.storage = storage
        market._get_context_uncached = Mock(
            return_value={"financial_data": {"price": 10}}
        )

        first = market.get_context(
            {"ticker": "NVDA"},
            quant_data={"score": 1},
            original_message="Analyze Nvidia"
        )
        second = market.get_context(
            {"ticker": "NVDA"},
            quant_data={"score": 1},
            original_message="Analyze Nvidia"
        )
        self.assertEqual(first, second)
        market._get_context_uncached.assert_called_once()

        portfolio = PortfolioContextProvider.__new__(
            PortfolioContextProvider
        )
        portfolio.storage = storage
        portfolio._get_context_uncached = Mock(
            return_value={"status": "available", "holdings": []}
        )
        holdings = [{"ticker": "NVDA", "weight": 100, "entity_type": "stock"}]
        portfolio.get_context(holdings)
        portfolio.get_context(holdings)
        portfolio._get_context_uncached.assert_called_once()

    def test_live_portfolio_context_bypasses_cache(self):
        storage = SimpleNamespace(
            build_cache_key=StorageManager.build_cache_key,
            get_cached_data=Mock(return_value={"status": "stale"}),
            set_cached_data=Mock()
        )
        portfolio = PortfolioContextProvider.__new__(
            PortfolioContextProvider
        )
        portfolio.storage = storage
        portfolio._get_context_uncached = Mock(
            return_value={"status": "available", "holdings": []}
        )

        result = portfolio.get_context(
            [{"ticker": "NVDA", "weight": 100, "entity_type": "stock"}],
            original_message="Show my portfolio today"
        )

        self.assertEqual(result["status"], "available")
        storage.get_cached_data.assert_not_called()
        storage.set_cached_data.assert_not_called()
        portfolio._get_context_uncached.assert_called_once_with(
            [{"ticker": "NVDA", "weight": 100, "entity_type": "stock"}],
            None,
            True
        )

    def test_financial_cache_excludes_volatile_evidence(self):
        cache = {}
        storage = SimpleNamespace(
            build_cache_key=StorageManager.build_cache_key,
            get_cached_data=lambda namespace, key: cache.get(
                (namespace, key)
            ),
            set_cached_data=lambda namespace, key, value, ttl: cache.update({
                (namespace, key): value
            })
        )
        market = MarketContextProvider.__new__(MarketContextProvider)
        market.storage = storage
        market._get_context_uncached = Mock(return_value={
            "financial_data": {"price": 10},
            "news": [{"headline": "latest headline"}],
            "social_context": {"results": [{"text": "recent post"}]},
            "live_market_context": {"available": True, "results": ["live"]}
        })

        market.get_context(
            {"ticker": "NVDA"},
            original_message="Analyze Nvidia"
        )

        cached = next(iter(cache.values()))
        self.assertIn("financial_data", cached)
        self.assertNotIn("news", cached)
        self.assertNotIn("social_context", cached)
        self.assertNotIn("live_market_context", cached)

    def test_live_financial_context_bypasses_cached_data(self):
        storage = SimpleNamespace(
            build_cache_key=StorageManager.build_cache_key,
            get_cached_data=Mock(return_value={"stale": True}),
            set_cached_data=Mock()
        )
        market = MarketContextProvider.__new__(MarketContextProvider)
        market.storage = storage
        market._get_context_uncached = Mock(
            return_value={"live": True}
        )

        result = market.get_context(
            {"ticker": "NVDA"},
            original_message="What is Nvidia doing today?",
            requires_live_data=True
        )

        self.assertEqual(result, {"live": True})
        storage.get_cached_data.assert_not_called()
        storage.set_cached_data.assert_not_called()


if __name__ == "__main__":
    unittest.main()
