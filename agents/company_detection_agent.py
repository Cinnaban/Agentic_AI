# agents/company_detection_agent.py
import json
import re
from agents.ollama_client import OllamaClient
from configs.config import Config

class CompanyDetectionAgent:

    KNOWN_PUBLIC_COMPANY_ALIASES = {
        "intel": {
            "name": "Intel",
            "ticker": "INTC",
            "entity_type": "stock"
        },
        "intel corporation": {
            "name": "Intel",
            "ticker": "INTC",
            "entity_type": "stock"
        }
    }

    def __init__(self):
        self.ollama = OllamaClient()

    @classmethod
    def _extract_known_company_entities(cls, message):
        normalized = str(message or "").lower()
        entities = []
        for alias, entity in cls.KNOWN_PUBLIC_COMPANY_ALIASES.items():
            if re.search(
                rf"\b{re.escape(alias)}\b",
                normalized
            ):
                entities.append(dict(entity))
        return entities

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
        known_company_entities = (
            self._extract_known_company_entities(message)
        )
        
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
            "intent": "general_information",
            "companies": []
        }}

        Never return explanatory prose outside the JSON.
        
        Determine whether the user's message is asking
        about one or more companies, organizations,
        publicly traded securities, ETFs, or private
        companies.
        
        Also determine the user's intent.

        Valid intents:

        analysis
        evaluation
        comparison
        history
        leadership
        products
        general_information

        Use analysis when the user explicitly asks to:
        - analyze
        - perform analysis
        - investment analysis
        - valuation
        - forecast
        - outlook
        - risk analysis
        - recommendation
        - buy
        - sell
        - bull case
        - bear case

        Use evaluation when the user explicitly asks to:
        - evaluate
        - assess
        - rate
        - review as an investment

        Use comparison when the user compares:
        - companies
        - stocks
        - investments

        Use history when the user asks about:
        - history
        - founding
        - origins
        - timeline

        Use leadership when the user asks about:
        - management
        - CEO
        - executives
        - board members
        - founders

        Use products when the user asks about:
        - products
        - services
        - business segments

        Use general_information for:
        - tell me about
        - what is
        - who is
        - company overview
        - business overview

        IMPORTANT:

        Do NOT classify something as analysis merely because a company name is mentioned.

        A company name alone is usually general_information.
        
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
            "intent": "analysis",
            "companies": [
                {{
                    "name": "NVIDIA",
                    "ticker": "NVDA"
                }}
            ]
        }}
        
        {{
            "is_company_request": true,
            "intent": "history",
            "companies": [
                {{
                    "name": "Intel",
                    "ticker": "INTC"
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

        if not isinstance(
            response,
            dict
        ):
            fallback_entities = explicit_entities + known_company_entities
            return {
                "is_company_request": bool(
                    fallback_entities
                ),
                "intent": "general_information",
                "companies": fallback_entities
            }

        model_response = response.get(
            "response",
            ""
        )

        if not model_response:
            fallback_entities = explicit_entities + known_company_entities
            return {
                "is_company_request": bool(
                    fallback_entities
                ),
                "intent": "general_information",
                "companies": fallback_entities
            }

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
                + known_company_entities
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

                ticker = company.get("ticker")
                if isinstance(ticker, str):
                    ticker = ticker.strip().upper() or None
                else:
                    ticker = None

                if known_company_entities:
                    mentioned = any(
                        re.search(
                            rf"\b{re.escape(candidate)}\b",
                            str(message or ""),
                            re.IGNORECASE
                        )
                        for candidate in (
                            name,
                            ticker or ""
                        )
                        if candidate
                    )
                    if not mentioned:
                        continue

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

            intent = result.get(
                "intent",
                "general_information"
            )

            return {
                "is_company_request":
                    bool(
                        merged_companies
                    ),
                "intent":
                    intent,
                "companies":
                    merged_companies
            }


        except Exception as e:

            print(
                f"JSON Parse Error: {e}"
            )


            fallback_entities = explicit_entities + known_company_entities
            if fallback_entities:

                return {
                    "is_company_request": True,
                    "intent": "general_information",
                    "companies": fallback_entities,
                    "error": str(e)
                }


            return {
                "is_company_request": False,
                "intent": "general_information",
                "companies": [],
                "error": str(e)
            }