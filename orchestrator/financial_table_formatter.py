from orchestrator.quant_summary_reviewer import QuantSummaryReviewer


class FinancialTableFormatter:
                
   
        
    def format_value(
        self,
        metric
    ):
        if not isinstance(
            metric,
            dict
        ):
            return "N/A"

        value = metric.get(
            "value"
        )

        metric_type = metric.get(
            "type"
        )

        if value is None:
            return "N/A"

        if metric_type == "currency":
            if isinstance(
                value,
                (int, float)
            ):
                return f"${value:,.2f}"

        if metric_type == "large_currency":
            if isinstance(
                value,
                (int, float)
            ):
                absolute_value = abs(
                    value
                )

                if absolute_value >= 1_000_000_000_000:
                    return (
                        f"${value / 1_000_000_000_000:.2f}T"
                    )

                if absolute_value >= 1_000_000_000:
                    return (
                        f"${value / 1_000_000_000:.2f}B"
                    )

                if absolute_value >= 1_000_000:
                    return (
                        f"${value / 1_000_000:.2f}M"
                    )

                return f"${value:,.2f}"

        if metric_type == "multiple":
            if isinstance(
                value,
                (int, float)
            ):
                return f"{value:.2f}x"

        if metric_type == "percent":
            if isinstance(
                value,
                (int, float)
            ):
                return f"{value:.2f}%"

        if metric_type == "change_percent":
            if isinstance(
                value,
                (int, float)
            ):
                return f"{value:+.2f}%"

        if metric_type == "score":
            if isinstance(
                value,
                (int, float)
            ):
                return f"{value}/100"

        if metric_type == "number":
            if isinstance(
                value,
                (int, float)
            ):
                return f"{value:.2f}"

        return str(value)
    
    def build_category_table(
        self,
        metrics,
        category
    ):
        category_metrics = {
            key: metric
            for key, metric in metrics.items()
            if (
                isinstance(
                    metric,
                    dict
                )
                and metric.get(
                    "category"
                ) == category
            )
        }

        if not category_metrics:
            return ""

        return self.build_single_table(
            category_metrics
        )
    
    def build_sectioned_tables(
        self,
        metrics
    ):
        sections = []

        categories = [
            (
                "Market & Valuation",
                "market"
            ),
            (
                "Reported Financials",
                "reported_financials"
            ),
            (
                "Quantitative Models",
                "quantitative_models"
            ),
            (
                "Risk",
                "risk"
            )
        ]

        for title, category in categories:

            table = self.build_category_table(
                metrics,
                category
            )

            if table:
                section = (
                    f"**{title}**\n\n"
                    + table
                )

                if category == "quantitative_models":
                    review = QuantSummaryReviewer().build(
                        metrics
                    )

                    if review:
                        section += "\n\n" + review

                sections.append(
                    section
                )

        return "\n\n".join(
            sections
        )
    
    def format_source(
            self,
            source
        ):
            source_labels = {
                "quant": "Quant",
                "risk": "Risk",
                "sec": "SEC",
                "market": "Market",
                "fred": "FRED"
            }
    
            return source_labels.get(
                source,
                source
            )
    
    def build_single_table(
        self,
        metrics
    ):
        rows = [
            "| Metric | Value | Source |",
            "|---|---:|---|"
        ]

        for metric in metrics.values():

            label = metric.get(
                "label",
                ""
            )

            display = self.format_value(
                metric
            )

            source = self.format_source(
                metric.get(
                    "source",
                    ""
                )
            )      

            rows.append(
                f"| {label} | "
                f"{display} | "
                f"{source} |"
            )

        return "\n".join(
            rows
        )
    
    def build_comparison_table(
            self,
            company_metrics
        ):
            if not isinstance(
                company_metrics,
                dict
            ):
                return ""

            tickers = list(
                company_metrics.keys()
            )

            if not tickers:
                return ""

            metric_keys = []

            for ticker in tickers:
                metrics = company_metrics.get(
                    ticker,
                    {}
                )

                if not isinstance(
                    metrics,
                    dict
                ):
                    continue

                for key in metrics.keys():
                    if key not in metric_keys:
                        metric_keys.append(
                            key
                        )

            header = (
                "| Metric | "
                + " | ".join(
                    tickers
                )
                + " |"
            )

            separator = (
                "|---|"
                + "---:|" * len(
                    tickers
                )
            )

            rows = [
                header,
                separator
            ]

            for key in metric_keys:

                label = key

                for ticker in tickers:
                    metric = (
                        company_metrics
                        .get(
                            ticker,
                            {}
                        )
                        .get(
                            key
                        )
                    )

                    if isinstance(
                        metric,
                        dict
                    ):
                        label = metric.get(
                            "label",
                            key
                        )

                        break

                values = []

                for ticker in tickers:

                    metric = (
                        company_metrics
                        .get(
                            ticker,
                            {}
                        )
                        .get(
                            key
                        )
                    )

                    if isinstance(
                        metric,
                        dict
                    ):
                        value = (
                            self.format_value(
                                metric
                            )
                        )
                    else:
                        value = "N/A"

                    values.append(
                        value
                    )

                row = (
                    f"| {label} | "
                    + " | ".join(
                        values
                    )
                    + " |"
                )

                rows.append(
                    row
                )

            return "\n".join(
                rows
            )

            