import unittest

from data.providers.live.alpha_vantage_backend import AlphaVantageBackend


class FakeAV:
    def __init__(self):
        self.calls = []

    def configured(self):
        return True

    def quote(self, s):
        self.calls.append(("quote", s))
        return {"05. price": "66.06", "10. change percent": "-28.06%", "07. latest trading day": "2026-10-30",
                "08. previous close": "91.8", "06. volume": "1000"}

    def overview(self, s):
        self.calls.append(("overview", s))
        return None

    def etf_profile(self, s):
        self.calls.append(("etf", s))
        return None

    def fx_rate(self, a, b):
        self.calls.append(("fx", a, b))
        return {"5. Exchange Rate": "1.0850", "6. Last Refreshed": "2026-11-02 12:00:00", "8. Bid Price": "1.0849",
                "9. Ask Price": "1.0851"}

    def economic(self, fn, **kw):
        self.calls.append(("econ", fn))
        rows = [{"date": f"2026-{m:02d}-01", "value": str(300 - m)} for m in range(9, 0, -1)] + \
               [{"date": f"2025-{m:02d}-01", "value": str(280 - m)} for m in range(12, 0, -1)]
        return {"name": fn, "unit": "index", "rows": rows}

    def movers(self):
        self.calls.append(("movers",))
        return {"last_updated": "2026-11-02", "top_gainers": [{"ticker": "AAA", "change_percentage": "9%"}],
                "top_losers": [{"ticker": "BBB", "change_percentage": "-8%"}], "most_actively_traded": []}


class AlphaVantageBackendTests(unittest.TestCase):
    def search(self, company, query):
        fake = FakeAV()
        return AlphaVantageBackend(fake).search(company, query), fake.calls

    def test_irrelevant_question_costs_no_requests(self):
        results, calls = self.search({}, "who won the world cup")
        self.assertEqual((results, calls), ([], []))

    def test_dividend_yield_is_not_a_treasury_query(self):
        _, calls = self.search({}, "what is the dividend yield of KO")
        self.assertEqual(calls, [])

    def test_forex_pair_and_names(self):
        self.assertEqual(AlphaVantageBackend.forex_pairs("EUR/USD outlook"), [("EUR", "USD")])
        self.assertEqual(AlphaVantageBackend.forex_pairs("how strong is the yen against the dollar"), [("JPY", "USD")])
        self.assertEqual(AlphaVantageBackend.forex_pairs("who won the game"), [])

    def test_economic_series_and_yoy(self):
        results, calls = self.search({}, "is inflation cooling and will the Fed cut rates?")
        self.assertEqual({c[1] for c in calls}, {"CPI", "FEDERAL_FUNDS_RATE"})
        cpi = next(r for r in results if "CPI" in r["title"])
        self.assertIn("year over year", cpi["summary"])
        self.assertIn("as of 2026-09-01", cpi["summary"])

    def test_stock_gets_quote_and_results_are_marked_api_data(self):
        results, calls = self.search({"ticker": "INTC", "entity_type": "stock"}, "is INTC undervalued")
        self.assertIn(("quote", "INTC"), calls)
        self.assertTrue(all(r["source"] == "Alpha Vantage" and r["no_scrape"] and not r.get("authoritative") for r in results))

    def test_market_movers(self):
        results, _ = self.search({}, "show me the top gainers today")
        self.assertIn("AAA", results[0]["summary"])

    def test_unconfigured_returns_nothing(self):
        class Off(FakeAV):
            def configured(self):
                return False
        self.assertEqual(AlphaVantageBackend(Off()).search({"ticker": "INTC"}, "INTC"), [])


if __name__ == "__main__":
    unittest.main()
