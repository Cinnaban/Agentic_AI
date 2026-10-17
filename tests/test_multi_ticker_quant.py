import unittest
from unittest.mock import MagicMock

from agents.quant_agent import QuantAgent
from job_queue.work_package import WorkPackage
from orchestrator.financial_metric_builder import FinancialMetricBuilder


def item(ticker):
    return {
        "company": {"ticker": ticker},
        "analysis": {"recommendation": "Bullish", "prediction_pct": 1.5},
    }


class MultiTickerQuantTests(unittest.TestCase):

    def make_agent(self, fail=()):
        agent = QuantAgent.__new__(QuantAgent)
        agent.bridge = MagicMock(worker_name="gaming")
        agent.storage = MagicMock()
        agent.storage.build_cache_key.side_effect = lambda payload: str(payload)
        agent.storage.get_cached_data.return_value = None
        agent.freshness_detector = MagicMock()
        agent.freshness_detector.requires_live_data.return_value = False

        def submit(package):
            ticker = package.companies[0]["ticker"]
            if ticker in fail:
                return {"status": "failed", "results": [],
                        "failed_companies": [{"ticker": ticker, "error": "x"}]}
            return {"status": "completed", "results": [item(ticker)],
                    "failed_companies": []}

        agent.bridge.submit_job.side_effect = submit
        return agent

    def package(self, tickers):
        return WorkPackage(
            job_id="j",
            companies=[{"ticker": t} for t in tickers],
            required_agents={"quant": True},
            original_message="Compare " + ", ".join(tickers),
            source="test",
        )

    def test_every_ticker_gets_a_quant_job_and_cache_entry(self):
        agent = self.make_agent()
        result = agent.analyze(self.package(["MU", "WDC", "STX", "P"]))
        self.assertEqual(
            [r["company"]["ticker"] for r in result["results"]],
            ["MU", "WDC", "STX", "P"],
        )
        self.assertEqual(agent.bridge.submit_job.call_count, 4)
        self.assertEqual(agent.storage.set_cached_data.call_count, 4)

    def test_partial_failure_keeps_other_tickers(self):
        agent = self.make_agent(fail={"WDC"})
        result = agent.analyze(self.package(["MU", "WDC"]))
        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(result["results"]), 1)

    def test_metric_builder_reads_single_item_quant(self):
        metrics = FinancialMetricBuilder().build_comparison(
            {"MU": {"quant": item("MU")}, "P": {"quant": item("P")}}
        )
        self.assertTrue(metrics["MU"])
        self.assertTrue(metrics["P"])


if __name__ == "__main__":
    unittest.main()
