import os
import requests

class SECProvider:

    def __init__(self):

        self.base_url = (
            "https://data.sec.gov"
        )
        self.ticker_url = (
            "https://www.sec.gov/files/"
            "company_tickers.json"
        )
        self.user_agent = os.getenv(
            "SEC_USER_AGENT"
        )
# IS CONFIGURED
    def is_configured(
        self
    ):
        return bool(
            self.user_agent
        )
# GET
    def _get(
        self,
        url
    ):

        if not self.is_configured():

            return None

        headers = {
            "User-Agent":
                self.user_agent,

            "Accept-Encoding":
                "gzip, deflate"
        }

        try:

            response = requests.get(
                url,
                headers=headers,
                timeout=15
            )

        except requests.RequestException:

            return None

        if response.status_code != 200:

            return None

        try:

            return response.json()

        except ValueError:

            return None

    # GET RECENT FILINGS
    def get_recent_filings(
        self,
        company
    ):

        cik = self.resolve_cik(
            company
        )

        if not cik:
            return []

        url = (
            self.base_url
            + "/submissions/"
            + f"CIK{cik}.json"
        )

        data = self._get(
            url
        )

        if not isinstance(
            data,
            dict
        ):
            return []

        filings = (
            data.get(
                "filings",
                {}
            )
            .get(
                "recent",
                {}
            )
        )

        if not isinstance(
            filings,
            dict
        ):
            return []

        return {
            "cik":
                cik,

            "company_name":
                data.get(
                    "name"
                ),

            "filings":
                filings
        }

# HEALTH CHECK        
    def health_check(
        self
    ):
        if not self.is_configured():
            return {
                "configured": False,
                "reachable": False
            }
        data = self._get(
            (
                self.base_url
                + "/submissions/"
                + "CIK0000320193.json"
            )
        )
        return {
            "configured": True,
            "reachable":
                isinstance(
                    data,
                    dict
                )
        }
# GET COMPANY FACTS
    def get_company_facts(
        self,
        company
    ):

        cik = self.resolve_cik(
            company
        )

        if not cik:
            return {}

        url = (
            self.base_url
            + "/api/xbrl/companyfacts/"
            + f"CIK{cik}.json"
        )

        data = self._get(
            url
        )

        if not isinstance(
            data,
            dict
        ):
            return {}

        return {
            "cik":
                cik,

            "entity_name":
                data.get(
                    "entityName"
                ),

            "facts":
                data.get(
                    "facts",
                    {}
                ),

            "source":
                "SEC"
        }
# RESOLVE
    def resolve_cik(
        self,
        company
    ):

        if not isinstance(
            company,
            dict
        ):

            return None

        ticker = company.get(
            "ticker"
        )

        if not ticker:

            return None

        ticker = (
            str(ticker)
            .strip()
            .upper()
        )

        data = self._get(
            self.ticker_url
        )

        if not isinstance(
            data,
            dict
        ):

            return None

        for entry in data.values():

            if not isinstance(
                entry,
                dict
            ):

                continue

            entry_ticker = (
                str(
                    entry.get(
                        "ticker",
                        ""
                    )
                )
                .strip()
                .upper()
            )

            if entry_ticker != ticker:

                continue

            cik_value = entry.get(
                "cik_str"
            )

            if cik_value is None:

                return None

            return str(
                cik_value
            ).zfill(10)

        return None
# Normalize Recent Filings 
    def normalize_recent_filings(
        self,
        company,
        allowed_forms=None,
        limit=10
    ):

        if allowed_forms is None:

            allowed_forms = {
                "10-K",
                "10-Q",
                "8-K"
            }

        filing_data = (
            self.get_recent_filings(
                company
            )
        )

        if not isinstance(
            filing_data,
            dict
        ):

            return []

        recent = filing_data.get(
            "filings",
            {}
        )

        if not isinstance(
            recent,
            dict
        ):

            return []
        
        forms = recent.get(
            "form",
            []
        )

        filing_dates = recent.get(
            "filingDate",
            []
        )

        accession_numbers = recent.get(
            "accessionNumber",
            []
        )

        primary_documents = recent.get(
            "primaryDocument",
            []
        )
        normalized = []

        record_count = min(
            len(forms),
            len(filing_dates),
            len(accession_numbers),
            len(primary_documents)
        )
        for index in range(
            record_count
        ):

            form = forms[index]

            if form not in allowed_forms:
                continue

            normalized.append(
                {
                    "form":
                        form,

                    "filing_date":
                        filing_dates[index],

                    "accession_number":
                        accession_numbers[index],

                    "primary_document":
                        primary_documents[index],

                    "source":
                        "SEC"
                }
            )

            if len(normalized) >= limit:
                break

        return normalized