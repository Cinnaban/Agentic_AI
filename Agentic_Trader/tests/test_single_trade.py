from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np

from test_trader import _pt, _q

ET = ZoneInfo("America/New_York")


def test_day_agent_one_trade_then_flatten(tmp_path):
    clk = {"t": datetime(2026, 10, 14, 9, 40, tzinfo=ET)}
    tr, _ = _pt(tmp_path, lambda s: _q({"NVDA": 200.0, "AMD": 150.0}.get(s, 120.0), clk["t"]),
                lambda syms: {"NVDA": {"signal_score": 0.5, "rsi14": 55, "realized_vol_ann": 0.35},
                              "AMD": {"signal_score": 0.9, "rsi14": 55, "realized_vol_ann": 0.35}}, lambda: clk["t"])
    tr.step()
    assert tr.s["day"]["single"]["day"]["sym"] in ("NVDA", "AMD")
    n = len(tr.s["trades"])
    for h, m in ((9, 50), (10, 5), (11, 0), (13, 0)):
        clk["t"] = clk["t"].replace(hour=h, minute=m)
        tr.step()
    assert len(tr.s["trades"]) == n  # no further trades and no intraday exits
    clk["t"] = clk["t"].replace(hour=15, minute=51)
    tr.step()
    sells = [x for x in tr.s["trades"] if x["side"] == "sell" and x["sleeve"] == "day"]
    assert len(sells) == 1 and "end-of-day" in sells[0]["reason"]
    assert not any(p["sleeve"] == "day" for p in tr.s["positions"].values())


def test_no_entry_after_window(tmp_path):
    clk = {"t": datetime(2026, 10, 14, 11, 0, tzinfo=ET)}
    tr, _ = _pt(tmp_path, lambda s: _q(120.0, clk["t"]),
                lambda syms: {"NVDA": {"signal_score": 0.9, "rsi14": 55, "realized_vol_ann": 0.3}}, lambda: clk["t"])
    tr.step()
    assert not tr.s["trades"]
    assert tr.s["day"]["single"]["day"]["sym"] is None and tr.s["day"]["single"]["growth"]["sym"] is None


def test_scoring_pillars():
    from agentic_trader import single_trade as st
    up, down = list(np.linspace(100, 130, 120)), list(np.linspace(130, 100, 120))
    assert st.trend_score(up, up[-1]) > 0.3 > -0.3 > st.trend_score(down, down[-1])
    s, cov = st.composite({"prediction": 0.5, "sentiment": None, "financials": None, "trend": 0.5})
    assert abs(s - 0.5) < 1e-9 and abs(cov - 0.6) < 1e-9
    assert (st.financial_score({"pe_ratio": "15", "market_cap": "2e11"})
            > st.financial_score({"pe_ratio": "-3", "market_cap": "2e8"}))


def test_stop_losses_scale_with_volatility_and_sit_outside_the_entry_limit(tmp_path):
    clk = {"t": datetime(2026, 10, 14, 9, 40, tzinfo=ET)}
    px = {"NVDA": 200.0}
    tr, _ = _pt(tmp_path, lambda s: _q(px.get(s, 120.0), clk["t"]),
                lambda syms: {"NVDA": {"signal_score": 0.5, "rsi14": 55, "realized_vol_ann": 0.35}}, lambda: clk["t"])
    assert tr.stop_for("day", 0.10) == tr.cfg.day_stop_min and tr.stop_for("day", 2.0) == tr.cfg.day_stop_max
    assert tr.stop_for("core", 0.05) == tr.cfg.growth_stop_min and tr.stop_for("core", 1.0) == tr.cfg.growth_stop_max
    tr.step()
    assert tr.s["positions"]["NVDA"]["stop_pct"] >= tr.cfg.day_stop_min
    assert all(p.get("stop_pct") for p in tr.s["positions"].values() if p["sleeve"] == "core")
    clk["t"] = clk["t"].replace(hour=10, minute=5)
    px["NVDA"] = 200.0 * (1 - tr.s["positions"]["NVDA"]["stop_pct"] - 0.002)
    tr.step()
    stopped = [x for x in tr.s["trades"] if x["sym"] == "NVDA" and x["side"] == "sell"]
    assert len(stopped) == 1 and "stop loss" in stopped[0]["reason"] and "NVDA" not in tr.s["positions"]
    n = len(tr.s["trades"])
    clk["t"] = clk["t"].replace(hour=10, minute=20)
    px["NVDA"] = 200.0
    tr.step()
    assert len(tr.s["trades"]) == n  # no re-entry after the stop: still one entry per day
