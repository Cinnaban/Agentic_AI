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

    @staticmethod
    def _parse_json(text):
        """Tolerates markdown fences and text around the JSON object."""
        text = str(text or "").strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start < 0 or end <= start:
                return None
            try:
                data = json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def completeness_cap(results):
        """Deterministic ceiling on confidence plus issues, independent of the reviewer model."""
        if not isinstance(results, dict):
            return 0, ["Invalid quality context"]
        cap, issues = 100, []

        research = results.get("research")
        if isinstance(research, dict):
            research = research.get("response") or research.get("analysis") or research.get("text")
        research_text = str(research or "").strip()
        if not research_text or research_text.startswith("Research analysis unavailable"):
            cap = min(cap, 65)
            issues.append("Research agent returned no usable output")

        risk = results.get("risk")
        if not isinstance(risk, dict) or not any(
            k in risk for k in ("overall_risk", "risk_score", "signal_uncertainty")
        ):
            cap = min(cap, 65)
            issues.append("Risk agent output unavailable")

        quant = results.get("quant_summary") or results.get("quant")
        if not quant:
            cap = min(cap, 70)
            issues.append("Quantitative analysis unavailable")

        failed = results.get("failed_agents") or []
        if failed:
            cap = min(cap, 80 - 5 * len(failed))
            issues.append("Failed agents: " + ", ".join(str(f) for f in failed))

        if not results.get("social_available"):
            cap = min(cap, 90)
        return max(cap, 0), issues

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
    
    def _build_fallback_review(
        self,
        results
    ):
        strengths = []
        limitations = []
        issues = []

        if not isinstance(
            results,
            dict
        ):
            return {
                "approved": False,
                "confidence": 0,
                "issues": [
                    "Invalid quality context"
                ],
                "strengths": [],
                "limitations": [
                    "Quality context was unavailable"
                ],
                "review_source":
                    "heuristic_fallback"
            }

        reconciliation_validation = (
            self._validate_reconciliation(
                results
            )
        )

        challenger_validation = (
            self._validate_challenger(
                results
            )
        )

        market_context = (
            results.get(
                "market_context",
                {}
            )
        )

        if not isinstance(
            market_context,
            dict
        ):
            market_context = {}

        source_status = (
            market_context.get(
                "source_status",
                {}
            )
        )

        if not isinstance(
            source_status,
            dict
        ):
            source_status = {}

        # Base confidence for a structurally
        # usable quality context.
        confidence = 20

        evidence_weights = {
            "financial_data": 20,
            "sec_facts": 15,
            "sec_filings": 15,
            "macro": 10,
            "social": 5
        }

        display_names = {
            "financial_data":
                "Financial data",
            "sec_facts":
                "SEC facts",
            "sec_filings":
                "SEC filings",
            "macro":
                "Macroeconomic data",
            "social":
                "Public discussion evidence"
        }

        for source, points in (
            evidence_weights.items()
        ):
            status = (
                source_status.get(
                    source
                )
            )

            display_name = (
                display_names.get(
                    source,
                    source
                )
            )

            if status == "available":
                confidence += points

                strengths.append(
                    f"{display_name} available"
                )
            else:
                limitations.append(
                    f"{display_name} unavailable"
                )

        news_status = (
            source_status.get(
                "news"
            )
        )

        if news_status == "available":
            strengths.append(
                "Current news evidence available"
            )
        else:
            limitations.append(
                "Current news evidence unavailable"
            )

        live_status = (
            source_status.get(
                "live_market_context"
            )
        )

        if live_status == "available":
            strengths.append(
                "Live market context available"
            )
        else:
            limitations.append(
                "Live market context unavailable"
            )

        quant = results.get(
            "quant",
            {}
        )

        quant_completed = bool(
            isinstance(
                quant,
                dict
            )
            and (
                quant.get(
                    "status"
                ) == "completed"
                or bool(
                    quant.get(
                        "results"
                    )
                )
            )
        )

        if quant_completed:
            confidence += 10

            strengths.append(
                "Quantitative analysis completed"
            )
        else:
            limitations.append(
                "Quantitative analysis incomplete"
            )

        risk = results.get(
            "risk",
            {}
        )

        risk_completed = bool(
            isinstance(
                risk,
                dict
            )
            and (
                risk.get(
                    "status"
                ) == "completed"
                or any(
                    key in risk
                    for key in {
                        "overall_risk",
                        "risk_score",
                        "signal_uncertainty"
                    }
                )
            )
        )

        if risk_completed:
            confidence += 5

            strengths.append(
                "Risk analysis completed"
            )
        else:
            limitations.append(
                "Risk analysis incomplete"
            )

        reconciliation_consistent = bool(
            reconciliation_validation.get(
                "consistent",
                False
            )
        )

        if reconciliation_consistent:
            strengths.append(
                "Signal reconciliation is "
                "internally consistent"
            )
        else:
            confidence -= 20

            reconciliation_issues = (
                reconciliation_validation.get(
                    "issues",
                    []
                )
            )

            if isinstance(
                reconciliation_issues,
                list
            ):
                issues.extend(
                    str(issue)
                    for issue
                    in reconciliation_issues
                )

        if challenger_validation.get(
            "available"
        ):
            if challenger_validation.get(
                "completed"
            ):
                strengths.append(
                    "Independent challenger "
                    "review completed"
                )
            else:
                limitations.append(
                    "Independent challenger "
                    "review incomplete"
                )

        confidence = max(
            0,
            min(
                int(confidence),
                100
            )
        )

        return {
            "approved":
                reconciliation_consistent,
            "confidence":
                confidence,
            "issues":
                issues,
            "strengths":
                strengths,
            "limitations":
                limitations,
            "review_source":
                "heuristic_fallback"
        }
    def _validate_challenger(
        self,
        results
    ):
        validation = {
            "available": False,
            "completed": False,
            "issues": []
        }

        if not isinstance(
            results,
            dict
        ):
            return validation

        challenger = results.get(
            "challenger"
        )

        if challenger is None:
            return validation

        validation[
            "available"
        ] = True

        if not isinstance(
            challenger,
            dict
        ):
            validation[
                "issues"
            ].append(
                "Invalid Challenger output"
            )
            return validation

        status = challenger.get(
            "status"
        )

        if status == "completed":
            validation[
                "completed"
            ] = True

        elif status == "failed":
            validation[
                "issues"
            ].append(
                "Challenger review failed"
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
        challenger_validation = (
            self._validate_challenger(
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
            5. Material objections identified by the Challenger.
            6. Whether Challenger objections are supported by
               supplied agent evidence.

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
    
    CHALLENGER RULES:
    - Challenger is an independent adversarial review.
    - Challenger is advisory, not authoritative.
    - Do not reject analysis merely because Challenger
        disagrees with Research or Risk.
    - Evaluate whether each material Challenger objection
        is supported by the supplied agent evidence.
    - Unsupported Challenger objections should not cause
        rejection.
    - A supported Challenger objection that exposes a
        material unresolved error, contradiction, missing
        risk, or unsupported claim should be treated as a
        quality issue.
    - If Research or Risk already acknowledges the issue,
        do not treat the Challenger observation alone as a
        new quality defect.
    - Do not allow Challenger to override authoritative
        deterministic Signal Reconciliation results.
    - Challenger must not introduce facts that are absent
        from the supplied evidence.
    - A failed or unavailable Challenger is not by itself
        a reason to reject otherwise valid analysis.
    
    
    
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

            model=Config.QUALITY_MODEL,

            keep_alive=(
                Config.OLLAMA_KEEP_ALIVE_QUALITY
            )
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

            return self._build_fallback_review(
                results
            )

        result = self._parse_json(
            model_response
        )
        if result is None:
            print("QUALITY REVIEW INVALID JSON:", model_response[:200])
            return self._build_fallback_review(
                results
            )
            
        issues = result.get("issues", [])
        if not isinstance(issues, list):
            issues = [str(issues)]
        try:
            confidence = int(result.get("confidence", 0))
        except (TypeError, ValueError):
            confidence = 0

        cap, cap_issues = self.completeness_cap(results)
        if confidence > cap:
            confidence = cap
        known = " ".join(str(i).lower() for i in issues)
        for issue in cap_issues:
            if issue.lower().split(" returned")[0] not in known:
                issues.append(issue)

        return {
            "approved": bool(
                result.get(
                    "approved",
                    False
                )
            ),
            "issues": issues,
            "confidence": confidence
        }
