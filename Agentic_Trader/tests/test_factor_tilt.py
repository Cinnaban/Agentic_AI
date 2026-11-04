import numpy as np

from agentic_trader.factor_tilt import rank01, raw_signals, tilt


def bars(drift, vol, n=130, seed=0, volume=5e6):
    rng = np.random.default_rng(seed)
    c = 100 * np.cumprod(1 + drift + vol * rng.standard_normal(n))
    return [{"close": float(x), "high": float(x * 1.01), "volume": volume} for x in c]


def test_rank01_ties_and_single():
    assert list(rank01([1.0])) == [0.5]
    assert list(rank01([3, 1, 2])) == [1.0, 0.0, 0.5]
    assert list(rank01([1, 1, 2])) == [0.25, 0.25, 1.0]


def test_too_little_history_is_ignored():
    assert raw_signals(bars(0, 0.01, n=30)) is None
    assert tilt({"A": bars(0, 0.01, n=30), "B": bars(0, 0.01), "C": bars(0, 0.01, seed=2)}) == {}


def test_calm_uptrend_outranks_choppy_downtrend():
    out = tilt({"UP": bars(0.003, 0.004, seed=1), "MID": bars(0.0, 0.015, seed=2), "DOWN": bars(-0.003, 0.03, seed=3)})
    assert out["UP"]["tilt"] > out["MID"]["tilt"] > out["DOWN"]["tilt"]
    assert all(-1 <= v["tilt"] <= 1 for v in out.values())


def test_liquidity_floor_flag():
    out = tilt({"BIG": bars(0, 0.01, seed=1), "MID": bars(0, 0.01, seed=2), "THIN": bars(0, 0.01, seed=3, volume=100)})
    assert out["BIG"]["liquid"] and not out["THIN"]["liquid"]


def test_signals_are_causal():
    b = bars(0.001, 0.01, seed=4)
    a = raw_signals(b)
    b2 = b + [{"close": b[-1]["close"] * 3, "high": b[-1]["close"] * 3, "volume": 5e6}]
    assert raw_signals(b2)["hi52"] != a["hi52"]
    assert raw_signals(b[:-1] + [dict(b[-1])]) == a
