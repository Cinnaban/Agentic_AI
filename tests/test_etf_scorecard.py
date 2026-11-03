import unittest

import pandas as pd

from orchestrator.etf_scorecard import ETFScorecard, _rank_scores


def raw(er, aum, volume, bid=None, ask=None, nav=None, last=None, holdings=(), drift=0.0, category="Industrials"):
    idx = pd.date_range("2025-01-01", periods=250, freq="B")
    closes = pd.Series([100 * (1 + drift) ** i * (1 + 0.01 * ((i % 5) - 2)) for i in range(250)], index=idx)
    return {
        "info": {"netExpenseRatio": er, "totalAssets": aum, "averageVolume": volume, "bid": bid, "ask": ask,
                 "navPrice": nav, "previousClose": last, "category": category, "longName": "Fund"},
        "holdings": list(holdings),
        "closes": closes,
    }


BENCH = pd.Series([100 * 1.0004 ** i for i in range(250)], index=pd.date_range("2025-01-01", periods=250, freq="B"))

FUNDS = {
    "GOOD": raw(0.05, 5e9, 5e6, 100.00, 100.02, 100.0, 100.02, [("A", 0.05), ("B", 0.04)], 0.001, "Large Blend"),
    "BAD": raw(0.9, 20e6, 5e3, 50.0, 51.5, 50.0, 49.0, [("A", 0.3), ("C", 0.3)], -0.001),
    "MID": raw(0.5, 80e6, 5e4, holdings=[("D", 0.1)]),
}


class ETFScorecardTests(unittest.TestCase):
    def card(self, tickers=("GOOD", "BAD")):
        return ETFScorecard(loader=lambda t: FUNDS.get(t), benchmark_loader=lambda: BENCH)

    def test_better_fund_scores_higher_and_cost_is_scored(self):
        profiles = self.card().score(["GOOD", "BAD"])
        self.assertGreater(profiles["GOOD"]["total"], profiles["BAD"]["total"])
        self.assertEqual(profiles["GOOD"]["scores"]["expense"], 1.0)
        self.assertEqual(profiles["BAD"]["scores"]["expense"], 0.0)
        self.assertEqual(profiles["BAD"]["scores"]["aum"], 0.0)

    def test_output_has_tables_and_read_without_null_talk(self):
        text = self.card().build(["GOOD", "BAD", "MID"])
        self.assertIn("**ETF Scorecard**", text)
        self.assertIn("/100", text)
        self.assertIn("Scorecard read:", text)
        for word in ("null", "unavailable", "missing", "None"):
            self.assertNotIn(word, text)

    def test_needs_two_etfs(self):
        self.assertEqual(self.card().build(["GOOD", "AAPL"]), "")
        self.assertEqual(self.card().build(["GOOD"]), "")

    def test_missing_metrics_are_skipped_not_penalised(self):
        profiles = self.card().score(["GOOD", "MID"])
        self.assertNotIn("spread", profiles["MID"]["scores"])
        self.assertIsNotNone(profiles["MID"]["total"])

    def test_overlap_flagged_only_when_heavy(self):
        funds = dict(FUNDS)
        funds["TWIN"] = raw(0.5, 90e6, 5e4, holdings=[("A", 0.3), ("C", 0.3)])
        card = ETFScorecard(loader=lambda t: funds.get(t), benchmark_loader=lambda: BENCH)
        self.assertIn("overlap: BAD/TWIN 60%", card.build(["BAD", "TWIN", "GOOD"]))
        self.assertNotIn("overlap", self.card().build(["GOOD", "MID"]))

    def test_rank_scores(self):
        self.assertEqual(_rank_scores({"a": 1, "b": 3}, lower_better=True), {"a": 1.0, "b": 0.0})
        self.assertEqual(_rank_scores({"a": 2, "b": 2}, lower_better=True), {"a": 0.5, "b": 0.5})
        self.assertEqual(_rank_scores({"a": 2, "b": None}, lower_better=True), {})


if __name__ == "__main__":
    unittest.main()
