import sys

from pathlib import Path


ROOT_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)


if str(ROOT_DIR) not in sys.path:

    sys.path.append(
        str(ROOT_DIR)
    )


from agents.financial_formula_designer import (
    FinancialFormulaDesigner
)

from financial_engine.formula_metric_extractor import (
    FormulaMetricExtractor
)

from financial_engine.formula_evaluator import (
    FormulaEvaluator
)


company_results = {
    "AAA": {
        "quant": {
            "analysis": {
                "growth_score": 80,
                "profitability_score": 90,
                "financial_strength_score": 70
            }
        },

        "risk": {
            "risk_score": 30
        }
    },

    "BBB": {
        "quant": {
            "analysis": {
                "growth_score": 70,
                "profitability_score": 60,
                "financial_strength_score": 90
            }
        },

        "risk": {
            "risk_score": 50
        }
    },

    "CCC": {
        "quant": {
            "analysis": {
                "growth_score": 60,
                "profitability_score": 80,
                "financial_strength_score": 50
            }
        },

        "risk": {
            "risk_score": 70
        }
    }
}


companies = [
    {
        "name": "AAA Corp",
        "ticker": "AAA"
    },

    {
        "name": "BBB Corp",
        "ticker": "BBB"
    },

    {
        "name": "CCC Corp",
        "ticker": "CCC"
    }
]


extractor = (
    FormulaMetricExtractor()
)

designer = (
    FinancialFormulaDesigner()
)

evaluator = (
    FormulaEvaluator()
)


metric_result = extractor.extract(
    company_results
)


print()
print("=" * 70)
print("AVAILABLE METRICS")
print("=" * 70)

print(
    metric_result[
        "available_metrics"
    ]
)


formula = designer.design(
    message=(
        "Which company appears financially "
        "strongest when considering growth, "
        "profitability, financial strength "
        "and risk?"
    ),

    companies=companies,

    available_metrics=(
        metric_result[
            "available_metrics"
        ]
    )
)


print()
print("=" * 70)
print("HERMES FORMULA DESIGN")
print("=" * 70)

print(
    formula
)


evaluation = evaluator.evaluate(
    formula=formula,

    company_metrics=(
        metric_result[
            "company_metrics"
        ]
    )
)


print()
print("=" * 70)
print("DETERMINISTIC EVALUATION")
print("=" * 70)

print(
    evaluation
)


assert formula.get(
    "name"
)


assert formula.get(
    "purpose"
)


assert formula.get(
    "how_created"
)


assert formula.get(
    "why_important"
)


assert (
    evaluation.get(
        "status"
    )
    == "completed"
)


assert evaluation.get(
    "ranking"
)


print()
print(
    "CUSTOM FINANCIAL FORMULA "
    "PIPELINE TEST PASSED"
)