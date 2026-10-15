import numpy as np
import pandas as pd
import pytest

from agentic_trader import compute, indicators as ind
from agentic_trader.brokers.paper import PaperBroker
from agentic_trader.config import Settings
from agentic_trader.data.mock import MockProvider
from agentic_trader.engine import Engine
from agentic_trader.improve import fit_and_validate
from agentic_trader.notify.discord import DiscordNotifier
from agentic_trader.strategies.day_trader import DEFAULT_PARAMS, DayTradeStrategy
from agentic_trader.strategies.etf_core import ETFCoreStrategy


@pytest.fixture
def settings(monkeypatch, tmp_path):
    monkeypatch.setattr("agentic_trader.config.STATE_DIR", tmp_path)
    monkeypatch.setattr("agentic_trader.notify.discord.STATE_DIR", tmp_path)
    monkeypatch.setattr("agentic_trader.engine.STATE_DIR", tmp_path)
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    s = Settings()
    return s


def test_live_mode_rejected(monkeypatch):
    monkeypatch.setenv("TRADING_MODE", "live")
    with pytest.raises(RuntimeError):
        Settings.from_env()


def test_indicators_and_sweep():
    c = pd.Series(np.linspace(100, 120, 200) + np.sin(np.arange(200)))
    assert 0 <= ind.rsi(c).iloc[-1] <= 100
    res = compute.sweep_ma_crossover(c.values, [5, 9], [20, 30])
    assert res and res[0]["fast"] < res[0]["slow"]


def test_paper_broker_no_leverage_no_short():
    b = PaperBroker(1000, persist=False)
    f = b.submit_order("day", "X", "buy", 100, 50.0, "t")
    assert f.qty < 20 and b.cash >= 0
    assert b.submit_order("day", "Y", "sell", 5, 10.0, "t") is None


def test_etf_trend_filter_rotates_to_bond():
    up = pd.DataFrame({"close": np.linspace(50, 100, 260)})
    down = pd.DataFrame({"close": np.linspace(100, 50, 260)})
    w = ETFCoreStrategy({"VTI": 0.6, "BND": 0.4}).target_weights({"VTI": down, "BND": up})
    assert w["BND"] > 0.4 and abs(sum(w.values()) - 1) < 1e-9


def test_regression_pipeline_runs():
    p = MockProvider(["SPY"])
    p.cursor = len(p.idx)
    m = fit_and_validate({"SPY": p.get_bars("SPY", "1m", 5000)})["metrics"]
    assert m["n_train"] > m["n_test"] > 0


def test_simulation_sends_half_hour_and_daily(settings):
    prov = MockProvider(settings.day_symbols + list(settings.etf_universe))
    n = DiscordNotifier(settings, echo=False)
    e = Engine(settings, prov, PaperBroker(100_000, persist=False), n, DayTradeStrategy(dict(DEFAULT_PARAMS)))
    e.run_simulation()
    realtime = [t for c, t in n.sent if c == "realtime"]
    updates = [t for c, t in n.sent if c == "updates"]
    assert len(realtime) >= 12 and len(updates) == 1
    assert not e.broker.positions["day"]  # flattened at close
    assert e.broker.positions["etf"]  # ETF sleeve was built
    assert e.broker.cash >= 0


def test_shock_triggers_hedge(settings):
    prov = MockProvider(settings.day_symbols + list(settings.etf_universe))
    prov.cursor = 4 * 390 + 120
    prov.inject_shock("SPY", -0.03)
    n = DiscordNotifier(settings, echo=False)
    e = Engine(settings, prov, PaperBroker(100_000, persist=False), n, DayTradeStrategy(dict(DEFAULT_PARAMS)))
    e.run_simulation(max_ticks=60)
    assert any(f.symbol == "SH" and f.side == "buy" for f in e.broker.fills)


def test_robinhood_client_only_calls_market_data():
    from agentic_trader.robinhood.mcp_client import ReadOnlyViolation, RobinhoodMCP
    for tool in ("place_equity_order", "exercise_option", "get_portfolio", "update_watchlist", "get_equity_positions"):
        with pytest.raises(ReadOnlyViolation):
            RobinhoodMCP(allow={tool}).call(tool)


class FakeResearch:
    @staticmethod
    def snapshot(symbols, earnings_days=14):
        return {s: {"quote": None, "ratings": None, "consensus": f"90% Buy ({s})",
                    "next_earnings": "2026-10-14" if s == "AAPL" else None, "upside_to_target": None} for s in symbols}


def test_earnings_blackout_and_analyst_line_in_daily_summary(settings):
    prov = MockProvider(settings.day_symbols + list(settings.etf_universe))
    n = DiscordNotifier(settings, echo=False)
    e = Engine(settings, prov, PaperBroker(100_000, persist=False), n, DayTradeStrategy(dict(DEFAULT_PARAMS)), research=FakeResearch)
    e.run_simulation()
    assert e.blackout == {"AAPL"}
    assert not any(f.symbol == "AAPL" and f.side == "buy" for f in e.broker.fills)
    daily = [t for c, t in n.sent if c == "updates"][0]
    assert "Earnings-day no-entry list: AAPL" in daily and "Analyst consensus" in daily


def test_robinhood_data_parses_quote_and_picks_latest_session():
    from agentic_trader.robinhood.data import RobinhoodData
    d = RobinhoodData()
    d._call = lambda tool, args, ttl: {"results": [{"quote": {
        "symbol": "SPY", "last_trade_price": "770", "venue_last_trade_time": "2026-10-14T19:59:59Z",
        "last_non_reg_trade_price": "766", "venue_last_non_reg_trade_time": "2026-10-15T06:00:00Z",
        "adjusted_previous_close": "770", "bid_price": "765.9", "ask_price": "766.1", "state": "active"}}]}
    q = d.quotes(["spy"])["SPY"]
    assert q["price"] == 766.0 and q["session"] == "extended" and round(q["change_pct"], 4) == -0.0052


def _bars(n=300, seed=1):
    import numpy as np
    r = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(r.normal(0, 0.001, n)))
    return [{"close": float(x), "high": float(x * 1.001), "low": float(x * 0.999), "volume": 1000} for x in c]


def test_quant_live_metrics_and_scorecard():
    from agentic_trader import quant_live
    b = _bars()
    m = quant_live.metrics({"symbol": "T", "price": b[-1]["close"], "bid": 99.9, "ask": 100.1}, b, _bars(seed=2))
    assert -1 <= m["signal_score"] <= 1 and "beta_vs_spy" in m and m["realized_vol_ann"] > 0
    sc = quant_live.prediction_scorecard(b)
    assert {"ic", "hit_rate", "r2", "rmse", "calibration_slope"} <= set(sc)


def test_shared_storage_cache_roundtrip(tmp_path):
    from agentic_trader.robinhood import data as d
    st = d._storage()
    if st is None:
        return
    k = st.build_cache_key({"t": "pytest"})
    st.set_cached_data("robinhood_market", k, {"ok": 1}, 5)
    assert st.get_cached_data("robinhood_market", k) == {"ok": 1}


def test_ts_handles_odd_fraction_digits():
    from agentic_trader.robinhood.data import _ts
    for v in ("2026-10-15T07:44:24.1Z", "2026-10-15T07:44:24.12345Z", "2026-10-15T07:44:24Z", "2026-10-15T07:44:24.123456789+00:00"):
        assert _ts(v) is not None


def test_account_tools_not_callable_from_market_client():
    import pytest
    from agentic_trader.robinhood.mcp_client import ReadOnlyViolation, RobinhoodMCP
    c = RobinhoodMCP(allow={"get_portfolio", "place_equity_order"})
    for name in ("get_portfolio", "place_equity_order", "get_accounts"):
        with pytest.raises(ReadOnlyViolation):
            c.call(name, {})
    for name in ("place_option_order", "cancel_equity_order", "place_crypto_order", "get_option_positions"):
        with pytest.raises(ReadOnlyViolation):
            c.call_account(name, {})


def _fake_account(monkeypatch, bp=5.0, held=None, live=False):
    from agentic_trader.robinhood import account, orders
    placed = []
    monkeypatch.setattr(account, "agentic_account", lambda: {"account_number": "A1"})
    monkeypatch.setattr(account, "review_order", lambda a: {"order_checks": {}, "quote_data": {"ask_price": "100", "bid_price": "99.9"}})
    monkeypatch.setattr(account, "portfolio", lambda n: {"buying_power": {"unleveraged_buying_power": str(bp)}})
    monkeypatch.setattr(account, "positions", lambda n: held or [])
    monkeypatch.setattr(account, "approval_required", lambda n: True)
    monkeypatch.setattr(account, "place_order", lambda a: placed.append(a) or {"content": [{"text": "{\"data\":{}}"}]})
    monkeypatch.setattr(orders, "_spent_today", lambda: 0.0)
    monkeypatch.setattr(orders, "_record", lambda x: None)
    monkeypatch.setattr(orders, "_audit", lambda e: None)
    monkeypatch.setenv("ROBINHOOD_LIVE_ORDERS", "true" if live else "false")
    return orders, placed


def test_order_guards_and_confirm(monkeypatch):
    orders, placed = _fake_account(monkeypatch, bp=5.0, live=True)
    assert "Blocked" in orders.propose("/buy NVDA $50", 1)  # over buying power (no margin)
    assert "Blocked" in orders.propose("/sell NVDA 1", 1)  # nothing held
    assert "Usage" in orders.propose("/buy NVDA call 5", 1)
    out = orders.propose("/buy NVDA $2", 1)
    code = out.split("/confirm ")[1].split()[0]
    assert "different user" in orders.confirm(code, 2) and not placed
    code = orders.propose("/buy NVDA $2", 1).split("/confirm ")[1].split()[0]
    assert "submitted" in orders.confirm(code, 1) and len(placed) == 1
    assert placed[0]["account_number"] == "A1" and "ref_id" in placed[0]
    assert "No valid" in orders.confirm(code, 1)  # single use


def test_orders_disabled_by_default(monkeypatch):
    orders, placed = _fake_account(monkeypatch, live=False)
    code = orders.propose("/buy NVDA $2", 1).split("/confirm ")[1].split()[0]
    assert "disabled" in orders.confirm(code, 1) and not placed
