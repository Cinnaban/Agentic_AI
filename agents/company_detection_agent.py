# agents/company_detection_agent.py
import json
import re

from data.providers.company_ticker_lookup import CompanyTickerLookup
from agents.ollama_client import OllamaClient
from configs.config import Config

class CompanyDetectionAgent:

    LOOKUP_ACTION = re.compile(
        r"^\s*(?:please\s+)?(?:analyze|analyse|evaluate|assess|review|"
        r"compare|should i buy|should i sell|invest in)\s+",
        re.IGNORECASE
    )
    LOOKUP_SUFFIX = re.compile(
        r"\s+(?:stock|shares?|ticker|company|corporation|incorporated|"
        r"inc\.?|limited|ltd\.?|llc|plc)$",
        re.IGNORECASE
    )

    def __init__(self):
        self.ollama = OllamaClient()
        self.ticker_lookup = CompanyTickerLookup()

    @classmethod
    def _extract_lookup_queries(cls, message):
        text = str(message or "").strip().rstrip("?.!")
        if not text:
            return []

        subject = cls.LOOKUP_ACTION.sub("", text).strip()
        subject = re.sub(
            r"^(?:the\s+)?(?:company|stock|ticker)\s+",
            "",
            subject,
            flags=re.IGNORECASE
        ).strip()
        parts = re.split(
            r"\s*(?:,|;|\band\b|\bvs\.?\b|\bversus\b)\s*",
            subject,
            flags=re.IGNORECASE
        )
        queries = []
        for part in parts:
            candidate = cls.LOOKUP_SUFFIX.sub("", part.strip()).strip()
            if candidate and candidate.casefold() not in {
                query.casefold() for query in queries
            }:
                queries.append(candidate)
            if len(queries) >= 5:
                break
        return queries

    @staticmethod
    def _normalized_name_terms(value):
        ignored = {
            "company", "corporation", "corp", "inc", "incorporated",
            "limited", "ltd", "llc", "plc", "the"
        }
        return {
            term
            for term in re.findall(r"[a-z0-9]+", str(value or "").casefold())
            if term not in ignored
        }

    @classmethod
    def _candidate_matches_name(cls, candidate, name):
        name_terms = cls._normalized_name_terms(name)
        candidate_terms = cls._normalized_name_terms(candidate.get("name"))
        if not name_terms or not candidate_terms:
            return False
        shared_terms = name_terms.intersection(candidate_terms)
        return len(shared_terms) >= min(2, len(name_terms))

    @classmethod
    def _candidate_matches_query(cls, candidate, query):
        return cls._candidate_matches_name(
            candidate,
            query
        )

    @classmethod
    def _company_is_mentioned(cls, company, message):
        company_terms = cls._normalized_name_terms(company)
        message_terms = cls._normalized_name_terms(message)
        if not company_terms or not message_terms:
            return False
        shared_terms = company_terms.intersection(message_terms)
        return len(shared_terms) >= min(2, len(company_terms))

    @staticmethod
    def _is_company_analysis_request(message):
        return bool(re.search(
            r"\b(?:analy[sz]e|analysis|evaluate|evaluation|assess|"
            r"review|compare|history|founding|origins|timeline|"
            r"stock|shares?|ticker|company)\b",
            str(message or ""),
            re.IGNORECASE
        ))

    @classmethod
    def _listing_fallback(
        cls,
        message,
        lookup_queries,
        lookup_candidates
    ):
        if (
            len(lookup_queries) != 1
            or not cls._is_company_analysis_request(message)
        ):
            return None

        candidates = [
            candidate
            for candidate in lookup_candidates
            if (
                candidate.get("quote_type") == "EQUITY"
                and candidate.get("searched_name")
                and cls._candidate_matches_query(
                    candidate,
                    candidate["searched_name"]
                )
            )
        ]
        if not candidates:
            return None

        preferred_exchanges = {
            "NYSE",
            "NASDAQ",
            "NASDAQGS",
            "NASDAQGM",
            "NASDAQCM",
            "NYSE AMERICAN"
        }
        candidate = next(
            (
                item
                for item in candidates
                if str(item.get("exchange") or "").upper()
                in preferred_exchanges
            ),
            candidates[0]
        )
        return {
            "is_company_request": True,
            "intent": "general_information",
            "companies": [{
                "name": candidate["name"],
                "ticker": candidate["symbol"],
                "entity_type": "stock",
                "ticker_source": "Yahoo Finance company search"
            }]
        }

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
    @classmethod
    def _add_lookup_companies(
        cls,
        message,
        lookup_queries,
        lookup_candidates,
        explicit_tickers,
        companies
    ):
        companies = list(companies)
        if len(lookup_queries) < 2 or not re.search(
            r"\b(?:compare|comparison|versus|vs\.?|against|or)\b",
            str(message),
            re.IGNORECASE
        ):
            return companies

        for query in lookup_queries:
            if query.upper() in explicit_tickers:
                continue
            if any(
                cls._company_is_mentioned(item["name"], query)
                for item in companies
            ):
                continue
            matches = [
                item
                for item in lookup_candidates
                if item.get("searched_name") == query
                and item.get("quote_type") in {"EQUITY", "ETF"}
                and cls._normalized_name_terms(query).issubset(
                    cls._normalized_name_terms(item.get("name"))
                )
            ]
            if not matches:
                continue
            best = matches[0]
            if best["symbol"] in {item.get("ticker") for item in companies}:
                continue
            companies.append({
                "name": best["name"],
                "ticker": best["symbol"],
                "entity_type": (
                    "etf" if best.get("quote_type") == "ETF" else "stock"
                ),
                "ticker_source": "Yahoo Finance company search"
            })
        return companies

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
        lookup_queries = self._extract_lookup_queries(message)
        lookup_candidates = []
        for query in lookup_queries:
            for candidate in self.ticker_lookup.search(query):
                candidate = dict(candidate)
                candidate["searched_name"] = query
                if not any(
                    existing.get("symbol") == candidate.get("symbol")
                    and existing.get("searched_name")
                    == candidate.get("searched_name")
                    for existing in lookup_candidates
                ):
                    lookup_candidates.append(candidate)
        
        explicit_ticker_context = (
            ", ".join(
                explicit_tickers
            )
            if explicit_tickers
            else "None"
        )
        lookup_context = json.dumps(
            lookup_candidates,
            indent=2,
            ensure_ascii=False
        )
        
        prompt = f"""
        You are a company detection agent.

        Explicit ticker symbols already detected:

        {explicit_ticker_context}

        Dynamically retrieved public listing candidates:

        {lookup_context or "No listing candidates were retrieved."}
        

        IMPORTANT:

        - Explicit ticker symbols listed above have already
        been preserved deterministically.

        - Do not reinterpret or rename those tickers.

        - Also detect any additional publicly traded
        companies or securities referred to by natural
        language names.

        - Do not omit natural-language companies merely
        because another explicit ticker is present.

        - Use retrieved listing candidates as evidence when
        associating company names with ticker symbols.

        - Never invent or guess a ticker. For natural-language
        company names, use a ticker only when the supplied
        candidates contain the same company and symbol.

        - A search candidate is evidence to evaluate, not proof
        by itself. Match the candidate's company name to the
        organization the user asked about.

        - If the company is identified but no matching listed
        candidate exists, return its name with ticker null.

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
            lookup_fallback = self._listing_fallback(
                message,
                lookup_queries,
                lookup_candidates
            )
            if lookup_fallback:
                return lookup_fallback
            fallback_companies = self._add_lookup_companies(
                message,
                lookup_queries,
                lookup_candidates,
                explicit_tickers,
                explicit_entities
            )
            return {
                "is_company_request": bool(fallback_companies),
                "intent": "general_information",
                "companies": fallback_companies
            }

        model_response = response.get(
            "response",
            ""
        )

        if not model_response:
            lookup_fallback = self._listing_fallback(
                message,
                lookup_queries,
                lookup_candidates
            )
            if lookup_fallback:
                return lookup_fallback
            fallback_companies = self._add_lookup_companies(
                message,
                lookup_queries,
                lookup_candidates,
                explicit_tickers,
                explicit_entities
            )
            return {
                "is_company_request": bool(fallback_companies),
                "intent": "general_information",
                "companies": fallback_companies
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

                if (
                    not self._company_is_mentioned(name, message)
                    and not any(
                        self._candidate_matches_name(candidate, name)
                        for candidate in lookup_candidates
                    )
                ):
                    continue

                matching_candidates = [
                    candidate
                    for candidate in lookup_candidates
                    if self._candidate_matches_name(
                        candidate,
                        name
                    )
                ]

                candidate = next(
                    (
                        item
                        for item in matching_candidates
                        if item.get("symbol") == ticker
                    ),
                    None
                )
                if ticker and ticker not in explicit_tickers:
                    if candidate is None:
                        ticker = None
                    else:
                        company["ticker_source"] = (
                            "Yahoo Finance company search"
                        )
                if not ticker and matching_candidates:
                    preferred_quote_type = (
                        "ETF"
                        if entity_type == "etf"
                        else "EQUITY"
                    )
                    candidate = next(
                        (
                            item
                            for item in matching_candidates
                            if item.get("quote_type")
                            == preferred_quote_type
                        ),
                        matching_candidates[0]
                    )
                    ticker = candidate["symbol"]
                    company["ticker_source"] = (
                        "Yahoo Finance company search"
                    )
                    if candidate.get("quote_type") == "ETF":
                        entity_type = "etf"
                    elif candidate.get("quote_type") == "EQUITY":
                        entity_type = "stock"

                normalized_companies.append(
                    {
                        "name":
                            name,

                        "ticker":
                            ticker,

                        "entity_type":
                            entity_type,

                        "ticker_source":
                            company.get("ticker_source")
                    }
                )

            if not normalized_companies:
                lookup_fallback = self._listing_fallback(
                    message,
                    lookup_queries,
                    lookup_candidates
                )
                if lookup_fallback:
                    normalized_companies = lookup_fallback["companies"]

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

                ticker = company.get("ticker")
                if isinstance(ticker, str):
                    ticker = ticker.strip().upper() or None
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
                            entity_type,

                        "ticker_source":
                            company.get("ticker_source")
                    }
                )

            merged_companies = self._add_lookup_companies(
                message,
                lookup_queries,
                lookup_candidates,
                explicit_tickers,
                merged_companies
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


            fallback_entities = self._add_lookup_companies(
                message,
                lookup_queries,
                lookup_candidates,
                explicit_tickers,
                explicit_entities
            )
            lookup_fallback = self._listing_fallback(
                message,
                lookup_queries,
                lookup_candidates
            )
            if lookup_fallback:
                lookup_fallback["error"] = str(e)
                return lookup_fallback
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