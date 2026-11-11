import unittest
from unittest.mock import Mock

from agents.research_agent import ResearchAgent
from job_queue.work_package import WorkPackage
from orchestrator.hermes import Hermes
from workers.agent_executor import AgentExecutor


class ComparisonExecutionOrderTests(unittest.TestCase):
    def test_comparison_research_limitations_are_visible(self):
        issues = Hermes._comparison_research_limitations({
            "AMZN": {"research": "Research analysis unavailable: Ollama request timed out."},
            "NVDA": {"research": "Research output was truncated by the model's generation limit."},
            "AAPL": {"research": "Complete research."},
        })
        self.assertEqual(len(issues), 2)
        self.assertIn("AMZN", issues[0])
        self.assertIn("truncated", issues[1])

    def test_grouped_agents_keep_each_company_evidence(self):
        executor = AgentExecutor.__new__(AgentExecutor)
        calls = []
        executor.freshness_detector = Mock()
        executor.freshness_detector.requires_live_data.return_value = False
        executor.quant_agent = Mock()
        executor.quant_agent.analyze.return_value = {
            "status": "completed",
            "results": [
                {"company": {"ticker": ticker}, "analysis": {"ticker": ticker}}
                for ticker in ("AMZN", "NVDA")
            ],
        }
        executor.market_context_provider = Mock()
        executor.market_context_provider.get_context.side_effect = (
            lambda company, **kwargs: {"ticker": company["ticker"]}
        )
        executor.research_agent = Mock()
        executor.research_agent.analyze.side_effect = (
            lambda company, market_context, comparison: calls.append(
                ("research", company["ticker"], market_context["ticker"])
            ) or ("research" if comparison else "unexpected")
        )
        executor.signal_reconciliation_agent = Mock()
        executor.signal_reconciliation_agent.analyze.side_effect = (
            lambda quant: {"ticker": quant["company"]["ticker"]}
        )
        executor.risk_agent = Mock()
        executor.risk_agent.analyze.side_effect = (
            lambda company, quant_data, reconciliation_data: calls.append(
                ("risk", company["ticker"], reconciliation_data["ticker"])
            ) or {"status": "completed"}
        )
        executor.sentiment_agent = Mock()
        executor.sentiment_agent.analyze.side_effect = (
            lambda company, market_context: calls.append(
                ("sentiment", company["ticker"], market_context["ticker"])
            ) or {"status": "completed"}
        )
        package = WorkPackage(
            job_id="test", companies=[{"ticker": "AMZN"}, {"ticker": "NVDA"}],
            required_agents={"quant": True, "research": True, "risk": True, "sentiment": True},
            original_message="Compare AMZN to NVDA", source="test"
        )
        result = executor._execute_multi_company(package)
        self.assertEqual(calls, [
            ("research", "AMZN", "AMZN"), ("research", "NVDA", "NVDA"),
            ("risk", "AMZN", "AMZN"), ("risk", "NVDA", "NVDA"),
            ("sentiment", "AMZN", "AMZN"), ("sentiment", "NVDA", "NVDA"),
        ])
        for ticker in ("AMZN", "NVDA"):
            self.assertEqual(result["company_results"][ticker]["quant"]["company"]["ticker"], ticker)
            self.assertEqual(result["company_results"][ticker]["risk"]["status"], "completed")

    def test_no_research_no_quant_does_not_leave_reconciliation_unbound(self):
        executor = AgentExecutor.__new__(AgentExecutor)
        executor.market_context_provider = Mock()
        executor.market_context_provider.get_context.return_value = {}
        package = WorkPackage(
            job_id="test", companies=[{"ticker": "AMZN"}, {"ticker": "NVDA"}],
            required_agents={"research": False, "quant": False, "risk": False},
            original_message="Compare AMZN to NVDA", source="test"
        )
        executor.freshness_detector = Mock()
        executor.freshness_detector.requires_live_data.return_value = False
        result = executor._execute_multi_company(package)
        self.assertIsNone(result["company_results"]["AMZN"]["signal_reconciliation"])


class ResearchRetryTests(unittest.TestCase):
    def test_timeout_is_not_retried(self):
        agent = ResearchAgent()
        agent.ollama = Mock()
        agent.ollama.generate.return_value = {
            "status": "failed", "error": "Ollama request timed out"
        }
        result = agent.analyze({"ticker": "AMZN"}, {})
        self.assertIn("Ollama request timed out", result)
        self.assertEqual(agent.ollama.generate.call_count, 1)

    def test_empty_model_response_is_retried(self):
        agent = ResearchAgent()
        agent.ollama = Mock()
        agent.ollama.generate.side_effect = [
            {"response": ""}, {"response": "A grounded research report."}
        ]
        result = agent.analyze({"ticker": "AMZN"}, {})
        self.assertEqual(result, "A grounded research report.")
        self.assertEqual(agent.ollama.generate.call_count, 2)

    def test_comparison_limits_output_and_reports_truncation(self):
        agent = ResearchAgent()
        agent.ollama = Mock()
        agent.ollama.generate.return_value = {
            "response": "Partial research.", "done_reason": "length"
        }
        result = agent.analyze({"ticker": "AMZN"}, {}, comparison=True)
        self.assertIn("truncated", result)
        self.assertEqual(agent.ollama.generate.call_args.kwargs["options"]["num_predict"], 768)

    def test_comparison_prompt_retains_evidence_and_grounding(self):
        agent = ResearchAgent()
        agent.ollama = Mock()
        agent.ollama.generate.return_value = {"response": "Complete research."}
        context = {
            "financial_data": {"example_metric": 123},
            "source_status": {"news": "unavailable"},
        }
        agent.analyze({"ticker": "AMZN"}, context, comparison=True)
        prompt = agent.ollama.generate.call_args.args[0]
        self.assertIn('"example_metric":123', prompt)
        self.assertIn('"news":"unavailable"', prompt)
        self.assertIn("filing metadata does not prove", prompt)
        self.assertIn("Social discussion is unverified", prompt)
        self.assertIn("Do not invent financial values", prompt)


if __name__ == "__main__":
    unittest.main()
