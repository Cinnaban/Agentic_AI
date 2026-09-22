
from agents.ollama_client import OllamaClient
from configs.config import Config


class GeneralResponseAgent:

    def __init__(self):
        self.ollama = OllamaClient()

    def analyze(
        self,
        message
    ):

        prompt = f"""
You are Hermes.

Answer the user's request directly and clearly.

Do not perform stock or company analysis unless
the request specifically requires it.

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