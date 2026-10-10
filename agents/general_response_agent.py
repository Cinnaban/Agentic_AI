import sys
import traceback 

from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))


from agents.ollama_client import OllamaClient
from configs.config import Config

from agents.generic_evidence_agent import (
    GenericEvidenceAgent
)
class GeneralResponseAgent:

    def __init__(self):
        self.ollama = OllamaClient()

        self.generic_evidence_agent = (
            GenericEvidenceAgent()
        )
        
    def analyze(
        self,
        message,
        evidence=None,
        research_plan=None
    ):
        
        if isinstance(
            evidence,
            dict
        ):
            return (
                self.generic_evidence_agent
                .analyze(
                    message=message,
                    evidence=evidence,
                    research_plan=research_plan
                )
            )

        prompt = f"""
You are Hermes.

This path has no retrieved public evidence.

Answer only conversational requests that do not
require external factual verification.

Do not provide factual claims about:

- companies
- organizations
- people
- locations
- dates
- founding history
- products
- population
- size
- ownership
- market position
- financial information

If the user asks a factual question that requires
external evidence, respond:

"I couldn't retrieve enough reliable public
evidence to answer that accurately."

Do not answer from model memory.

USER MESSAGE:

{message}
"""

        response = self.ollama.generate(
            prompt,
            model=Config.GENERAL_RESPONSE_MODEL
        )

        model_response = response.get(
            "response",
            ""
        )

        if not model_response.strip():
            return {
                "status": "failed",
                "response": (
                    "Unable to generate a response."
                )
            }

        return {
            "status": "completed",
            "response": model_response
        }