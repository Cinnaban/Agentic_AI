import json

from agents.ollama_client import OllamaClient
from configs.config import Config


class ChallengerAgent:

    def __init__(self):
        self.ollama = OllamaClient()

    def analyze(
        self,
        company,
        research=None,
        risk=None,
        quant=None,
        signal_reconciliation=None,
        market_context=None
    ):
        if not Config.ENABLE_CHALLENGER:
            return {
                "status": "disabled"
            }

        if market_context is None:
            market_context = {}

        challenge_input = {
            "company": company,
            "research": research,
            "risk": risk,
            "quant": quant,
            "signal_reconciliation": signal_reconciliation,
            "market_context": market_context
        }

        prompt = f"""
You are an independent investment research challenger.

Your job is NOT to redo the primary analysis.

Review the supplied research, risk analysis,
and evidence. Attempt to identify weaknesses in
the primary investment thesis.

Look specifically for:

1. Unsupported conclusions
2. Contradictory evidence
3. Missing material risks
4. Weak assumptions
5. Excessive confidence
6. Alternative interpretations
7. Evidence that does not support the conclusion
8. Important evidence the analysis overlooked

EVIDENCE RULES:

- Use only evidence supplied in the input.
- Do not fabricate financial data.
- Do not introduce current events from model memory.
- SEC facts are authoritative for supplied
  company-reported financial facts.
- Supplied macroeconomic facts must remain
  macroeconomic context.
- Quantitative model outputs must not be presented
  as reported financial facts.
- If evidence is insufficient to challenge a claim,
  say so.
- A disagreement alone is not evidence that the
  primary analysis is wrong.
- Treat Signal Reconciliation results preserved
  in Risk as authoritative for internal quantitative
  conflicts and forecast-horizon differences.
- Do not invent quantitative conflicts that are not
  supported by supplied quantitative or reconciliation
  evidence.
- Do not treat documented forecast-horizon differences
  as errors merely because different horizons point in
  different directions.
- Research conclusions must be evaluated against the
  supplied Market Context when available.
- Risk conclusions must be evaluated against supplied
  quantitative evidence and reconciliation results.
- Do not assume Research is correct merely because it
  contains more narrative detail.
- Do not assume Risk is correct merely because it
  contains numerical classifications.

Return ONLY valid JSON using this schema:

{{
    "status": "completed",
    "agreement": "agree|partial|challenge",
    "challenge_score": 0.0,
    "major_concerns": [],
    "contradictions": [],
    "missing_risks": [],
    "unsupported_claims": [],
    "alternative_interpretations": [],
    "summary": ""
}}

Challenge Input:

{json.dumps(
    challenge_input,
    indent=2,
    default=str
)}
"""

        response = self.ollama.generate(
            prompt,

            model=Config.CHALLENGER_MODEL,

            options={
                "num_predict":
                    Config.CHALLENGER_NUM_PREDICT,

                "num_ctx":
                    Config.CHALLENGER_NUM_CTX
            },

            keep_alive=(
                Config.OLLAMA_KEEP_ALIVE_CHALLENGER
            )
        )

        model_response = response.get(
            "response",
            ""
        )

        if not model_response.strip():
            return {
                "status": "failed",
                "error": "Challenger returned empty response"
            }

        try:
            result = json.loads(model_response)

        except json.JSONDecodeError:
            return {
                "status": "failed",
                "error": "Challenger returned invalid JSON",
                "raw_response": model_response
            }

        return result