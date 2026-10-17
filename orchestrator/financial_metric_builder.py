class FinancialMetricBuilder:

    def build_comparison(
        self,
        company_results
    ):
        comparison = {}

        if not isinstance(
            company_results,
            dict
        ):
            return comparison

        for ticker, results in (
            company_results.items()
        ):
            if not isinstance(
                results,
                dict
            ):
                continue

            comparison[ticker] = (
                self.build(
                    results
                )
            )

        return comparison

    def build(
        self,
        execution_results
    ):
        if not isinstance(
            execution_results,
            dict
        ):
            return {}

        metrics = {}

        quant = execution_results.get(
            "quant"
        )

        risk = execution_results.get(
            "risk"
        )
        
        market_context = execution_results.get(
            "market_context",
            {}
        )

        if not isinstance(
            market_context,
            dict
        ):
            market_context = {}

        financial_data = market_context.get(
            "financial_data",
            {}
        )

        if not isinstance(
            financial_data,
            dict
        ):
            financial_data = {}
            
        sec_facts = market_context.get(
            "sec_facts",
            {}
        )

        if not isinstance(
            sec_facts,
            dict
        ):
            sec_facts = {}

        sec_fact_values = sec_facts.get(
            "facts",
            {}
        )

        if not isinstance(
            sec_fact_values,
            dict
        ):
            sec_fact_values = {}

        company = market_context.get("company", {})
        is_etf = (
            isinstance(company, dict)
            and company.get("entity_type") == "etf"
        )
        

        quant_analysis = {}

        if isinstance(
            quant,
            dict
        ):
            quant_results = quant.get(
                "results",
                []
            )

            if (
                not quant_results
                and isinstance(quant.get("analysis"), dict)
            ):
                quant_results = [quant]

            if (
                isinstance(
                    quant_results,
                    list
                )
                and quant_results
            ):
                first_result = quant_results[0]

                if isinstance(
                    first_result,
                    dict
                ):
                    quant_analysis = (
                        first_result.get(
                            "analysis",
                            {}
                        )
                    )
                    

        if not isinstance(
            quant_analysis,
            dict
        ):
            quant_analysis = {}
            
        self._add_metric(
            metrics,
            "market_cap",
            "Market Cap",
            financial_data.get(
                "market_cap"
            ),
            "market",
            "large_currency",
            "market"
        )

        self._add_metric(
            metrics,
            "trailing_pe",
            "Trailing P/E",
            financial_data.get(
                "trailing_pe"
            ),
            "market",
            "multiple",
            "market"
        )

        self._add_metric(
            metrics,
            "forward_pe",
            "Forward P/E",
            financial_data.get(
                "forward_pe"
            ),
            "market",
            "multiple",
            "market"
        )

        self._add_metric(
                metrics,
                "dividend_yield",
                "Dividend Yield",
                financial_data.get(
                    "dividend_yield"
                ),
                "market",
                "percent",
                "market"
            )

        price = financial_data.get(
        "price"
        )

        if price is None:
            price = quant_analysis.get(
                "price"
            )

        self._add_metric(
            metrics,
            "price",
            "Price",
            price,
            "market",
            "currency",
            "market"
        )

        beta = financial_data.get(
            "beta"
        )

        if beta is None:
            beta = quant_analysis.get(
                "beta"
            )

        self._add_metric(
            metrics,
            "beta",
            "Beta",
            beta,
            "market",
            "number",
            "market"
        )
        revenue_fact = None if is_etf else self._get_sec_fact(
            sec_fact_values,
            "revenue"
        )

        net_income_fact = None if is_etf else self._get_sec_fact(
            sec_fact_values,
            "net_income"
        )

        operating_income_fact = None if is_etf else self._get_sec_fact(
            sec_fact_values,
            "operating_income"
        )

        assets_fact = None if is_etf else self._get_sec_fact(
            sec_fact_values,
            "assets"
        )

        liabilities_fact = None if is_etf else self._get_sec_fact(
            sec_fact_values,
            "liabilities"
        )

        equity_fact = None if is_etf else self._get_sec_fact(
            sec_fact_values,
            "stockholders_equity"
        )

        cash_fact = None if is_etf else self._get_sec_fact(
            sec_fact_values,
            "cash"
        )

        receivable_fact = None if is_etf else self._get_sec_fact(
            sec_fact_values,
            "accounts_receivable"
        )

        payable_fact = None if is_etf else self._get_sec_fact(
            sec_fact_values,
            "accounts_payable"
        )
        
        if revenue_fact:
            self._add_metric(
                metrics,
                "revenue",
                "Revenue",
                revenue_fact.get(
                    "value"
                ),
                "sec",
                "large_currency",
                "reported_financials",
                metadata={
                    "unit": revenue_fact.get("unit"),
                    "form": revenue_fact.get("form"),
                    "filed": revenue_fact.get("filed"),
                    "period_end": revenue_fact.get(
                        "period_end"
                    ),
                    "fiscal_year": revenue_fact.get(
                        "fiscal_year"
                    ),
                    "fiscal_period": revenue_fact.get(
                        "fiscal_period"
                    )
                }
            )
            
        if net_income_fact:
            self._add_metric(
                metrics,
                "net_income",
                "Net Income",
                net_income_fact.get(
                    "value"
                ),
                "sec",
                "large_currency",
                "reported_financials"
            )
            
        if operating_income_fact:
            self._add_metric(
                metrics,
                "operating_income",
                "Operating Income",
                operating_income_fact.get(
                    "value"
                ),
                "sec",
                "large_currency",
                "reported_financials"
            )
        if assets_fact:
            self._add_metric(
                metrics,
                "assets",
                "Total Assets",
                assets_fact.get(
                    "value"
                ),
                "sec",
                "large_currency",
                "reported_financials"
            )
        if liabilities_fact:
            self._add_metric(
                metrics,
                "liabilities",
                "Total Liabilities",
                liabilities_fact.get(
                    "value"
                ),
                "sec",
                "large_currency",
                "reported_financials"
            )
        if equity_fact:
            self._add_metric(
                metrics,
                "stockholders_equity",
                "Stockholders' Equity",
                equity_fact.get(
                    "value"
                ),
                "sec",
                "large_currency",
                "reported_financials"
            )
            
        if cash_fact:
            self._add_metric(
                metrics,
                "cash",
                "Cash",
                cash_fact.get(
                    "value"
                ),
                "sec",
                "large_currency",
                "reported_financials",
                metadata=self._build_sec_metadata(
                    cash_fact
                )
            )

        self._add_metric(
            metrics,
            "prediction_pct",
            "Prediction",
            quant_analysis.get(
                "prediction_pct"
            ),
            "quant",
            "change_percent",
            "quantitative_models"
        )

        self._add_metric(
            metrics,
            "confidence",
            "Model Confidence",
            quant_analysis.get(
                "confidence"
            ),
            "quant",
            "percent",
            "quantitative_models"
        )

        self._add_metric(
            metrics,
            "recommendation",
            "Model Recommendation",
            quant_analysis.get(
                "recommendation"
            ),
            "quant",
            "text",
            "quantitative_models"
        )

        self._add_metric(
            metrics,
            "predictive_rating",
            "Predictive Rating",
            quant_analysis.get(
                "predictive_rating"
            ),
            "quant",
            "text",
            "quantitative_models"
        )

        self._add_metric(
            metrics,
            "stability_rating",
            "Stability Rating",
            quant_analysis.get(
                "stability_rating"
            ),
            "quant",
            "text",
            "quantitative_models"
        )

        self._add_metric(
            metrics,
            "forecast_rating",
            "Forecast Rating",
            quant_analysis.get(
                "forecast_rating"
            ),
            "quant",
            "text",
            "quantitative_models"
        )

        self._add_metric(
            metrics,
            "forecast_consensus",
            "Forecast Consensus",
            quant_analysis.get(
                "forecast_consensus"
            ),
            "quant",
            "text",
            "quantitative_models"
        )

        self._add_metric(
            metrics,
            "forecast_5d",
            "5-Day Forecast",
            quant_analysis.get(
                "forecast_5d"
            ),
            "quant",
            "change_percent",
            "quantitative_models"
        )

        self._add_metric(
            metrics,
            "forecast_30d",
            "30-Day Forecast",
            quant_analysis.get(
                "forecast_30d"
            ),
            "quant",
            "change_percent",
            "quantitative_models"
        )

        self._add_metric(
            metrics,
            "forecast_90d",
            "90-Day Forecast",
            quant_analysis.get(
                "forecast_90d"
            ),
            "quant",
            "change_percent",
            "quantitative_models"
        )

        self._add_metric(
            metrics,
            "forecast_180d",
            "180-Day Forecast",
            quant_analysis.get(
                "forecast_180d"
            ),
            "quant",
            "change_percent",
            "quantitative_models"
        )

        self._add_metric(
            metrics,
            "momentum_rating",
            "Momentum Rating",
            quant_analysis.get(
                "momentum_rating"
            ),
            "quant",
            "text",
            "quantitative_models"
        )

        self._add_metric(
            metrics,
            "financial_strength_rating",
            "Financial Strength",
            quant_analysis.get(
                "financial_strength_rating"
            ),
            "quant",
            "text",
            "quantitative_models"
        )

        if isinstance(risk, dict):
            self._add_metric(
                metrics,
                "overall_risk",
                "Overall Risk",
                risk.get(
                    "overall_risk"
                ),
                "risk",
                "text",
                "risk",
            )
            self._add_metric(
                metrics,
                "risk_score",
                "Risk Score",
                risk.get(
                    "risk_score"
                ),
                "risk",
                "score",
                "risk"
            )
            self._add_metric(
                metrics,
                "signal_uncertainty",
                "Signal Uncertainty",
                risk.get(
                    "signal_uncertainty"
                ),
                "risk",
                "text",
                "risk"
            )

        return metrics


    def _get_sec_fact(
        self,
        sec_fact_values,
        key
    ):
        if not isinstance(
            sec_fact_values,
            dict
        ):
            return None

        fact = sec_fact_values.get(
            key
        )

        if not isinstance(
            fact,
            dict
        ):
            return None

        return fact

    def _build_sec_metadata(
        self,
        fact
    ):
        return {
            "unit": fact.get("unit"),
            "form": fact.get("form"),
            "filed": fact.get("filed"),
            "period_end": fact.get("period_end"),
            "fiscal_year": fact.get("fiscal_year"),
            "fiscal_period": fact.get(
                "fiscal_period"
            )
        }

    def _add_metric(
        self,
        metrics,
        key,
        label,
        value,
        source,
        metric_type,
        category,
        metadata=None
    ):
        if value is None:
            return

        metric = {
            "label": label,
            "value": value,
            "source": source,
            "type": metric_type,
            "category": category
        }
        
        if isinstance(
            metadata,
            dict
        ):
            metric[
                "metadata"
            ] = metadata

        metrics[
            key
        ] = metric