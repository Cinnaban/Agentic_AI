import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from workers.agent_executor import AgentExecutor


class QuantPriorityTests(unittest.TestCase):

    def test_quant_runs_before_market_context_collection(self):
        execution_order = []
        executor = AgentExecutor.__new__(AgentExecutor)
        executor.freshness_detector = SimpleNamespace(
            requires_live_data=lambda message: False
        )
        executor.quant_agent = SimpleNamespace(
            analyze=lambda work_package: (
                execution_order.append("quant") or {}
            )
        )
        executor.market_context_provider = SimpleNamespace(
            get_context=lambda *args, **kwargs: (
                execution_order.append("market_context") or {}
            )
        )
        executor.research_agent = Mock()
        executor.sentiment_agent = Mock()
        executor.risk_agent = Mock()
        executor.signal_reconciliation_agent = Mock()

        work_package = SimpleNamespace(
            companies=[
                {
                    "name": "NVIDIA",
                    "ticker": "NVDA",
                    "entity_type": "security"
                }
            ],
            required_agents={
                "quant": True,
                "research": False,
                "sentiment": False,
                "risk": False
            },
            original_message="Evaluate Nvidia"
        )

        result = executor.execute(work_package)

        self.assertEqual(
            execution_order,
            ["quant", "market_context"]
        )
        self.assertEqual(result["quant"], {})


if __name__ == "__main__":
    unittest.main()
