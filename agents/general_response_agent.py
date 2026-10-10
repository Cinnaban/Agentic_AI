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

Answer the user's request directly and clearly.

If the request involves:
- company research
- financial analysis
- investment analysis
- stock comparisons
- market sentiment

Respond only when the request is
general conversation.

If the request involves:
- Information capture
- General insight
- Research 

Highlight key moments, achievements, or noteworthy factors 

Include factors if possible:
- Geographic location
- Size or population
- Public or private entity
- Country reside or founded
- Year of reference
- Do not invent or infer themes, factors general information
- Provide summarization 

User message:

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