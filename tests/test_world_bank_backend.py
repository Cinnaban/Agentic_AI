import unittest

from data.providers.live.world_bank_backend import WorldBankBackend


class FakeWB:
    def __init__(self):
        self.calls = []

    def countries(self):
        return {"BR": "Brazil", "US": "United States", "JP": "Japan", "GE": "Georgia", "WLD": "World"}

    def indicator(self, iso, code):
        self.calls.append((iso, code))
        return {"name": code, "country": self.countries()[iso],
                "rows": [{"date": "2025", "value": 2.5}, {"date": "2024", "value": 3.0}, {"date": "2020", "value": 1.0}]}


class WorldBankBackendTests(unittest.TestCase):
    def search(self, query):
        fake = FakeWB()
        return WorldBankBackend(fake).search({}, query), fake.calls

    def test_no_country_no_requests(self):
        self.assertEqual(self.search("is inflation cooling?")[1], [])
        self.assertEqual(self.search("who won the world cup in Brazil")[1], [])

    def test_country_economy_defaults_to_broad_set(self):
        results, calls = self.search("How is Brazil's economy doing?")
        self.assertEqual({c[0] for c in calls}, {"BR"})
        self.assertEqual({c[1] for c in calls}, {"NY.GDP.MKTP.KD.ZG", "FP.CPI.TOTL.ZG", "SL.UEM.TOTL.ZS"})
        self.assertIn("Brazil", results[0]["summary"])
        self.assertTrue(results[0]["no_scrape"] and not results[0].get("authoritative"))

    def test_demographics_and_political(self):
        _, calls = self.search("Japan population and political stability")
        codes = {c[1] for c in calls}
        self.assertIn("SP.POP.TOTL", codes)
        self.assertIn("GOV_WGI_PV.EST", codes)

    def test_aliases_and_multiple_countries(self):
        _, calls = self.search("Compare US and Japan GDP")
        self.assertEqual({c[0] for c in calls}, {"US", "JP"})

    def test_global_scope(self):
        _, calls = self.search("global population trends")
        self.assertEqual({c[0] for c in calls}, {"WLD"})

    def test_ambiguous_name_needs_context(self):
        self.assertEqual(self.search("Georgia economy")[1], [])
        self.assertTrue(self.search("economy of Georgia")[1])


if __name__ == "__main__":
    unittest.main()
