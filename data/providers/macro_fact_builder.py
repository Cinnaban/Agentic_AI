class MacroFactBuilder:

    def _normalize_observation(
        self,
        observation,
        label,
        unit
    ):

        if not isinstance(
            observation,
            dict
        ):
            return {}

        value = observation.get(
            "value"
        )

        if value is None:
            return {}

        try:
            numeric_value = float(
                value
            )

        except (
            TypeError,
            ValueError
        ):
            return {}

        return {
            "series_id":
                observation.get(
                    "series_id"
                ),

            "label":
                label,

            "value":
                numeric_value,

            "unit":
                unit,

            "observation_date":
                observation.get(
                    "observation_date"
                ),

            "source":
                observation.get(
                    "source",
                    "FRED"
                )
        }
        
    def _percent_change(
        self,
        current,
        previous
    ):

        if not isinstance(
            current,
            (
                int,
                float
            )
        ):
            return None

        if not isinstance(
            previous,
            (
                int,
                float
            )
        ):
            return None

        if previous == 0:
            return None

        return (
            (
                current - previous
            )
            / previous
        ) * 100
        
    def _get_history(
        self,
        macro_context,
        category
    ):

        history = macro_context.get(
            "history",
            {}
        )

        if not isinstance(
            history,
            dict
        ):
            return []

        observations = history.get(
            category,
            []
        )

        if not isinstance(
            observations,
            list
        ):
            return []

        return [
            observation
            for observation
            in observations
            if isinstance(
                observation,
                dict
            )
        ]
        
    def build(
        self,
        macro_context
    ):

        result = {
            "interest_rates": {},
            "inflation_index": {},
            "unemployment": {},
            "real_gdp": {}
        }

        inflation_history = (
            self._get_history(
                macro_context,
                "inflation"
            )
        )

        if len(
            inflation_history
        ) >= 13:

            current_cpi = (
                inflation_history[0]
                .get(
                    "value"
                )
            )

            prior_year_cpi = (
                inflation_history[12]
                .get(
                    "value"
                )
            )

            inflation_yoy = (
                self._percent_change(
                    current_cpi,
                    prior_year_cpi
                )
            )

            if inflation_yoy is not None:

                result[
                    "inflation_yoy"
                ] = {
                    "label":
                        "CPI Year-over-Year Change",

                    "value":
                        inflation_yoy,

                    "unit":
                        "percent",

                    "observation_date":
                        inflation_history[0]
                        .get(
                            "observation_date"
                        ),

                    "comparison_date":
                        inflation_history[12]
                        .get(
                            "observation_date"
                        ),

                    "source":
                        "FRED",

                    "derived":
                        True
                }
            employment_history = (
                self._get_history(
                    macro_context,
                    "employment"
                )
            )

            if len(
                employment_history
            ) >= 2:

                current_unemployment = (
                    employment_history[0]
                    .get(
                        "value"
                    )
                )

                previous_unemployment = (
                    employment_history[1]
                    .get(
                        "value"
                    )
                )

                if (
                    isinstance(
                        current_unemployment,
                        (
                            int,
                            float
                        )
                    )
                    and isinstance(
                        previous_unemployment,
                        (
                            int,
                            float
                        )
                    )
                ):

                    result[
                        "unemployment_change"
                    ] = {
                        "label":
                            "Unemployment Rate Change",

                        "value":
                            (
                                current_unemployment
                                - previous_unemployment
                            ),

                        "unit":
                            "percentage_points",

                        "observation_date":
                            employment_history[0]
                            .get(
                                "observation_date"
                            ),

                        "comparison_date":
                            employment_history[1]
                            .get(
                                "observation_date"
                            ),

                        "source":
                            "FRED",

                        "derived":
                            True
                    }
                    
            rate_history = (
                self._get_history(
                    macro_context,
                    "interest_rates"
                )
            )

            if len(
                rate_history
            ) >= 2:

                current_rate = (
                    rate_history[0]
                    .get(
                        "value"
                    )
                )

                previous_rate = (
                    rate_history[1]
                    .get(
                        "value"
                    )
                )

                if (
                    isinstance(
                        current_rate,
                        (
                            int,
                            float
                        )
                    )
                    and isinstance(
                        previous_rate,
                        (
                            int,
                            float
                        )
                    )
                ):

                    result[
                        "interest_rate_change"
                    ] = {
                        "label":
                            "Federal Funds Rate Change",

                        "value":
                            current_rate
                            - previous_rate,

                        "unit":
                            "percentage_points",

                        "observation_date":
                            rate_history[0]
                            .get(
                                "observation_date"
                            ),

                        "comparison_date":
                            rate_history[1]
                            .get(
                                "observation_date"
                            ),

                        "source":
                            "FRED",

                        "derived":
                            True
                    }
                    
            gdp_history = (
                self._get_history(
                    macro_context,
                    "economic_growth"
                )
            )

            if len(
                gdp_history
            ) >= 2:

                current_gdp = (
                    gdp_history[0]
                    .get(
                        "value"
                    )
                )

                previous_gdp = (
                    gdp_history[1]
                    .get(
                        "value"
                    )
                )

                gdp_change = (
                    self._percent_change(
                        current_gdp,
                        previous_gdp
                    )
                )

                if gdp_change is not None:

                    result[
                        "real_gdp_change"
                    ] = {
                        "label":
                            "Real GDP Period-over-Period Change",

                        "value":
                            gdp_change,

                        "unit":
                            "percent",

                        "observation_date":
                            gdp_history[0]
                            .get(
                                "observation_date"
                            ),

                        "comparison_date":
                            gdp_history[1]
                            .get(
                                "observation_date"
                            ),

                        "source":
                            "FRED",

                        "derived":
                            True
                    }

        if not isinstance(
            macro_context,
            dict
        ):
            return result
        result[
            "interest_rates"
        ] = (
            self._normalize_observation(
                macro_context.get(
                    "interest_rates"
                ),
                label=(
                    "Federal Funds Effective Rate"
                ),
                unit="percent"
            )
        )

        result[
            "inflation_index"
        ] = (
            self._normalize_observation(
                macro_context.get(
                    "inflation"
                ),
                label=(
                    "Consumer Price Index"
                ),
                unit="index"
            )
        )

        result[
            "unemployment"
        ] = (
            self._normalize_observation(
                macro_context.get(
                    "employment"
                ),
                label=(
                    "Unemployment Rate"
                ),
                unit="percent"
            )
        )

        result[
            "real_gdp"
        ] = (
            self._normalize_observation(
                macro_context.get(
                    "economic_growth"
                ),
                label=(
                    "Real Gross Domestic Product"
                ),
                unit="index_or_level"
            )
        )


        return result
    