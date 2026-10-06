import sys
import traceback 

from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from orchestrator.hermes import (
    Hermes
)

from orchestrator.financial_metric_builder import (
    FinancialMetricBuilder
)

from orchestrator.financial_table_formatter import (
    FinancialTableFormatter
)


hermes = Hermes.__new__(
    Hermes
)


hermes.financial_metric_builder = (
    FinancialMetricBuilder()
)


hermes.financial_table_formatter = (
    FinancialTableFormatter()
)


execution_results = {
    "research":
        (
            "Company Overview\n\n"
            "The supplied research evidence supports "
            "a basic company overview."
        ),

    "risk": {
        "overall_risk":
            "moderate",

        "risk_score":
            42,

        "signal_uncertainty":
            "low"
    },

    "market_context": {
        "social_summary": {
            "available":
                True,

            "discussion_volume":
                12,

            "platforms": [
                "reddit"
            ],

            "discussion_themes": [
                "competition",
                "pricing",
                "product quality"
            ],

            "top_keywords": {
                "competition":
                    5,

                "pricing":
                    4,

                "quality":
                    3
            }
        }
    }
}


quality_review = {
    "approved":
        True,

    "confidence":
        91
}


response = (
    hermes._build_company_response(
        execution_results,
        quality_review
    )
)


print()
print("=" * 70)
print("COMPANY RESPONSE WITH SOCIAL EVIDENCE")
print("=" * 70)
print(response)
print("=" * 70)


assert (
    "Public Discussion Signals:"
    in response
)

assert (
    "Discussion Volume:"
    in response
)

assert (
    "Platforms:"
    in response
)

assert (
    "Recurring Themes:"
    in response
)

assert (
    "verified facts"
    in response
)

assert (
    response.count(
        "Public Discussion Signals"
    )
    == 1
)

print()
print(
    "COMPANY RESPONSE SOCIAL TEST PASSED"
)