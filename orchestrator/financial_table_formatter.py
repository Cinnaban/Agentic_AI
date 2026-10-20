from orchestrator.quant_summary_reviewer import QuantSummaryReviewer
from orchestrator.table_format import table


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
        metrics,
        evidence=None
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
                        metrics,
                        evidence
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
            [
                metric.get("label", ""),
                self.format_value(metric),
                self.format_source(metric.get("source", ""))
            ]
            for metric in metrics.values()
        ]

        return table(
            ["Metric", "Value", "Source"],
            rows,
            aligns="lrl"
        )

    def build_comparison_table(
        self,
        company_metrics
    ):
        if not isinstance(company_metrics, dict) or not company_metrics:
            return ""

        tickers = list(company_metrics.keys())
        categories = [
            ("Market & Valuation", "market"),
            ("Reported Financials", "reported_financials"),
            ("Quantitative Models", "quantitative_models"),
            ("Risk", "risk"),
        ]
        sections = []
        used = set()

        def rows_for(category):
            keys = []
            for ticker in tickers:
                metrics = company_metrics.get(ticker) or {}
                for key, metric in metrics.items():
                    if (
                        isinstance(metric, dict)
                        and (category is None or metric.get("category") == category)
                        and key not in keys
                        and key not in used
                    ):
                        keys.append(key)
            rows = []
            for key in keys:
                label, values = key, []
                for ticker in tickers:
                    metric = (company_metrics.get(ticker) or {}).get(key)
                    if isinstance(metric, dict):
                        label = metric.get("label", key)
                        formatted = self.format_value(metric)
                    else:
                        formatted = "-"
                    values.append(formatted)
                if all(v in ("-", "N/A", "", "None") for v in values):
                    continue
                rows.append([label] + values)
                used.add(key)
            return rows

        for title, category in categories:
            rows = rows_for(category)
            if rows:
                sections.append(
                    f"**{title}**\n\n"
                    + table(["Metric"] + tickers, rows, aligns="l" + "r" * len(tickers))
                )
        rest = rows_for(None)
        if rest:
            sections.append(
                "**Other Metrics**\n\n"
                + table(["Metric"] + tickers, rest, aligns="l" + "r" * len(tickers))
            )
        return "\n\n".join(sections)
