from agentic_trader import day_strategy as ds
from agentic_trader.paper_live import Cfg


def test_indicators():
    assert ds.ema([1, 1, 1, 1], 3)[-1] == 1
    assert ds.rsi([float(i) for i in range(1, 30)])[-1] > 90 if hasattr(ds.rsi([1.0] * 20), "__getitem__") else True


def _m(**kw):
    m = dict(price=100.0, vwap=99.5, ema9=100.0, ema21=99.0, rsi=60, rsi_prev=58, atr5=0.3, atr5_pct=0.003,
             daily_atr_pct=0.025, or_high=99.8, or_low=98.5, or_done=True, rvol=1.5, last_close=100.0,
             last_low=99.7, day_open=99.0, day_high=100.1, day_low=98.5, daily_ma20=98.0, daily_ma50=95.0,
             prev_close=98.8, above_vwap_share=0.8)
    m.update(kw)
    return m


def test_plan_has_stop_and_risk_sizing():
    c = Cfg()
    p = ds.plan_trade(_m(), c, 5000, 5000, 1.0)
    assert p["stop"] < 100 and p["target"] > 100
    assert p["risk_usd"] <= 5000 * c.risk_pct * 1.01
    assert p["notional"] <= 5000 * c.max_position_pct * 1.01


def test_manage_stop_moves_up_only_and_exits_on_target():
    c = Cfg()
    pos = {"avg": 100.0, "stop_px": 99.0, "target_px": 102.0, "r_per_share": 1.0, "high": 100.0, "opened_hm": 600}
    reason, stop = ds.manage(pos, _m(price=101.2), 101.2, (10, 20), c)
    assert reason is None and stop and stop >= 100.0
    reason, _ = ds.manage(pos, _m(price=102.1), 102.1, (10, 30), c)
    assert reason
