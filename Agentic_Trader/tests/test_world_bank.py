import unittest
from unittest import mock

from agentic_trader.market_apis.world_bank import WorldBank


class WorldBankTests(unittest.TestCase):
    def client(self):
        c = WorldBank()
        c._cached = lambda key, ttl, fn: fn()
        return c

    def test_indicator_drops_null_years(self):
        payload = [{}, [{"indicator": {"value": "GDP"}, "country": {"value": "Brazil"}, "date": "2025", "value": 2.2},
                        {"indicator": {"value": "GDP"}, "country": {"value": "Brazil"}, "date": "2024", "value": None}]]
        c = self.client()
        with mock.patch.object(c, "_get", return_value=payload):
            out = c.indicator("BR", "NY.GDP.MKTP.KD.ZG")
        self.assertEqual(out["rows"], [{"date": "2025", "value": 2.2}])

    def test_bad_codes_rejected(self):
        with self.assertRaises(ValueError):
            self.client().indicator("BR/../x", "NY.GDP")


if __name__ == "__main__":
    unittest.main()
