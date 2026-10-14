import unittest
from unittest.mock import Mock, patch

from data.providers.company_ticker_lookup import CompanyTickerLookup


class CompanyTickerLookupTests(unittest.TestCase):

    def test_returns_listing_candidates_with_useful_metadata(self):
        lookup = CompanyTickerLookup.__new__(CompanyTickerLookup)
        lookup.storage = Mock()
        lookup.storage.get_cached_data.return_value = None
        lookup.storage.build_cache_key.side_effect = lambda value: value
        search = Mock(return_value=Mock(quotes=[
            {
                "symbol": "DIS",
                "longname": "The Walt Disney Company",
                "quoteType": "EQUITY",
                "exchDisp": "NYSE",
                "sector": "Communication Services",
                "industry": "Entertainment"
            },
            {
                "symbol": "DIS.TO",
                "longname": "The Walt Disney Company",
                "quoteType": "ETF",
                "exchDisp": "Toronto"
            },
            {
                "symbol": "DIS=F",
                "longname": "Disney Future",
                "quoteType": "FUTURE"
            }
        ]))

        with patch(
            "data.providers.company_ticker_lookup.yf.Search",
            search
        ):
            candidates = lookup.search("Disney")

        self.assertEqual(
            candidates,
            [{
                "symbol": "DIS",
                "name": "The Walt Disney Company",
                "quote_type": "EQUITY",
                "exchange": "NYSE",
                "sector": "Communication Services",
                "industry": "Entertainment"
            }]
        )
        search.assert_called_once_with(
            "Disney",
            max_results=lookup.RESULT_LIMIT,
            news_count=0,
            lists_count=0
        )
        lookup.storage.set_cached_data.assert_called_once()

    def test_prefers_cached_primary_exchange_candidates(self):
        lookup = CompanyTickerLookup.__new__(CompanyTickerLookup)
        lookup.storage = Mock()
        cached = [
            {
                "symbol": "DELL",
                "name": "Dell Technologies Inc.",
                "exchange": "NYSE"
            },
            {
                "symbol": "DELL.MX",
                "name": "Dell Technologies Inc.",
                "exchange": "Mexico"
            }
        ]
        lookup.storage.get_cached_data.return_value = cached

        with patch(
            "data.providers.company_ticker_lookup.yf.Search"
        ) as search:
            result = lookup.search("Dell")

        self.assertEqual(result, [cached[0]])
        search.assert_not_called()

    def test_lookup_failure_is_logged_and_returns_no_candidates(self):
        lookup = CompanyTickerLookup.__new__(CompanyTickerLookup)
        lookup.storage = Mock()
        lookup.storage.get_cached_data.return_value = None

        with patch(
            "data.providers.company_ticker_lookup.yf.Search",
            side_effect=RuntimeError("network unavailable")
        ):
            with self.assertLogs(level="WARNING"):
                result = lookup.search("Disney")

        self.assertEqual(result, [])
        lookup.storage.set_cached_data.assert_not_called()


if __name__ == "__main__":
    unittest.main()
