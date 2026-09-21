import json

from agents.ollama_client import OllamaClient
from configs.config import Config


class RiskAgent:

    def __init__(self):

        self.ollama = OllamaClient()

    def analyze(
        self,
        company,
        quant_data=None,
        reconciliation_data=None
    ):

        quant_analysis = {}
        if isinstance(
            quant_data,
            dict
        ):
            quant_results = quant_data.get(
                "results",
                []
            )
            if (
                isinstance(
                    quant_results,
                    list
                )
                and quant_results
            ):
                first_result = (
                    quant_results[0]
                )
                if isinstance(
                    first_result,
                    dict
                ):
                    quant_analysis = (
                        first_result.get(
                            "analysis",
                            {}
                        )
                    )

        risk_context = {
            "price":
                quant_analysis.get("price"),

            "beta":
                quant_analysis.get("beta"),

            "risk":
                quant_analysis.get("risk"),

            "confidence":
                quant_analysis.get("confidence"),

            "prediction_pct":
                quant_analysis.get(
                    "prediction_pct"
                ),

            "recommendation":
                quant_analysis.get(
                    "recommendation"
                ),

            "regression_rating":
                quant_analysis.get(
                    "regression_rating"
                ),

            "predictive_score":
                quant_analysis.get(
                    "predictive_score"
                ),

            "predictive_rating":
                quant_analysis.get(
                    "predictive_rating"
                ),

            "stability_score":
                quant_analysis.get(
                    "stability_score"
                ),

            "stability_rating":
                quant_analysis.get(
                    "stability_rating"
                ),

            "forecast_score":
                quant_analysis.get(
                    "forecast_score"
                ),

            "forecast_rating":
                quant_analysis.get(
                    "forecast_rating"
                ),

            "forecast_consensus":
                quant_analysis.get(
                    "forecast_consensus"
                ),

            "average_confidence":
                quant_analysis.get(
                    "average_confidence"
                ),

            "momentum_score":
                quant_analysis.get(
                    "momentum_score"
                ),

            "momentum_rating":
                quant_analysis.get(
                    "momentum_rating"
                ),

            "financial_strength_score":
                quant_analysis.get(
                    "financial_strength_score"
                ),

            "financial_strength_rating":
                quant_analysis.get(
                    "financial_strength_rating"
                ),

            "institutional_ownership":
                quant_analysis.get(
                    "institutional_ownership"
                ),

            "insider_ownership":
                quant_analysis.get(
                    "insider_ownership"
                ),
            
            "short_percent":
                quant_analysis.get(
                    "short_percent"
                )
        }
        
        available_quant_fields = [
            key
            for key, value
            in risk_context.items()
            if value is not None
        ]
        
        prompt = f"""
You are the Hermes Market Risk Analyst.

Evaluate investment-related risks for the company below.

Company:
{json.dumps(company, indent=2)}

Quantitative Analysis: 
{json.dumps(risk_context, indent=2)}

Available Quantitative Fields:
{json.dumps(
    available_quant_fields,
    indent=2
)}

Signal Reconciliation:
{json.dumps(
    reconciliation_data or {},
    indent=2
)}
- Treat Signal Reconciliation as the authoritative interpretation
  of disagreements between internal quantitative model outputs.

- Do not independently invent additional quantitative conflicts
  when Signal Reconciliation already addresses those fields.

- Use Quantitative Analysis for raw quantitative evidence.

- Use Signal Reconciliation to distinguish genuine conflicts from
  differences caused by forecast horizon.

- RiskAgent may explain the risk implication of a documented
  conflict, but must not alter the underlying model result.

- Recommendation and predictive_rating are internal quantitative
  model outputs. Never describe them as investor sentiment,
  analyst sentiment, or market sentiment.

- Documented signal conflicts and forecast-horizon differences
  represent uncertainty in the quantitative outlook.

- Preserve that uncertainty in the risk assessment.

- Do not treat uncertainty itself as evidence that either the
  bullish or bearish signal is correct.
  
Analyze these risk categories:

1. Business Risk
2. Competitive Risk
3. Financial Risk
4. Market Risk
5. Regulatory Risk
6. Technology Risk
7. Concentration Risk

Return ONLY valid JSON using this schema:

{{
    "overall_risk": "low | moderate | high | very_high",
    "risk_score": 0,
    "signal_uncertainty":"low | moderate | high",
    "business_risk": "low | moderate | high | very_high",
    "competitive_risk": "low | moderate | high | very_high",
    "financial_risk": "low | moderate | high | very_high",
    "market_risk": "low | moderate | high | very_high",
    "regulatory_risk": "low | moderate | high | very_high",
    "technology_risk": "low | moderate | high | very_high",
    "concentration_risk": "low | moderate | high | very_high",

    "quantitative_signals": [
        {{
            "field": "",
            "value": null,
            "interpretation": ""
        }}
    ],

    "signal_conflicts": [
        {{
            "fields": [],
            "description": ""
        }}
    ],
    
    "horizon_differences": [
        {{
            "fields": [],
            "description": ""
        }}
    ],

    "risk_factors": []
}}

STRICT DATA RULES:

- Treat Quantitative Analysis as the only source of measured
  financial and market metrics.

- Never mention a financial ratio, score, percentage, valuation
  metric, ownership metric, risk metric, or model output unless
  its field exists in Available Quantitative Fields.

- Never invent debt-to-equity, interest coverage, debt levels,
  cash flow ratios, analyst recommendations, or other metrics
  unless explicitly supplied.

- Do not reinterpret an internal model recommendation as an
  analyst recommendation.
  
- Do not classify ownership or short-interest percentages as
  high, low, concentrated, supportive, bearish, or bullish unless
  an explicit deterministic threshold or classification is supplied.

- Internal recommendation values are quantitative model signals.

- If evidence is unavailable, omit the claim rather than infer it.

- Qualitative business risks may be discussed, but they must not
  be presented as measured quantitative facts.

- Preserve conflicting quantitative signals in signal_conflicts.

- Copy documented forecast-horizon differences from Signal
  Reconciliation into horizon_differences.

- Do not place a documented horizon difference in
  signal_conflicts unless Signal Reconciliation explicitly
  classifies it as a genuine conflict.

- Explain the risk implication of horizon differences without
  pretending one horizon invalidates another.
"""

        response = self.ollama.generate(
            prompt,
            model=Config.RISK_MODEL
        )

        model_response = response.get(
            "response",
            ""
        )

        if not model_response.strip():

            return {
                "status": "failed",
                "error": (
                    "Risk Agent returned "
                    "an empty response"
                )
            }

        try:

            result = json.loads(
                model_response
            )

        except json.JSONDecodeError:

            return {
                "status": "failed",
                "error": (
                    "Risk Agent returned "
                    "invalid JSON"
                )
            }

        if isinstance(
            reconciliation_data,
            dict
        ):

            authoritative_conflicts = (
                reconciliation_data.get(
                    "conflicts",
                    []
                )
            )

            authoritative_horizon_differences = (
                reconciliation_data.get(
                    "horizon_differences",
                    []
                )
            )

            result[
                "signal_conflicts"
            ] = authoritative_conflicts

            result[
                "horizon_differences"
            ] = (
                authoritative_horizon_differences
            )
            has_conflicts = bool(
                authoritative_conflicts
            )

            has_horizon_differences = bool(
                authoritative_horizon_differences
            )


            if (
                has_conflicts
                and has_horizon_differences
            ):
                result[
                    "signal_uncertainty"
                ] = "high"


            elif (
                has_conflicts
                or has_horizon_differences
            ):

                result[
                    "signal_uncertainty"
                ] = "moderate"


            else:

                result[
                    "signal_uncertainty"
                ] = "low"
            
        return result