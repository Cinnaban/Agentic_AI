import math
import re


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


def format_change_direction(field, old_value, new_value):
    normalized_field = str(field or "").strip().lower()
    if normalized_field not in {"eps", "dividend yield"}:
        return ""

    def numeric_value(value):
        if _is_finite_number(value):
            return float(value)
        if not isinstance(value, str):
            return None
        cleaned = value.strip().replace(",", "")
        match = re.fullmatch(r"[-+]?\$?(\d+(?:\.\d+)?)%?", cleaned)
        if not match:
            return None
        number = float(match.group(1))
        if cleaned.startswith("-"):
            number = -number
        if normalized_field == "dividend yield" and cleaned.endswith("%"):
            number /= 100
        return number

    old_number = numeric_value(old_value)
    new_number = numeric_value(new_value)
    if old_number is None or new_number is None:
        return "⚪ direction unavailable"
    if math.isclose(old_number, new_number, rel_tol=1e-9, abs_tol=1e-9):
        return "⚪ unchanged"
    if new_number > old_number:
        return "🟢 increase"
    return "🔴 decrease"


def generate_etf_portfolio_appendix(holdings):
    holdings = [
        holding
        for holding in holdings
        if isinstance(holding, dict) and holding.get("ticker")
    ] if isinstance(holdings, list) else []
    has_classifications = any(
        holding.get("entity_type") in {"stock", "etf"}
        for holding in holdings
    )
    if has_classifications:
        stocks = [
            holding for holding in holdings
            if holding.get("entity_type") == "stock"
        ]
        holdings = [
            holding for holding in holdings
            if holding.get("entity_type") == "etf"
        ]
    else:
        stocks = []

    lines = [
        "## ETF Fund Metrics (Appendix)",
        (
            f"Evaluated {len(holdings)} ETF holdings from the asset sheet. "
            "The sheet does not provide portfolio weights, so aggregate "
            "figures below are unweighted averages, not portfolio-weighted "
            "exposures."
        )
    ]
    if stocks:
        lines.append(
            f"Stock operating metrics are evaluated separately for "
            f"{len(stocks)} classified stock holdings."
        )
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
