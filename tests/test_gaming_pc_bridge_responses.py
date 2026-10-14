import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import requests

from workers.gaming_pc_bridge import GamingPCBridge


class GamingPCBridgeResponseTests(unittest.TestCase):

    def make_bridge(self, response_payload):
        bridge = GamingPCBridge.__new__(GamingPCBridge)
        bridge.worker_name = "gaming_pc"
        response = Mock()
        response.json.return_value = response_payload
        response.raise_for_status.return_value = None
        bridge.session = Mock()
        bridge.session.post.return_value = response
        return bridge

    @staticmethod
    def work_package():
        return SimpleNamespace(
            job_id="test-job",
            companies=[{
                "name": "Intel",
                "ticker": "INTC",
                "entity_type": "stock"
            }],
            original_message="Evaluate INTC",
            required_agents={"quant": True},
            source="discord"
        )

    def test_null_json_response_becomes_explicit_quant_failure(self):
        bridge = self.make_bridge(None)

        result = bridge.submit_job(self.work_package())

        self.assertEqual(result["status"], "failed")
        self.assertEqual(
            result["failed_companies"][0]["ticker"],
            "INTC"
        )
        self.assertIn("expected a JSON object", result["failed_companies"][0]["error"])

    def test_missing_quant_results_are_not_reported_as_success(self):
        bridge = self.make_bridge({"status": "completed"})

        result = bridge.submit_job(self.work_package())

        self.assertEqual(result["status"], "failed")
        self.assertIn("results list", result["failed_companies"][0]["error"])

    def test_valid_quant_results_are_returned(self):
        expected = {"company": {"ticker": "INTC"}, "status": "completed"}
        bridge = self.make_bridge({"results": [expected]})

        result = bridge.submit_job(self.work_package())

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["results"], [expected])

    def test_connection_timeout_returns_actionable_worker_error(self):
        bridge = self.make_bridge({})
        bridge.session.post.side_effect = requests.ConnectTimeout(
            "private endpoint detail"
        )

        result = bridge.submit_job(self.work_package())

        self.assertEqual(result["status"], "failed")
        self.assertIn(
            "compute request timed out",
            result["error"]
        )
        self.assertIn(
            "worker is running and reachable",
            result["error"]
        )
        self.assertNotIn("private endpoint detail", result["error"])


if __name__ == "__main__":
    unittest.main()
