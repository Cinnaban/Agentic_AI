class FormulaMetricExtractor:

    ALLOWED_METRICS = {
        "growth_score",
        "profitability_score",
        "financial_strength_score",
        "shareholder_score",
        "valuation_score",
        "momentum_score",
        "risk_score",
        "beta",
        "debt_to_equity",
        "current_ratio",
        "profit_margin",
        "operating_margin",
        "roe",
        "revenue_growth",
        "earnings_growth"
    }


    def extract(
        self,
        company_results
    ):

        if not isinstance(
            company_results,
            dict
        ):

            return {
                "company_metrics":
                    {},

                "available_metrics":
                    []
            }


        company_metrics = {}

        globally_available = set()


        for ticker, result in (
            company_results.items()
        ):

            if not isinstance(
                result,
                dict
            ):

                continue


            metrics = {}


            quant = result.get(
                "quant"
            )


            analysis = (
                self._extract_quant_analysis(
                    quant
                )
            )


            for metric in (
                self.ALLOWED_METRICS
            ):

                value = analysis.get(
                    metric
                )


                if isinstance(
                    value,
                    (
                        int,
                        float
                    )
                ):

                    metrics[
                        metric
                    ] = float(
                        value
                    )


            risk = result.get(
                "risk"
            )


            if isinstance(
                risk,
                dict
            ):

                risk_score = risk.get(
                    "risk_score"
                )


                if isinstance(
                    risk_score,
                    (
                        int,
                        float
                    )
                ):

                    metrics[
                        "risk_score"
                    ] = float(
                        risk_score
                    )


            company_metrics[
                ticker
            ] = metrics


            globally_available.update(
                metrics.keys()
            )


        consistent_metrics = []


        if company_metrics:

            for metric in sorted(
                globally_available
            ):

                if all(
                    metric
                    in company_data

                    for company_data
                    in company_metrics.values()
                ):

                    consistent_metrics.append(
                        metric
                    )


        return {
            "company_metrics":
                company_metrics,

            "available_metrics":
                consistent_metrics
        }


    def _extract_quant_analysis(
        self,
        quant
    ):

        if not isinstance(
            quant,
            dict
        ):

            return {}


        analysis = quant.get(
            "analysis"
        )


        if isinstance(
            analysis,
            dict
        ):

            return analysis


        return {}