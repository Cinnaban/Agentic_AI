import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock

import numpy as np

from agentic_trader import quant_suite as q
from agentic_trader.quant_gate import QuantGate


def bars(n=700, ar=0.0, seed=3, vol=0.002):
    rng = np.random.default_rng(seed)
    r = np.zeros(n)
    for i in range(1, n):
        r[i] = ar * r[i - 1] + vol * rng.normal()
    c = 100 * np.exp(np.cumsum(r))
    return [{"close": float(x), "volume": float(1000 + rng.integers(0, 500))} for x in c]


class Indicators(unittest.TestCase):
    def test_rsi_bounds_and_direction(self):
        up = np.linspace(100, 120, 60)
        self.assertEqual(q.rsi_series(up)[-1], 100.0)
        self.assertLess(q.rsi_series(up[::-1])[-1], 1.0)

    def test_macd_hist_positive_in_uptrend(self):
        self.assertGreater(q.macd_series(np.linspace(100, 130, 80))[2][-1], 0)

    def test_zscore_and_rvol(self):
        c = np.r_[np.full(19, 100.0), 110.0]
        self.assertGreater(q.zscore_series(c)[-1], 3)
        v = np.r_[np.full(30, 100.0), 300.0]
        self.assertAlmostEqual(q.rvol_series(v)[-1], 3.0)

    def test_garch_recovers_persistence(self):
        rng = np.random.default_rng(5)
        n, r, s2 = 3000, [], 4e-6
        for _ in range(n):
            x = np.sqrt(s2) * rng.normal()
            r.append(x)
            s2 = 4e-7 + 0.1 * x * x + 0.85 * s2
        g = q.garch11(np.array(r), 252)
        self.assertAlmostEqual(g["persistence"], 0.95, delta=0.06)


class Splits(unittest.TestCase):
    def test_purged_walk_forward_never_leaks(self):
        folds = list(q.purged_walk_forward(600, folds=5, horizon=3, embargo=2))
        self.assertEqual(len(folds), 5)
        for tr, te in folds:
            self.assertLessEqual(tr.max() + 3 + 2, te.min())  # purge gap between train labels and test
            self.assertTrue(set(tr).isdisjoint(te))
        self.assertTrue(all(a[1].min() > b[1].min() for a, b in zip(folds[1:], folds[:-1])))  # time moves forward


class Metrics(unittest.TestCase):
    def test_auc_and_log_loss(self):
        up = np.array([0, 0, 1, 1.0])
        self.assertEqual(q.auc_roc(np.array([0.1, 0.2, 0.8, 0.9]), up), 1.0)
        self.assertEqual(q.auc_roc(np.array([0.5, 0.5, 0.5, 0.5]), up), 0.5)
        self.assertLess(q.log_loss(np.array([0.1, 0.1, 0.9, 0.9]), up), q.log_loss(np.full(4, 0.5), up))

    def test_perf_stats(self):
        p = q.perf([0.01, -0.02, 0.03, 0.01, -0.01, 0.02], 252)
        self.assertAlmostEqual(p["profit_factor"], 0.07 / 0.03, places=6)
        self.assertAlmostEqual(p["max_dd"], -0.02, places=6)
        self.assertGreater(p["sharpe"], 0)
        self.assertGreater(p["sortino"], p["sharpe"])

    def test_noise_has_no_edge_and_signal_does(self):
        noise = q.analyze(bars(ar=0.0), "5minute")["wf"]
        self.assertLess(abs(noise["ic"]), 0.15)
        self.assertAlmostEqual(noise["auc"], 0.5, delta=0.08)
        signal = q.analyze(bars(ar=0.35, seed=9), "5minute")["wf"]
        self.assertGreater(signal["ic"], 0.15)
        self.assertGreater(signal["auc"], 0.58)
        self.assertGreater(signal["hit_rate"], 0.55)

    def test_full_suite_shape(self):
        out = q.analyze(bars(), "5minute", mode="options")
        for k in ("rsi", "macd_hist", "zscore", "rvol", "rv_ann", "garch", "score", "size_mult", "veto"):
            self.assertIn(k, out)
        for k in ("rmse", "hit_rate", "ic", "auc", "log_loss", "perf"):
            self.assertIn(k, out["wf"])
        for k in ("sharpe", "sortino", "max_dd", "profit_factor"):
            self.assertIn(k, out["wf"]["perf"])
        self.assertTrue(-1 <= out["score"] <= 1 and 0.5 <= out["size_mult"] <= 1.3)

    def test_too_few_bars_is_an_error_not_a_crash(self):
        self.assertIn("error", q.analyze(bars(40), "5minute"))

    def test_account_performance(self):
        log = [[f"2026-11-0{d}T16:00:00", 5000 + 50 * d] for d in range(1, 6)]
        trades = [{"side": "sell", "realized": 10.0}, {"side": "sell", "realized": -5.0}]
        a = q.account_performance(log, trades)
        self.assertAlmostEqual(a["trade_profit_factor"], 2.0)
        self.assertEqual(a["closed_trades"], 2)


class FakeData:
    def __init__(self, series):
        self.series, self.calls = series, 0

    def bars(self, syms, interval, days, ttl=0):
        self.calls += 1
        return {s: self.series[s] for s in syms if s in self.series}


class Gate(unittest.TestCase):
    def gate(self, series, tmp="/tmp/quant_gate_test.json", **kw):
        from pathlib import Path
        return QuantGate(FakeData(series), remote=False, path=Path(tmp), **kw)

    def test_caches_and_reports(self):
        g = self.gate({"AAA": bars()})
        g.ensure(["AAA", "MISSING"], "day")
        g.ensure(["AAA"], "day")
        self.assertEqual(g.data.calls, 1)
        veto, score, size, note = g.verdict("AAA", "day")
        self.assertIn("quant", note)
        self.assertEqual(g.verdict("MISSING", "day"), (False, 0.0, 1.0, ""))  # fail open

    def test_disabled_gate_does_nothing(self):
        g = self.gate({"AAA": bars()}, enabled=False)
        g.ensure(["AAA"], "day")
        self.assertEqual(g.data.calls, 0)

    def test_data_failure_fails_open(self):
        g = self.gate({})
        g.data.bars = mock.Mock(side_effect=RuntimeError("down"))
        g.ensure(["AAA"], "long")
        self.assertEqual(g.verdict("AAA", "long")[0], False)

    def test_gaming_pc_worker_round_trip(self):
        from agentic_trader import quant_worker
        srv = ThreadingHTTPServer(("127.0.0.1", 0), quant_worker.Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with mock.patch.dict("os.environ", {"TRADER_QUANT_URL": f"http://127.0.0.1:{srv.server_port}"}):
                g = QuantGate(FakeData({"AAA": bars()}), remote=True, path=__import__("pathlib").Path("/tmp/quant_gate_test.json"))
                g.ensure(["AAA"], "day")
            self.assertEqual(g.get("AAA", "day")["where"], "gaming_pc")
            self.assertIn("wf", g.get("AAA", "day"))
        finally:
            srv.shutdown()

    def test_worker_rejects_bad_token(self):
        from agentic_trader import quant_worker
        import requests
        srv = ThreadingHTTPServer(("127.0.0.1", 0), quant_worker.Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with mock.patch.dict("os.environ", {"TRADER_QUANT_TOKEN": "secret"}):
                r = requests.post(f"http://127.0.0.1:{srv.server_port}/suite", json={"bars": {}},
                                  headers={"X-Quant-Token": "nope"}, timeout=5)
            self.assertEqual(r.status_code, 401)
        finally:
            srv.shutdown()


if __name__ == "__main__":
    unittest.main()
