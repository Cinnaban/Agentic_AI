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


from financial_engine.formula_metric_extractor import (
    FormulaMetricExtractor
)


company_results = {
    "AAA": {
        "quant": {
            "analysis": {
                "growth_score":
                    80,

                "profitability_score":
                    90,

                "financial_strength_score":
                    70
            }
        },

        "risk": {
            "risk_score":
                30
        }
    },

    "BBB": {
        "quant": {
            "analysis": {
                "growth_score":
                    70,

                "profitability_score":
                    60,

                "financial_strength_score":
                    90
            }
        },

        "risk": {
            "risk_score":
                50
        }
    },

    "CCC": {
        "quant": {
            "analysis": {
                "growth_score":
                    60,

                "profitability_score":
                    80,

                "financial_strength_score":
                    50
            }
        },

        "risk": {
            "risk_score":
                70
        }
    }
}


extractor = (
    FormulaMetricExtractor()
)


result = extractor.extract(
    company_results
)


print(
    result
)


assert set(
    result[
        "company_metrics"
    ]
) == {
    "AAA",
    "BBB",
    "CCC"
}


available = set(
    result[
        "available_metrics"
    ]
)


assert {
    "growth_score",
    "profitability_score",
    "financial_strength_score",
    "risk_score"
}.issubset(
    available
)


print(
    "FORMULA METRIC EXTRACTOR TEST PASSED"
)