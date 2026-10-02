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
        
        
        OUTPUT REQUIREMENT:

        Always return valid JSON.

        Even when the message is not about a company,
        organization, security, ETF, or private company,
        return exactly this structure:

        {{
            "is_company_request": false,
            "companies": []
        }}

        Never return explanatory prose outside the JSON.
        Determine whether the user's message is asking
        about one or more companies, organizations,
        publicly traded securities, ETFs, or private
        companies.
        
        A private company is still a company request.

        For a private company:
        - preserve the company entity,
        - return ticker as null,
        - use entity_type "private_company".

        Return ONLY valid JSON.

        IMPORTANT PRIVATE COMPANY OR NO TICKER GUIDELINES:

        If an organization is privately held and does not
        have a publicly traded security ticker:

        - Do not invent a ticker.
        - Return ticker as null.
        - Use entity_type "private_company".

        If the organization cannot be confidently resolved
        to a public ticker:

        - Do not guess.
        - Return ticker as null.

        A company name by itself is not sufficient evidence
        that the company is publicly traded.


        Public company Example:

        {{
        "is_company_request": true,
        "companies": [
            {{
            "name": "NVIDIA",
            "ticker": "NVDA"
            }}
        ]
        }}
        
        Private company example:
        {{
            "is_company_request": true,
            "companies": [
                {{
                    "name": "Example Private Company",
                    "ticker": null,
                    "entity_type": "private_company"
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

                        ticker = None

                else:

                    ticker = None

                entity_type = str(
                    company.get(
                        "entity_type",
                        "company"
                    )
                    or "company"
                ).strip().lower()

                name = company.get(
                    "name"
                )

                if isinstance(
                    name,
                    str
                ):

                    name = (
                        name.strip()
                    )

                if not name:

                    continue

                normalized_companies.append(
                    {
                        "name":
                            name,

                        "ticker":
                            ticker,

                        "entity_type":
                            entity_type
                    }
                )

            merged_companies = []

            seen_entities = set()


            for company in (
                explicit_entities
                + normalized_companies
            ):

                if not isinstance(
                    company,
                    dict
                ):

                    continue


                name = company.get(
                    "name"
                )


                if isinstance(
                    name,
                    str
                ):

                    name = (
                        name.strip()
                    )


                if not name:

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

                        ticker = None


                else:

                    ticker = None


                entity_type = str(
                    company.get(
                        "entity_type",
                        "company"
                    )
                    or "company"
                ).strip().lower()


                if ticker:

                    identity = (
                        "ticker",
                        ticker
                    )


                else:

                    identity = (
                        "name",
                        name.lower()
                    )


                if identity in seen_entities:

                    continue


                seen_entities.add(
                    identity
                )


                merged_companies.append(
                    {
                        "name":
                            name,

                        "ticker":
                            ticker,

                        "entity_type":
                            entity_type
                    }
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