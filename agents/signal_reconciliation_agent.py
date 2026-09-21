import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from agents.ollama_client import OllamaClient
from orchestrator.signal_fact_builder import (
    SignalFactBuilder
)

class SignalReconciliationAgent:

    def __init__(self):

        self.fact_builder = (SignalFactBuilder())
        
    def analyze(
        self,
        quant_data
    ):
        if not isinstance(
            quant_data,
            dict
        ):
            return {
                "status": "failed",
                "error":
                    "Invalid quantitative data"
            }
        quant_results = quant_data.get(
            "results",
            []
        )
        if (
            not isinstance(
                quant_results,
                list
            )
            or not quant_results
        ):
            return {
                "status": "failed",
                "error":
                    "No quantitative results available"
            }
        first_result = (
            quant_results[0]
        )
        if not isinstance(
            first_result,
            dict
        ):
            return {
                "status": "failed",
                "error":
                    "Invalid quantitative result"
            }
        analysis = first_result.get(
            "analysis",
            {}
        )
        if not isinstance(
            analysis,
            dict
        ):
            return {
                "status": "failed",
                "error":
                    "Invalid quantitative analysis"
            }
            
        signal_facts = (
            self.fact_builder.build(
                quant_data
            )
        )
        
        deterministic_agreements = (
            signal_facts.get(
                "agreements",
                []
            )
        )

        deterministic_conflicts = (
            signal_facts.get(
                "conflicts",
                []
            )
        )

        deterministic_horizon_differences = (
            signal_facts.get(
                "horizon_differences",
                []
            )
        )
        has_conflicts = bool(
            deterministic_conflicts
        )

        has_horizon_differences = bool(
            deterministic_horizon_differences
        )

        requires_caution = (
            has_conflicts
            or has_horizon_differences
        )

        if (
            has_conflicts
            or has_horizon_differences
        ):

            overall_alignment = "mixed"

        else:

            overall_alignment = "aligned"

        return {
            "overall_alignment":
                overall_alignment,

            "requires_caution":
                requires_caution,

            "agreements":
                deterministic_agreements,

            "conflicts":
                deterministic_conflicts,

            "horizon_differences":
                deterministic_horizon_differences
        }