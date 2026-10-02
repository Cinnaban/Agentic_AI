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


from financial_engine.formula_evaluator import (
    FormulaEvaluator
)


formula = {
    "name":
        "Financial Strength Test",

    "purpose":
        "Compare financial strength",

    "components": [
        {
            "metric":
                "financial_strength_score",

            "weight":
                0.40,

            "direction":
                "higher_is_better",

            "reason":
                "Financial strength matters"
        },

        {
            "metric":
                "profitability_score",

            "weight":
                0.35,

            "direction":
                "higher_is_better",

            "reason":
                "Profitability matters"
        },

        {
            "metric":
                "risk_score",

            "weight":
                0.25,

            "direction":
                "lower_is_better",

            "reason":
                "Lower risk is preferred"
        }
    ]
}


company_metrics = {
    "AAA": {
        "financial_strength_score":
            90,

        "profitability_score":
            80,

        "risk_score":
            30
    },

    "BBB": {
        "financial_strength_score":
            70,

        "profitability_score":
            90,

        "risk_score":
            50
    },

    "CCC": {
        "financial_strength_score":
            50,

        "profitability_score":
            60,

        "risk_score":
            80
    }
}


evaluator = FormulaEvaluator()


result = evaluator.evaluate(
    formula=formula,
    company_metrics=company_metrics
)


print(
    result
)


assert (
    result.get(
        "status"
    )
    == "completed"
)


assert set(
    result.get(
        "scores",
        {}
    )
) == {
    "AAA",
    "BBB",
    "CCC"
}


assert len(
    result.get(
        "ranking",
        []
    )
) == 3


print(
    "FORMULA EVALUATOR TEST PASSED"
)
