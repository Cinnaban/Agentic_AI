import unittest
from unittest import mock

from agentic_trader.market_apis.kaggle import Kaggle


class KaggleTests(unittest.TestCase):
    def client(self):
        k = Kaggle()
        k._cached = lambda key, ttl, fn: fn()
        return k

    def test_search_maps_results(self):
        k = self.client()
        resp = mock.Mock()
        resp.json.return_value = [{"ref": "a/b", "title": "T", "totalBytes": 10}, {"nope": 1}]
        with mock.patch.object(k, "_get", return_value=resp):
            out = k.search("stock", limit=5)
        self.assertEqual([d["ref"] for d in out], ["a/b"])

    def test_bad_ref_rejected(self):
        with self.assertRaises(ValueError):
            self.client().metadata("../etc/passwd")

    def test_oversize_download_refused(self):
        k = self.client()
        k.max_mb = 1
        with mock.patch.object(k, "metadata", return_value={"bytes": 5_000_000}), \
                mock.patch.object(k, "_get") as get:
            self.assertIsNone(k.download("a/b"))
        get.assert_not_called()
        self.assertIn("cap", k.last_error)


if __name__ == "__main__":
    unittest.main()
