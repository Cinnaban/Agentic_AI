import json

from agents.ollama_client import (
    OllamaClient
)

from configs.config import (
    Config
)


class FinancialFormulaDesigner:

    def __init__(
        self
    ):

        self.ollama = (
            OllamaClient()
        )


    def design(
        self,
        message,
        companies,
        available_metrics
    ):

        if not isinstance(
            available_metrics,
            list
        ):

            available_metrics = []


        if not available_metrics:

            return {
                "status":
                    "unavailable",

                "reason":
                    "No financial metrics are available."
            }


        prompt = f"""
You are designing a transparent custom financial
analysis formula for a specific user question.

USER QUESTION:

{message}


COMPANIES:

{json.dumps(
    companies,
    indent=2
)}


ALLOWED FINANCIAL METRICS:

{json.dumps(
    available_metrics,
    indent=2
)}


IMPORTANT:

You may ONLY use metrics listed in
ALLOWED FINANCIAL METRICS.

Do not invent metrics.

Do not invent metric values.

Your responsibility is to DESIGN the analytical
formula, not calculate company scores.

The formula should help answer the user's actual
financial question.

Choose metrics because they are relevant to that
question, not merely because they are available.

Each formula component must contain:

- metric
- weight
- direction
- reason

direction must be either:

"higher_is_better"

or

"lower_is_better"


Weights must be numeric.

Explain how the formula was created.

Explain why the formula is useful for this specific
question.

Explain important limitations.

Do not claim this is an established financial model,
industry standard, academic model, or investment
guarantee.

This is a custom analytical framework created for
this specific request.


Return ONLY valid JSON using this structure:

{{
    "name": "Formula Name",

    "purpose": "What the formula evaluates",

    "components": [
        {{
            "metric": "metric_name",
            "weight": 0.40,
            "direction": "higher_is_better",
            "reason": "Why this metric matters"
        }}
    ],

    "how_created":
        "Explanation of how the metrics and weights
        were selected.",

    "why_important":
        "Explanation of why combining these metrics
        helps answer the question.",

    "assumptions": [
        "..."
    ],

    "limitations": [
        "..."
    ]
}}
"""


        response = (
            self.ollama.generate(
                prompt,
                model=Config.HERMES_MODEL
            )
        )


        model_response = response.get(
            "response",
            ""
        )


        if not isinstance(
            model_response,
            str
        ):

            model_response = ""


        try:

            result = json.loads(
                model_response
            )

        except Exception as exc:

            return {
                "status":
                    "failed",

                "error":
                    str(
                        exc
                    )
            }


        components = result.get(
            "components",
            []
        )


        if not isinstance(
            components,
            list
        ):

            components = []


        validated_components = []


        for component in components:

            if not isinstance(
                component,
                dict
            ):

                continue


            metric = component.get(
                "metric"
            )


            if metric not in (
                available_metrics
            ):

                continue


            weight = component.get(
                "weight"
            )


            if not isinstance(
                weight,
                (
                    int,
                    float
                )
            ):

                continue


            direction = component.get(
                "direction"
            )


            if direction not in {
                "higher_is_better",
                "lower_is_better"
            }:

                continue


            validated_components.append(
                {
                    "metric":
                        metric,

                    "weight":
                        float(
                            weight
                        ),

                    "direction":
                        direction,

                    "reason":
                        component.get(
                            "reason",
                            ""
                        )
                }
            )


        if not validated_components:

            return {
                "status":
                    "failed",

                "error":
                    (
                        "Formula contained no "
                        "valid components."
                    )
            }


        return {
            "name":
                result.get(
                    "name",
                    "Custom Financial Formula"
                ),

            "purpose":
                result.get(
                    "purpose",
                    ""
                ),

            "components":
                validated_components,

            "how_created":
                result.get(
                    "how_created",
                    ""
                ),

            "why_important":
                result.get(
                    "why_important",
                    ""
                ),

            "assumptions":
                result.get(
                    "assumptions",
                    []
                ),

            "limitations":
                result.get(
                    "limitations",
                    []
                )
        }