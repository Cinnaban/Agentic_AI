# agents/company_detection_agent.py
import json
import re
from agents.ollama_client import OllamaClient
from configs.config import Config

class CompanyDetectionAgent:

    def __init__(self):
        self.ollama = OllamaClient()
        def _extract_explicit_tickers(
            self,
            message
        ):

            if not isinstance(
                message,
                str
            ):

                return []


            candidates = re.findall(
                r"\b[A-Z]{1,5}\b",
                message
            )


            ignored = {
                "I",
                "A",
                "THE",
                "AND",
                "OR",
                "ETF"
            }


            tickers = [
                candidate
                for candidate
                in candidates
                if candidate not in ignored
            ]


            return list(
                dict.fromkeys(
                    tickers
                )
            )
    def analyze(
        self,
        message
    ):

        explicit_tickers = (
            self._extract_explicit_tickers(
                message
            )
        )


        if explicit_tickers:

            return {
                "is_company_request":
                    True,

                "companies": [
                    {
                        "name":
                            ticker,

                        "ticker":
                            ticker,

                        "entity_type":
                            "security"
                    }

                    for ticker
                    in explicit_tickers
                ]
            }
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