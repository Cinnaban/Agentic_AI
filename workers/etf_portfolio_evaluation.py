import math


def _is_finite_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _format_percent(value, multiplier=1.0):
    if not _is_finite_number(value):
        return None
    return f"{value * multiplier:.2f}%"


def _format_number(value):
    if not _is_finite_number(value):
        return None
    return f"{value:.2f}"


def generate_etf_portfolio_appendix(holdings):
    holdings = [
        holding
        for holding in holdings
        if isinstance(holding, dict) and holding.get("ticker")
    ] if isinstance(holdings, list) else []

    lines = [
        "## ETF Portfolio Evaluation (Appendix)",
        (
            f"Evaluated {len(holdings)} ETF rows from the asset sheet. "
            "The sheet does not provide portfolio weights, so aggregate "
            "figures below are unweighted averages, not portfolio-weighted "
            "exposures."
        )
    ]
    if not holdings:
        lines.append("No ETF holdings were available for this evaluation.")
        return "\n".join(lines)

    metrics = (
        ("expense_ratio", "Expense ratio", 100.0),
        ("dividend_yield", "Distribution yield", 100.0),
        ("beta", "Beta", 1.0)
    )
    for key, label, multiplier in metrics:
        available = [
            (holding["ticker"], holding.get(key))
            for holding in holdings
            if _is_finite_number(holding.get(key))
        ]
        if not available:
            lines.append(f"- {label}: no retrieved values.")
            continue

        values = [value for _, value in available]
        average = sum(values) / len(values)
        formatted_average = (
            _format_percent(average, multiplier)
            if multiplier != 1.0
            else _format_number(average)
        )
        lines.append(
            f"- Unweighted average {label.lower()}: {formatted_average} "
            f"({len(available)}/{len(holdings)} holdings)."
        )

        if key == "beta":
            highest_ticker, highest_value = max(available, key=lambda x: x[1])
            lowest_ticker, lowest_value = min(available, key=lambda x: x[1])
            lines.append(
                "- Retrieved beta range: "
                f"{lowest_ticker} {_format_number(lowest_value)} to "
                f"{highest_ticker} {_format_number(highest_value)}; "
                "beta is a historical market-sensitivity measure, not a "
                "standalone risk rating."
            )

    return "\n".join(lines)
