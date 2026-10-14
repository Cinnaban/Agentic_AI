import logging

import yfinance as yf

from shared_storage.storage_manager import StorageManager


class CompanyTickerLookup:

    CACHE_TTL_SECONDS = 24 * 60 * 60
    RESULT_LIMIT = 8
    SUPPORTED_QUOTE_TYPES = {
        "EQUITY",
        "ETF"
    }
    PREFERRED_EXCHANGES = {
        "NYSE",
        "NASDAQ",
        "NASDAQGS",
        "NASDAQGM",
        "NASDAQCM",
        "NYSE AMERICAN",
        "NYSE ARCA"
    }

    def __init__(self):
        self.storage = StorageManager()

    @classmethod
    def _prefer_primary_exchanges(cls, candidates):
        preferred = [
            candidate
            for candidate in candidates
            if str(candidate.get("exchange") or "").upper()
            in cls.PREFERRED_EXCHANGES
        ]
        return preferred or candidates

    def search(self, company_name):
        query = str(company_name or "").strip()
        if not query:
            return []

        cache_key = self.storage.build_cache_key(
            query.casefold()
        )
        try:
            cached = self.storage.get_cached_data(
                "company_ticker_search",
                cache_key
            )
        except (OSError, ValueError, TypeError) as error:
            logging.warning("Company ticker cache read failed: %s", error)
            cached = None
        if isinstance(cached, list):
            return self._prefer_primary_exchanges(cached)

        try:
            search_result = yf.Search(
                query,
                max_results=self.RESULT_LIMIT,
                news_count=0,
                lists_count=0
            )
            quotes = getattr(search_result, "quotes", [])
        except Exception as error:
            logging.warning(
                "Company ticker lookup failed for %r: %s",
                query,
                error
            )
            return []

        candidates = []
        seen_symbols = set()
        for quote in quotes:
            if not isinstance(quote, dict):
                continue
            quote_type = str(quote.get("quoteType") or "").upper()
            symbol = str(quote.get("symbol") or "").strip().upper()
            if (
                quote_type not in self.SUPPORTED_QUOTE_TYPES
                or not symbol
                or symbol in seen_symbols
            ):
                continue

            seen_symbols.add(symbol)
            candidate = {
                "symbol": symbol,
                "name": (
                    quote.get("longname")
                    or quote.get("shortname")
                    or symbol
                ),
                "quote_type": quote_type,
                "exchange": quote.get("exchDisp") or quote.get("exchange")
            }
            for field in ("sector", "industry"):
                value = quote.get(field)
                if isinstance(value, str) and value.strip():
                    candidate[field] = value.strip()
            candidates.append(candidate)

        candidates = self._prefer_primary_exchanges(candidates)

        if candidates:
            try:
                self.storage.set_cached_data(
                    "company_ticker_search",
                    cache_key,
                    candidates,
                    self.CACHE_TTL_SECONDS
                )
            except (OSError, ValueError, TypeError) as error:
                logging.warning("Company ticker cache write failed: %s", error)
        return candidates
