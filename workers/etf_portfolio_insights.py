import math
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime


STOCK_METRIC_LABELS = (
    ("cash_flow", "Operating cash flow (TTM)"),
    ("free_cash_flow", "Free cash flow (TTM)"),
    ("market_cap", "Market capitalization"),
    ("eps", "Trailing EPS"),
    ("ebitda", "EBITDA"),
    ("current_ratio", "Current ratio"),
    ("quick_ratio", "Quick ratio"),
    ("operating_margin", "Operating margin"),
    ("profit_margin", "Profit margin"),
    ("return_on_equity", "Return on equity"),
    ("debt_to_equity", "Debt to equity"),
    ("revenue_growth", "Revenue growth"),
    ("earnings_growth", "Earnings growth"),
    ("trailing_pe", "Trailing P/E"),
    ("beta", "Beta"),
    ("dividend_yield", "Dividend yield")
)

ETF_METRIC_LABELS = (
    ("total_assets", "Fund assets"),
    ("expense_ratio", "Expense ratio"),
    ("dividend_yield", "Distribution yield"),
    ("beta", "Beta")
)

TICKER_SYMBOL_PATTERN = re.compile(
    r"^[A-Za-z][A-Za-z0-9.-]{0,9}$"
)


def parse_asset_rows(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError("Asset worksheet is empty or unavailable")

    header = rows[0]
    first_header_cell = (
        str(header[0]).strip().casefold()
        if isinstance(header, (list, tuple)) and header
        else ""
    )
    if first_header_cell not in {"ticker", "symbol"}:
        raise ValueError(
            "Configured asset worksheet must have Ticker or Symbol in cell A1"
        )

    holdings = []
    skipped = []
    for row_number, row in enumerate(rows[1:], start=2):
        if not isinstance(row, (list, tuple)) or not row:
            continue
        raw_ticker = str(row[0] or "").strip()
        if not raw_ticker:
            continue
        if raw_ticker.casefold() in {"ticker", "symbol"}:
            continue
        if not TICKER_SYMBOL_PATTERN.fullmatch(raw_ticker):
            skipped.append({
                "row": row_number,
                "reason": "invalid ticker symbol"
            })
            continue
        holdings.append({
            "row": row_number,
            "ticker": raw_ticker.upper(),
            "values": row
        })
    return holdings, skipped


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _statement_columns(statement):
    if statement is None:
        return []
    columns = getattr(statement, "columns", None)
    if columns is not None:
        return list(columns)
    if isinstance(statement, dict):
        return list(statement.keys())
    return []


def _statement_rows(statement):
    if statement is None:
        return []
    if hasattr(statement, "iterrows"):
        return list(statement.iterrows())
    if isinstance(statement, dict):
        return list(statement.items())
    return []


def _column_value(row, column):
    if hasattr(row, "get"):
        return row.get(column)
    if isinstance(row, (list, tuple)):
        try:
            return row[column]
        except (IndexError, TypeError):
            return None
    return None


def _find_statement_metric(statement, aliases):
    aliases = {alias.casefold() for alias in aliases}
    for label, row in _statement_rows(statement):
        normalized = str(label).strip().casefold()
        if normalized in aliases:
            values = [
                (column, _number(_column_value(row, column)))
                for column in _statement_columns(statement)
            ]
            values = [
                (column, value)
                for column, value in values
                if value is not None
            ]
            values.sort(
                key=lambda item: parse_publication_time(
                    _period_label(item[0])
                ) or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True
            )
            if values:
                return values
    return []


def _period_label(column):
    if isinstance(column, datetime):
        return column.date().isoformat()
    if hasattr(column, "date"):
        try:
            return column.date().isoformat()
        except (AttributeError, ValueError):
            pass
    return str(column)


def collect_holding_insights(
    ticker,
    entity_type,
    info,
    income_statement=None,
    cash_flow_statement=None,
    balance_sheet=None,
    price_history=None,
    fund_context=None
):
    info = info if isinstance(info, dict) else {}
    entity_type = entity_type if entity_type in {"stock", "etf"} else "unresolved"
    record = {
        "ticker": str(ticker or "").strip().upper(),
        "entity_type": entity_type,
        "data_source": "Yahoo Finance",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "name": info.get("shortName") or info.get("longName") or ticker,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "market_performance_3m_pct": None,
        "metrics": {},
        "quarterly": {},
        "not_applicable": []
    }

    if price_history is not None and hasattr(price_history, "empty"):
        if not price_history.empty and "Close" in price_history:
            closes = [
                _number(value)
                for value in price_history["Close"].tolist()
            ]
            closes = [value for value in closes if value and value > 0]
            if len(closes) > 1:
                record["market_performance_3m_pct"] = (
                    (closes[-1] / closes[0]) - 1
                ) * 100

    if entity_type == "stock":
        record["metrics"] = {
            "cash_flow": info.get("operatingCashflow"),
            "free_cash_flow": info.get("freeCashflow"),
            "market_cap": info.get("marketCap"),
            "eps": info.get("trailingEps")
            if info.get("trailingEps") is not None
            else info.get("epsTrailingTwelveMonths"),
            "ebitda": info.get("ebitda"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            "operating_margin": info.get("operatingMargins"),
            "profit_margin": info.get("profitMargins"),
            "return_on_equity": info.get("returnOnEquity"),
            "debt_to_equity": info.get("debtToEquity"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "trailing_pe": info.get("trailingPE"),
            "beta": info.get("beta"),
            "dividend_yield": info.get("dividendYield")
            if info.get("dividendYield") is not None
            else info.get("yield")
        }

        quarterly_aliases = {
            "revenue": ("total revenue", "revenue"),
            "net_income": ("net income", "net income common stockholders"),
            "eps": ("diluted eps", "basic eps", "eps")
        }
        for key, aliases in quarterly_aliases.items():
            values = _find_statement_metric(income_statement, aliases)
            if values:
                current_period, current_value = values[0]
                metric = {
                    "latest": current_value,
                    "period_ended": _period_label(current_period)
                }
                if len(values) > 1:
                    previous_period, previous_value = values[1]
                    metric["previous_quarter"] = previous_value
                    metric["previous_period_ended"] = _period_label(
                        previous_period
                    )
                    metric["quarter_over_quarter_change"] = (
                        current_value - previous_value
                    )
                    if previous_value > 0:
                        metric["quarter_over_quarter_change_pct"] = (
                            (current_value / previous_value) - 1
                        ) * 100
                record["quarterly"][key] = metric

        for key, statement, aliases in (
            (
                "operating_cash_flow",
                cash_flow_statement,
                ("operating cash flow", "cash flow from continuing operating activities")
            ),
            ("free_cash_flow", cash_flow_statement, ("free cash flow",)),
            ("current_assets", balance_sheet, ("current assets", "total current assets")),
            ("current_liabilities", balance_sheet, ("current liabilities", "total current liabilities"))
        ):
            values = _find_statement_metric(statement, aliases)
            if values:
                record["quarterly"][key] = {
                    "latest": values[0][1],
                    "period_ended": _period_label(values[0][0])
                }
        current_assets = record["quarterly"].get("current_assets", {}).get("latest")
        current_liabilities = record["quarterly"].get(
            "current_liabilities", {}
        ).get("latest")
        if (
            _number(current_assets) is not None
            and _number(current_liabilities) not in (None, 0)
        ):
            record["quarterly"]["current_ratio"] = {
                "latest": current_assets / current_liabilities
            }
    elif entity_type == "etf":
        fund_context = fund_context if isinstance(fund_context, dict) else {}
        record["metrics"] = {
            "total_assets": info.get("totalAssets"),
            "expense_ratio": info.get("annualReportExpenseRatio")
            if info.get("annualReportExpenseRatio") is not None
            else info.get("netExpenseRatio"),
            "dividend_yield": info.get("yield")
            if info.get("yield") is not None
            else info.get("dividendYield"),
            "beta": info.get("beta")
        }
        record["fund_profile"] = {
            "overview": fund_context.get("fund_overview"),
            "asset_classes": fund_context.get("asset_classes"),
            "sector_weightings": fund_context.get("sector_weightings"),
            "top_holdings": fund_context.get("top_holdings")
        }
        record["not_applicable"] = [
            "issuer-style EPS",
            "EBITDA",
            "operating/free cash flow",
            "current ratio"
        ]
        record["quarterly"]["note"] = (
            "An ETF is a pooled investment vehicle, not an operating "
            "company. Its own EPS, EBITDA, operating cash flow, and current "
            "ratio are not comparable operating-company measures. Use "
            "fund performance, assets, costs, distributions, holdings, and "
            "sector exposures instead."
        )
    else:
        record["classification_status"] = "unresolved"
    return record


def retrieve_holding_insights(
    yf_ticker,
    ticker,
    entity_type,
    info,
    fund_context=None
):
    def optional_attribute(name):
        try:
            return getattr(yf_ticker, name)
        except Exception as error:
            logging.warning(
                "ETF update could not retrieve %s for %s: %s",
                name,
                ticker,
                error
            )
            return None

    if entity_type == "stock":
        income_statement = optional_attribute("quarterly_income_stmt")
        cash_flow_statement = optional_attribute("quarterly_cashflow")
        balance_sheet = optional_attribute("quarterly_balance_sheet")
    else:
        income_statement = None
        cash_flow_statement = None
        balance_sheet = None

    try:
        price_history = yf_ticker.history(
            period="3mo",
            auto_adjust=False
        )
    except Exception as error:
        logging.warning(
            "ETF update could not retrieve 3-month price history for %s: %s",
            ticker,
            error
        )
        price_history = None

    return collect_holding_insights(
        ticker=ticker,
        entity_type=entity_type,
        info=info,
        income_statement=income_statement,
        cash_flow_statement=cash_flow_statement,
        balance_sheet=balance_sheet,
        price_history=price_history,
        fund_context=fund_context
    )


def parse_publication_time(value):
    if isinstance(value, datetime):
        published_at = value
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        try:
            published_at = datetime.fromisoformat(
                text.replace("Z", "+00:00")
            )
        except ValueError:
            try:
                published_at = parsedate_to_datetime(text)
            except (TypeError, ValueError, OverflowError):
                return None
    else:
        return None
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    return published_at.astimezone(timezone.utc)


def filter_recent_news(items, now=None, window_hours=48):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now.astimezone(timezone.utc) - timedelta(hours=window_hours)
    selected = []
    seen_urls = set()
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        published_at = parse_publication_time(item.get("published_at"))
        url = item.get("url")
        if (
            published_at is None
            or published_at < cutoff
            or published_at > now.astimezone(timezone.utc)
            or not isinstance(url, str)
            or not url.strip()
            or url in seen_urls
        ):
            continue
        selected.append({
            **item,
            "published_at": published_at.isoformat()
        })
        seen_urls.add(url)
    return sorted(
        selected,
        key=lambda item: item["published_at"],
        reverse=True
    )


def _format_metric(key, value):
    value = _number(value)
    if value is None:
        return "Unavailable"
    if key in {
        "cash_flow",
        "free_cash_flow",
        "market_cap",
        "ebitda",
        "total_assets"
    }:
        return f"${value:,.0f}"
    if key in {
        "expense_ratio",
        "dividend_yield",
        "operating_margin",
        "profit_margin",
        "return_on_equity",
        "revenue_growth",
        "earnings_growth"
    }:
        return f"{value * 100:.2f}%"
    return f"{value:,.4g}"


def format_holding_insights(holdings, news_by_ticker, now=None):
    now = now or datetime.now(timezone.utc)
    generated_at = now.astimezone(timezone.utc).isoformat()
    symbols = [
        holding.get("ticker")
        for holding in holdings
        if holding.get("ticker")
    ]
    lines = [
        f"Portfolio insights retrieved at {generated_at}.",
        f"Included worksheet tickers ({len(symbols)}): "
        + (", ".join(symbols) if symbols else "none"),
        "News below is limited to stories with a parseable publication "
        "timestamp within the preceding 48 hours."
    ]
    for holding in holdings:
        ticker = holding.get("ticker", "Unknown")
        kind = holding.get("entity_type", "unresolved").upper()
        lines.extend([
            "",
            f"### {ticker} — {kind}",
            "Classification: "
            + str(holding.get("classification_status") or "unavailable")
            + " via "
            + str(holding.get("classification_source") or "unknown source"),
            "Market-data source: "
            + str(holding.get("data_source") or "unavailable")
            + " (retrieved "
            + str(holding.get("retrieved_at") or "time unavailable")
            + ")",
            f"Name: {holding.get('name') or 'Unavailable'}",
            f"Sector: {holding.get('sector') or 'Unavailable'}",
            f"Industry: {holding.get('industry') or 'Unavailable'}"
        ])
        performance = _number(holding.get("market_performance_3m_pct"))
        lines.append(
            "Trailing 3-month price performance: "
            + (
                f"{performance:+.2f}% (price return; excludes distributions)."
                if performance is not None
                else "Unavailable."
            )
        )
        metric_labels = (
            ETF_METRIC_LABELS
            if kind == "ETF"
            else STOCK_METRIC_LABELS
            if kind == "STOCK"
            else ()
        )
        metrics = holding.get("metrics", {})
        if kind == "UNRESOLVED":
            lines.append(
                "Financial assessment withheld because ticker classification "
                "could not be verified."
            )
        for key, label in metric_labels:
            value = metrics.get(key) if isinstance(metrics, dict) else None
            lines.append(
                f"{label}: "
                + _format_metric(key, value)
                + "."
            )
        if kind == "STOCK" and holding.get("industry"):
            peers = [
                peer for peer in holdings
                if (
                    peer is not holding
                    and peer.get("entity_type") == "stock"
                    and str(peer.get("industry") or "").casefold()
                    == str(holding.get("industry")).casefold()
                )
            ]
            lines.append(
                "Same-industry holdings in this portfolio "
                "(partial cohort, not an industry-wide benchmark):"
            )
            if peers:
                for peer in peers:
                    peer_metrics = peer.get("metrics", {})
                    available_peer_metrics = [
                        (key, label)
                        for key, label in (
                            ("revenue_growth", "revenue growth"),
                            ("earnings_growth", "earnings growth"),
                            ("operating_margin", "operating margin"),
                            ("profit_margin", "profit margin"),
                            ("current_ratio", "current ratio"),
                            ("debt_to_equity", "debt to equity"),
                            ("return_on_equity", "return on equity")
                        )
                        if isinstance(peer_metrics, dict)
                        and _number(peer_metrics.get(key)) is not None
                    ]
                    peer_summary = ", ".join(
                        f"{label}: {_format_metric(key, peer_metrics[key])}"
                        for key, label in available_peer_metrics
                    ) or "no comparable metrics retrieved"
                    lines.append(
                        f"- {peer.get('ticker')}: {peer_summary}"
                    )
            else:
                lines.append(
                    "- No other same-industry stock holding was present; "
                    "no industry-wide benchmark was retrieved."
                )
        quarterly = holding.get("quarterly", {})
        if kind == "ETF":
            lines.append(quarterly.get("note", "Quarterly operating metrics not applicable."))
            profile = holding.get("fund_profile", {})
            if isinstance(profile, dict):
                lines.append(
                    "Fund sector exposures: "
                    + str(profile.get("sector_weightings") or "Unavailable.")
                )
                lines.append(
                    "Top holdings: "
                    + str(profile.get("top_holdings") or "Unavailable.")
                )
        else:
            if quarterly:
                lines.append("Latest available quarterly financial-statement values:")
                for key, value in quarterly.items():
                    if isinstance(value, dict):
                        label = key.replace("_", " ").title()
                        lines.append(f"- {label}: {value}")
            else:
                lines.append("Quarterly financial-statement data: unavailable.")
        recent_news = filter_recent_news(
            (news_by_ticker or {}).get(ticker, []),
            now=now
        )
        lines.append("News published in the last 48 hours:")
        if not recent_news:
            lines.append("- No timestamp-verified relevant headlines retrieved.")
        for item in recent_news[:3]:
            lines.append(
                f"- {item.get('title')} | {item.get('source') or 'Source unavailable'}"
                f" | {item.get('published_at')} | {item.get('url')}"
            )
    return "\n".join(lines)
