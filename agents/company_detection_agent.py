# agents/company_detection_agent.py
import json

from agents.ollama_client import OllamaClient
from configs.config import Config

class CompanyDetectionAgent:

    def __init__(self):
        self.ollama = OllamaClient()
    
    def analyze(
        self,
        message
    ):

        prompt = f"""
        You are a company detection agent.

        Determine whether the user's message is asking
        about one or more publicly traded companies.

        Return ONLY valid JSON.

        Example:

        {{
        "is_company_request": true,
        "companies": [
            {{
            "name": "NVIDIA",
            "ticker": "NVDA"
            }}
        ]
        }}

        User Message:

        {message}
        """

        response = self.ollama.generate(
            prompt,
            model=Config.COMPANY_DETECTION_MODEL
        )

        model_response = response["response"]

        print(model_response)

        try:
            result = json.loads(
                model_response
            )
            return result

        except Exception as e:
            print(
                f"JSON Parse Error: {e}"
            )

            return {
                "is_company_request": False,
                "companies": [],
                "error": str(e)
            }