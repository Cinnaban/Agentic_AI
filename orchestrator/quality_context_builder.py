class QualityContextBuilder:

    def build(
        self,
        execution_results
    ):

        context = {
            "agents_present":
                list(
                    execution_results.keys()
                ),

            "failed_agents": [],

            "signal_reconciliation":
                execution_results.get(
                    "signal_reconciliation"
                ),

            "risk":
                execution_results.get(
                    "risk"
                )
        }

        for (
            agent_name,
            result
        ) in execution_results.items():

            if (
                isinstance(
                    result,
                    dict
                )
                and result.get(
                    "status"
                ) == "failed"
            ):

                context[
                    "failed_agents"
                ].append(
                    agent_name
                )
        quant = execution_results.get(
            "quant"
        )

        quant_summary = {}


        if isinstance(
            quant,
            dict
        ):

            quant_results = quant.get(
                "results",
                []
            )

            if (
                isinstance(
                    quant_results,
                    list
                )
                and quant_results
            ):

                analysis = (
                    quant_results[0]
                    .get(
                        "analysis",
                        {}
                    )
                )

                if isinstance(
                    analysis,
                    dict
                ):

                    quant_summary = {
                        "prediction_pct":
                            analysis.get(
                                "prediction_pct"
                            ),

                        "confidence":
                            analysis.get(
                                "confidence"
                            ),

                        "recommendation":
                            analysis.get(
                                "recommendation"
                            ),

                        "regression_rating":
                            analysis.get(
                                "regression_rating"
                            ),

                        "predictive_rating":
                            analysis.get(
                                "predictive_rating"
                            ),

                        "stability_rating":
                            analysis.get(
                                "stability_rating"
                            ),

                        "forecast_rating":
                            analysis.get(
                                "forecast_rating"
                            ),

                        "forecast_consensus":
                            analysis.get(
                                "forecast_consensus"
                            ),

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
                            ),

                        "momentum_rating":
                            analysis.get(
                                "momentum_rating"
                            )
                    }


                context[
                    "quant_summary"
                ] = quant_summary
                
                return context