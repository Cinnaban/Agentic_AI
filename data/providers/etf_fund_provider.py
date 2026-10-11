import math
import re
from datetime import datetime, timezone

import yfinance as yf


class ETFFundProvider:

    ETF_REQUEST_PATTERN = re.compile(
        r"\b(?:ETF|exchange[- ]traded fund)\b",
        re.IGNORECASE
    )
    STOCK_REQUEST_PATTERN = re.compile(
        r"\b(?:stock|equity|shares?)\b",
        re.IGNORECASE
    )

    def resolve(self, ticker, message=""):
        ticker = str(ticker or "").strip().upper()
        if not ticker:
            return {
                "entity_type": "security",
                "classification_status": "unavailable",
                "classification_error": "Ticker is required"
            }

        yf_ticker = yf.Ticker(ticker)
        has_etf_cue = bool(
            self.ETF_REQUEST_PATTERN.search(
                str(message or "")
            )
        )
        has_stock_cue = bool(
            self.STOCK_REQUEST_PATTERN.search(
                str(message or "")
            )
        )

        classification_error = None
        quote_info = {}
        try:
            quote_info = yf_ticker.info or {}
            quote_type = str(
                quote_info.get("quoteType", "")
            ).upper()
        except Exception as exc:
            quote_type = ""
            classification_error = str(exc)

        if quote_type == "ETF":
            entity_type = "etf"
            classification_status = "resolved"
            classification_source = "Yahoo Finance quote type"
        elif quote_type == "EQUITY":
            entity_type = "stock"
            classification_status = "resolved"
            classification_source = "Yahoo Finance quote type"
        elif quote_type:
            return {
                "entity_type": "security",
                "classification_status": "unsupported",
                "classification_source": "Yahoo Finance quote type",
                "quote_type": quote_type
            }
        elif has_etf_cue and not has_stock_cue:
            entity_type = "etf"
            classification_status = "unverified"
            classification_source = "user_request"
        elif has_stock_cue and not has_etf_cue:
            entity_type = "stock"
            classification_status = "unverified"
            classification_source = "user_request"
        else:
            return {
                "entity_type": "security",
                "classification_status": (
                    "unavailable"
                    if classification_error
                    else "unresolved"
                ),
                "classification_error": classification_error,
                "quote_type": None
            }

        result = {
            "entity_type": entity_type,
            "classification_status": classification_status,
            "classification_source": classification_source
        }
        for field in ("industry", "sector"):
            value = quote_info.get(field)
            if isinstance(value, str) and value.strip():
                result[field] = value.strip()
        if classification_error:
            result["classification_error"] = classification_error
        if entity_type == "etf":
            etf_context = self.get_fund_context(
                ticker,
                yf_ticker=yf_ticker
            )
            fund_quote_type = str(
                etf_context.get("quote_type", "")
            ).upper()
            if fund_quote_type and fund_quote_type != "ETF":
                return {
                    "entity_type": "security",
                    "classification_status": "unsupported",
                    "classification_source": (
                        "Yahoo Finance fund quote type"
                    ),
                    "quote_type": fund_quote_type
                }
            if fund_quote_type == "ETF":
                result["classification_status"] = "resolved"
                result["classification_source"] = (
                    "Yahoo Finance fund quote type"
                )
                result.pop("classification_error", None)
            result["etf_context"] = etf_context
        return result

    def get_fund_context(self, ticker, yf_ticker=None):
        if yf_ticker is None:
            yf_ticker = yf.Ticker(ticker)

        try:
            funds = yf_ticker.funds_data
            operations = self._dataframe_rows(
                funds.fund_operations
            )
            top_holdings = self._dataframe_rows(
                funds.top_holdings
            )
            context = {
                "source": "Yahoo Finance",
                "retrieved_at": datetime.now(
                    timezone.utc
                ).isoformat(),
                "quote_type": self._normalize(
                    funds.quote_type
                ),
                "fund_overview": self._normalize(
                    funds.fund_overview
                ),
                "fund_operations": operations,
                "asset_classes": self._normalize(
                    funds.asset_classes
                ),
                "top_holdings": top_holdings[:10],
                "sector_weightings": self._normalize(
                    funds.sector_weightings
                ),
                "equity_holdings": self._dataframe_rows(
                    funds.equity_holdings
                ),
                "bond_holdings": self._dataframe_rows(
                    funds.bond_holdings
                ),
                "bond_ratings": self._normalize(
                    funds.bond_ratings
                )
            }
            context["status"] = (
                "available"
                if any(
                    context[key]
                    for key in (
                        "fund_overview",
                        "fund_operations",
                        "asset_classes",
                        "top_holdings",
                        "sector_weightings",
                        "equity_holdings",
                        "bond_holdings",
                        "bond_ratings"
                    )
                )
                else "unavailable"
            )
            if context["status"] == "unavailable":
                context["error"] = (
                    "Yahoo Finance returned no ETF profile data."
                )
            return context
        except Exception as exc:
            return {
                "status": "unavailable",
                "source": "Yahoo Finance",
                "retrieved_at": datetime.now(
                    timezone.utc
                ).isoformat(),
                "error": str(exc)
            }

    @classmethod
    def _dataframe_rows(cls, value):
        if value is None or not hasattr(value, "to_dict"):
            return []

        rows = value.to_dict(orient="index")
        if not isinstance(rows, dict):
            return []

        return [
            {
                "key": str(key),
                **(
                    cls._normalize(row)
                    if isinstance(row, dict)
                    else {"value": cls._normalize(row)}
                )
            }
            for key, row in rows.items()
        ]

    @classmethod
    def _normalize(cls, value):
        if value is None or isinstance(value, (str, bool, int)):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        if isinstance(value, dict):
            return {
                str(key): cls._normalize(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [
                cls._normalize(item)
                for item in value
            ]
        if hasattr(value, "item"):
            try:
                return cls._normalize(value.item())
            except (TypeError, ValueError):
                return None
        return None
