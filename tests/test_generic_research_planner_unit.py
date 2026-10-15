import json
import unittest
from unittest.mock import Mock

from orchestrator.generic_research_planner import GenericResearchPlanner


class GenericResearchPlannerTests(unittest.TestCase):

    def test_planner_preserves_multi_topic_scope_and_task_type(self):
        planner = GenericResearchPlanner()
        planner.ollama = Mock()
        planner.ollama.generate.return_value = {
            "response": json.dumps({
                "intent": "explanation",
                "task_type": "comparison",
                "research_scope": (
                    "Explain how MOBA, FPS, and RTS gaming genres differ."
                ),
                "queries": [
                    "MOBA FPS RTS game genres gameplay differences",
                    "MOBA FPS RTS genre definitions from game references"
                ],
                "requested_dimensions": [
                    "genre definitions",
                    "gameplay differences"
                ]
            })
        }

        question = "Explain MOBA gaming to FPS and RTS gaming"
        plan = planner.plan(question)
        prompt = planner.ollama.generate.call_args.args[0]

        self.assertEqual(plan["task_type"], "comparison")
        self.assertEqual(plan["evidence_depth"], "deep")
        self.assertIn("MOBA, FPS, and RTS", plan["research_scope"])
        self.assertEqual(len(plan["queries"]), 2)
        self.assertIn("Keep every named subject or concept", prompt)
        self.assertIn("Questions may concern any public-information", prompt)
        self.assertIn("research several meaningful dimensions", prompt)

    def test_explicit_brief_request_keeps_summary_evidence_depth(self):
        planner = GenericResearchPlanner()
        planner.ollama = Mock()
        planner.ollama.generate.return_value = {
            "response": json.dumps({
                "task_type": "comparison",
                "research_scope": "Briefly compare two racing series.",
                "queries": ["Racing series comparison"]
            })
        }

        plan = planner.plan("Briefly compare NASCAR and Formula One")

        self.assertEqual(plan["task_type"], "comparison")
        self.assertEqual(plan["evidence_depth"], "summary")

    def test_planner_uses_original_question_if_plan_is_unstructured(self):
        planner = GenericResearchPlanner()
        planner.ollama = Mock()
        planner.ollama.generate.return_value = {"response": "not json"}

        question = "Explain mutual funds and ETFs"
        plan = planner.plan(question)

        self.assertEqual(plan["task_type"], "other")
        self.assertEqual(plan["research_scope"], question)
        self.assertEqual(plan["queries"], [question])


if __name__ == "__main__":
    unittest.main()
