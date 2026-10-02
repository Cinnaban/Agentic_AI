class FormulaEvaluator:

    ALLOWED_DIRECTIONS = {
        "higher_is_better",
        "lower_is_better"
    }


    def evaluate(
        self,
        formula,
        company_metrics
    ):

        if not isinstance(
            formula,
            dict
        ):

            return {
                "status":
                    "failed",

                "error":
                    "Invalid formula"
            }


        if not isinstance(
            company_metrics,
            dict
        ):

            return {
                "status":
                    "failed",

                "error":
                    "Invalid company metrics"
            }


        components = formula.get(
            "components",
            []
        )


        if not isinstance(
            components,
            list
        ):

            return {
                "status":
                    "failed",

                "error":
                    "Invalid formula components"
            }


        valid_components = []


        for component in components:

            if not isinstance(
                component,
                dict
            ):

                continue


            metric = component.get(
                "metric"
            )

            weight = component.get(
                "weight"
            )

            direction = component.get(
                "direction"
            )


            if not isinstance(
                metric,
                str
            ):

                continue


            if not isinstance(
                weight,
                (
                    int,
                    float
                )
            ):

                continue


            if direction not in (
                self.ALLOWED_DIRECTIONS
            ):

                continue


            valid_components.append(
                {
                    "metric":
                        metric,

                    "weight":
                        float(
                            weight
                        ),

                    "direction":
                        direction,

                    "reason":
                        component.get(
                            "reason",
                            ""
                        )
                }
            )


        if not valid_components:

            return {
                "status":
                    "failed",

                "error":
                    "No valid formula components"
            }


        normalized_metrics = (
            self._normalize_metrics(
                company_metrics=(
                    company_metrics
                ),

                components=(
                    valid_components
                )
            )
        )


        scores = {}


        for ticker, metrics in (
            normalized_metrics.items()
        ):

            score = 0.0

            weight_used = 0.0

            component_scores = {}


            for component in (
                valid_components
            ):

                metric = component[
                    "metric"
                ]

                weight = component[
                    "weight"
                ]


                value = metrics.get(
                    metric
                )


                if value is None:

                    continue


                weighted_value = (
                    value
                    * weight
                )


                score += (
                    weighted_value
                )


                weight_used += abs(
                    weight
                )


                component_scores[
                    metric
                ] = {
                    "normalized_value":
                        value,

                    "weight":
                        weight,

                    "weighted_value":
                        weighted_value
                }


            if weight_used:

                score = (
                    score
                    / weight_used
                )


            scores[
                ticker
            ] = {
                "score":
                    round(
                        score,
                        6
                    ),

                "components":
                    component_scores
            }


        ranking = sorted(
            scores.items(),

            key=lambda item: (
                item[
                    1
                ][
                    "score"
                ]
            ),

            reverse=True
        )


        return {
            "status":
                "completed",

            "formula":
                formula,

            "scores":
                scores,

            "ranking": [
                {
                    "ticker":
                        ticker,

                    "score":
                        result[
                            "score"
                        ]
                }

                for ticker, result
                in ranking
            ]
        }


    def _normalize_metrics(
        self,
        company_metrics,
        components
    ):

        normalized = {
            ticker: {}
            for ticker
            in company_metrics
        }


        for component in components:

            metric = component[
                "metric"
            ]

            direction = component[
                "direction"
            ]


            values = {}


            for ticker, metrics in (
                company_metrics.items()
            ):

                if not isinstance(
                    metrics,
                    dict
                ):

                    continue


                value = metrics.get(
                    metric
                )


                if isinstance(
                    value,
                    (
                        int,
                        float
                    )
                ):

                    values[
                        ticker
                    ] = float(
                        value
                    )


            if not values:

                continue


            minimum = min(
                values.values()
            )

            maximum = max(
                values.values()
            )


            for ticker, value in (
                values.items()
            ):

                if maximum == minimum:

                    normalized_value = (
                        0.5
                    )


                else:

                    normalized_value = (
                        (
                            value
                            - minimum
                        )
                        /
                        (
                            maximum
                            - minimum
                        )
                    )


                if (
                    direction
                    == "lower_is_better"
                ):

                    normalized_value = (
                        1.0
                        - normalized_value
                    )


                normalized[
                    ticker
                ][
                    metric
                ] = (
                    normalized_value
                )


        return normalized