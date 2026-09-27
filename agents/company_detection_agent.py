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


        explicit_entities = [
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
        
        explicit_ticker_context = (
            ", ".join(
                explicit_tickers
            )
            if explicit_tickers
            else "None"
        )
        
        prompt = f"""
        You are a company detection agent.

        Explicit ticker symbols already detected:

        {explicit_ticker_context}

        IMPORTANT:

        - Explicit ticker symbols listed above have already
        been preserved deterministically.

        - Do not reinterpret or rename those tickers.

        - Also detect any additional publicly traded
        companies or securities referred to by natural
        language names.

        - Do not omit natural-language companies merely
        because another explicit ticker is present.

        - Return all detected entities.
        
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


            companies = result.get(
                "companies",
                []
            )


            if not isinstance(
                companies,
                list
            ):

                companies = []


            normalized_companies = []


            for company in companies:

                if not isinstance(
                    company,
                    dict
                ):

                    continue


                ticker = company.get(
                    "ticker"
                )


                if isinstance(
                    ticker,
                    str
                ):

                    ticker = (
                        ticker
                        .strip()
                        .upper()
                    )


                if not ticker:

                    continue


                normalized_companies.append(
                    {
                        "name":
                            company.get(
                                "name"
                            ),

                        "ticker":
                            ticker,

                        "entity_type":
                            company.get(
                                "entity_type",
                                "company"
                            )
                    }
                )


            merged_companies = []

            seen_tickers = set()


            for company in (
                explicit_entities
                + normalized_companies
            ):

                ticker = company.get(
                    "ticker"
                )


                if not isinstance(
                    ticker,
                    str
                ):

                    continue


                ticker = (
                    ticker
                    .strip()
                    .upper()
                )


                if not ticker:

                    continue


                if ticker in seen_tickers:

                    continue


                seen_tickers.add(
                    ticker
                )


                company[
                    "ticker"
                ] = ticker


                merged_companies.append(
                    company
                )


            return {
                "is_company_request":
                    bool(
                        merged_companies
                    ),

                "companies":
                    merged_companies
            }


        except Exception as e:

            print(
                f"JSON Parse Error: {e}"
            )


            if explicit_entities:

                return {
                    "is_company_request":
                        True,

                    "companies":
                        explicit_entities,

                    "error":
                        str(
                            e
                        )
                }


            return {
                "is_company_request":
                    False,

                "companies":
                    [],

                "error":
                    str(
                        e
                    )
            }