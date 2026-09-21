import os
import requests

class MacroProvider:

    def __init__(self):

        self.base_url = (
            "https://api.stlouisfed.org"
            "/fred/series/observations"
        )

        self.api_key = os.getenv(
            "FRED_API_KEY"
        )
    def is_configured(
        self
    ):

        return bool(
            self.api_key
        )
    def _get_latest_observation(
        self,
        series_id
    ):

        if not self.is_configured():
            return None

        params = {
            "series_id":
                series_id,

            "api_key":
                self.api_key,

            "file_type":
                "json",

            "sort_order":
                "desc",

            "limit":
                10
        }

        try:

            response = requests.get(
                self.base_url,
                params=params,
                timeout=15
            )

        except requests.RequestException:

            return None

        if response.status_code != 200:
            return None

        try:

            data = response.json()

        except ValueError:

            return None

        observations = data.get(
            "observations",
            []
        )

        if not isinstance(
            observations,
            list
        ):

            return None

        for observation in observations:

            if not isinstance(
                observation,
                dict
            ):
                continue

            value = observation.get(
                "value"
            )

            if value in {
                None,
                "."
            }:
                continue

            return {
                "series_id":
                    series_id,

                "value":
                    value,

                "observation_date":
                    observation.get(
                        "date"
                    ),

                "source":
                    "FRED"
            }

        return None
    
    def _get_observations(
        self,
        series_id,
        limit=24
    ):

        if not self.is_configured():
            return []

        params = {
            "series_id":
                series_id,

            "api_key":
                self.api_key,

            "file_type":
                "json",

            "sort_order":
                "desc",

            "limit":
                limit
        }

        try:

            response = requests.get(
                self.base_url,
                params=params,
                timeout=15
            )

        except requests.RequestException:

            return []

        if response.status_code != 200:
            return []

        try:

            data = response.json()

        except ValueError:

            return []

        observations = data.get(
            "observations",
            []
        )

        if not isinstance(
            observations,
            list
        ):
            return []

        normalized = []

        for observation in observations:

            if not isinstance(
                observation,
                dict
            ):
                continue

            value = observation.get(
                "value"
            )

            if value in {
                None,
                "."
            }:
                continue

            try:

                numeric_value = float(
                    value
                )

            except (
                TypeError,
                ValueError
            ):
                continue

            normalized.append(
                {
                    "value":
                        numeric_value,

                    "observation_date":
                        observation.get(
                            "date"
                        )
                }
            )

        return normalized
    
    def get_context(
        self
    ):

        if not self.is_configured():

            return {
                "interest_rates": {},
                "inflation": {},
                "employment": {},
                "economic_growth": {},
                "source": None
            }

        interest_rates = (
            self._get_latest_observation(
                "FEDFUNDS"
            )
        )

        inflation = (
            self._get_latest_observation(
                "CPIAUCSL"
            )
        )

        employment = (
            self._get_latest_observation(
                "UNRATE"
            )
        )

        economic_growth = (
            self._get_latest_observation(
                "GDPC1"
            )
        )

        return {
            "interest_rates":
                interest_rates or {},

            "inflation":
                inflation or {},

            "employment":
                employment or {},

            "economic_growth":
                economic_growth or {},

            "source":
                "FRED",
                
            "history": {
                "interest_rates":
                    self._get_observations(
                        "FEDFUNDS",
                        limit=24
                    ),

                "inflation":
                    self._get_observations(
                        "CPIAUCSL",
                        limit=24
                    ),

                "employment":
                    self._get_observations(
                        "UNRATE",
                        limit=24
                    ),

                "economic_growth":
                    self._get_observations(
                        "GDPC1",
                        limit=12
                    )
            },
            
        }