import sys
import json

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from agents.ollama_client import OllamaClient
from configs.config import Config


class QwenManager:

    def __init__(self):

        self.ollama = OllamaClient()

    def _validate_reconciliation(
        self,
        results
    ):

        validation = {
            "consistent": True,
            "issues": []
        }

        if not isinstance(
            results,
            dict
        ):

            validation[
                "consistent"
            ] = False

            validation[
                "issues"
            ].append(
                "Invalid quality context"
            )

            return validation


        reconciliation = results.get(
            "signal_reconciliation",
            {}
        )

        risk = results.get(
            "risk",
            {}
        )


        if not isinstance(
            reconciliation,
            dict
        ):

            return validation


        if not isinstance(
            risk,
            dict
        ):

            validation[
                "consistent"
            ] = False

            validation[
                "issues"
            ].append(
                "Risk output unavailable"
            )

            return validation
        
        reconciliation_conflicts = (
            reconciliation.get(
                "conflicts",
                []
            )
        )

        risk_conflicts = (
            risk.get(
                "signal_conflicts",
                []
            )
        )


        if (
            reconciliation_conflicts
            != risk_conflicts
        ):

            validation[
                "consistent"
            ] = False

            validation[
                "issues"
            ].append(
                "Risk conflicts do not match "
                "Signal Reconciliation"
            )
        reconciliation_horizons = (
            reconciliation.get(
                "horizon_differences",
                []
            )
        )

        risk_horizons = (
            risk.get(
                "horizon_differences",
                []
            )
        )


        if (
            reconciliation_horizons
            != risk_horizons
        ):

            validation[
                "consistent"
            ] = False

            validation[
                "issues"
            ].append(
                "Risk horizon differences do not "
                "match Signal Reconciliation"
            )
            
        requires_caution = (
            reconciliation.get(
                "requires_caution",
                False
            )
        )

        signal_uncertainty = (
            risk.get(
                "signal_uncertainty"
            )
        )


        if (
            requires_caution
            and signal_uncertainty
            not in {
                "moderate",
                "high"
            }
        ):

            validation[
                "consistent"
            ] = False

            validation[
                "issues"
            ].append(
                "Risk failed to acknowledge "
                "quantitative uncertainty"
            )


        return validation

    def review(
        self,
        results
    ):
        reconciliation_validation = (
            self._validate_reconciliation(
                results
            )
        )

        prompt = f"""
        You are the Hermes Quality Gate.

        Your ONLY task is to decide whether the supplied agent
        results are internally consistent and complete enough
        to continue.

        You are NOT the final analyst.

        Do NOT:
        - write a report
        - summarize the company
        - provide investment advice
        - provide recommendations
        - add new financial analysis
        - explain the results at length

        Check:

            1. Missing required information.
            2. Unresolved contradictions between agent outputs.
            3. Obvious factual or structural errors.
            4. Incomplete analysis.

            QUALITY RULES:
            - A documented quantitative signal conflict is not by itself
            a quality failure.
            - A documented forecast-horizon difference is not by itself
            a quality failure.
            - Signal Reconciliation is the authoritative source for
            quantitative conflicts and horizon differences.
            - Risk may preserve those disagreements as uncertainty.
            - If Risk.signal_uncertainty is "high", this means the
            conflicting quantitative evidence has been explicitly
            acknowledged.
            - Do not reject solely because
            Signal Reconciliation.requires_caution is true.
            - Do not reject solely because short-term and long-term
            forecasts point in different directions.
            - Do not reject solely because predictive_rating,
            recommendation, and forecast_consensus disagree.
            - Reject when a downstream agent contradicts, removes,
            misrepresents, or fails to acknowledge an authoritative
            Signal Reconciliation result.
            - Reject when Risk.signal_conflicts differs materially from
            Signal Reconciliation.conflicts.
            - Reject when Risk.horizon_differences differs materially
            from Signal Reconciliation.horizon_differences.
            - A mixed investment outlook may still be internally
            consistent and complete.
            
            DETERMINISTIC VALIDATION RULES:
            - Deterministic Reconciliation Validation is authoritative.
            - If its consistent value is true, do not reject solely because
            quantitative conflicts or horizon differences exist.
            - A consistent value of true means Risk correctly preserved the
            authoritative reconciliation structure.
            - High signal uncertainty is an acceptable analytical conclusion.
            - Mixed quantitative evidence is an analysis result, not
            automatically a quality defect.
            - If deterministic validation is false, treat its listed issues
            as material quality problems.
            
            Deterministic Reconciliation Validation:
                {json.dumps(
                    reconciliation_validation,
                    indent=2
                )}
                
        Return ONLY valid JSON using exactly this schema:

        {{
            "approved": true,
            "issues": [],
            "confidence": 95
        }}

        Rules:

        - approved must be true or false.
        - issues must be a JSON list of short strings.
        - confidence must be an integer from 0 through 100.
        - Do not include markdown.
        - Do not include tables.
        - Do not include commentary outside the JSON object.
        - Do not provide BUY, SELL, or HOLD advice.
        - Do not create new financial calculations.
        - Reject only when a material unresolved quality problem remains.
        - A documented disagreement between quantitative models is not
        automatically a quality failure.

        - Differences between short-term and long-term forecast horizons
        are not quality failures when Signal Reconciliation identifies
        them as horizon differences and Risk preserves the uncertainty.

        - If Signal Reconciliation sets requires_caution to true, that
        means the final analysis should communicate uncertainty. It does
        not automatically mean the analysis must be rejected.

        - Reject a quantitative conflict only when:
        1. the conflict is materially important,
        2. Signal Reconciliation failed to identify it, or
        3. Risk ignored, misrepresented, or contradicted it.

        - Approve an analysis containing conflicting signals when the
        conflicts are accurately identified, preserved, and reflected
        in the Risk assessment.

        Agent Results:

        {json.dumps(results, indent=2)}
"""
        response = self.ollama.generate(
            prompt,
            model=Config.QUALITY_MODEL
        )

        thinking = response.get(
            "thinking",
            ""
        )

        model_response = response.get(
            "response",
            ""
        )

        if not model_response.strip():

            return {
                "approved": False,
                "issues": [
                    "Quality Manager returned an empty response"
                ],
                "confidence": 0
            }

        try:

            result = json.loads(
                model_response
            )

        except json.JSONDecodeError:

            return {
                "approved": False,
                "issues": [
                    "Quality Manager returned invalid JSON"
                ],
                "confidence": 0
            }
        if not isinstance(
            result,
            dict
        ):
            return {
                "approved": False,
                "issues": [
                    "Quality Manager returned an invalid result"
                ],
                "confidence": 0
            }
            
        return {
            "approved": bool(
                result.get(
                    "approved",
                    False
                )
            ),
            "issues": result.get(
                "issues",
                []
            ),
            "confidence": result.get(
                "confidence",
                0
            )
        }