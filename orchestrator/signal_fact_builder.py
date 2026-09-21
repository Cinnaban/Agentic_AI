class SignalFactBuilder:
    def _direction(
        self,
        value
    ):

        if not isinstance(
            value,
            (
                int,
                float
            )
        ):
            return "unknown"

        if value > 0:
            return "positive"

        if value < 0:
            return "negative"

        return "neutral"

    def build(
        self,
        quant_data
    ):

        facts = {
            "directions": {},
            "agreements": [],
            "conflicts": [],
            "horizon_differences": []
        }

        if not isinstance(
            quant_data,
            dict
        ):
            return facts

        results = quant_data.get(
            "results",
            []
        )

        if (
            not isinstance(
                results,
                list
            )
            or not results
        ):
            return facts

        analysis = (
            results[0].get(
                "analysis",
                {}
            )
        )

        if not isinstance(
            analysis,
            dict
        ):
            
            
            return facts
        
        forecast_fields = {
            "forecast_5d":
                analysis.get(
                    "forecast_5d"
                ),

            "forecast_30d":
                analysis.get(
                    "forecast_30d"
                ),

            "forecast_90d":
                analysis.get(
                    "forecast_90d"
                ),

            "forecast_180d":
                analysis.get(
                    "forecast_180d"
                )
        }
        for field, value in (
            forecast_fields.items()
        ):

            facts["directions"][field] = {
                "value": value,
                "direction":
                    self._direction(
                        value
                    )
            }

        short_term = [
            facts["directions"]
            .get(
                "forecast_5d",
                {}
            )
            .get("direction"),

            facts["directions"]
            .get(
                "forecast_30d",
                {}
            )
            .get("direction"),

            facts["directions"]
            .get(
                "forecast_90d",
                {}
            )
            .get("direction")
        ]


        long_term = (
            facts["directions"]
            .get(
                "forecast_180d",
                {}
            )
            .get("direction")
        )
        if (
            short_term
            and all(
                direction == "negative"
                for direction
                in short_term
            )
            and long_term == "positive"
        ):

            facts[
                "horizon_differences"
            ].append(
                {
                    "fields": [
                        "forecast_5d",
                        "forecast_30d",
                        "forecast_90d",
                        "forecast_180d"
                    ],
                    "description":
                        "Short-term forecasts are negative "
                        "while the 180-day forecast is positive."
                }
            )
        recommendation = analysis.get(
            "recommendation"
        )

        forecast_consensus = analysis.get(
            "forecast_consensus"
        )

        predictive_rating = analysis.get(
            "predictive_rating"
        )
        if (
            recommendation == "Bearish"
            and forecast_consensus == "Bearish"
        ):

            facts[
                "agreements"
            ].append(
                {
                    "fields": [
                        "recommendation",
                        "forecast_consensus"
                    ],
                    "description":
                        "Recommendation and forecast "
                        "consensus are both bearish."
                }
            )
        if (
            predictive_rating == "Strong Buy"
            and (
                recommendation == "Bearish"
                or forecast_consensus == "Bearish"
            )
        ):

            facts[
                "conflicts"
            ].append(
                {
                    "fields": [
                        "predictive_rating",
                        "recommendation",
                        "forecast_consensus"
                    ],
                    "description":
                        "Strong Buy predictive rating "
                        "conflicts with bearish "
                        "directional signals."
                }
            )
        return facts