from pathlib import Path

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


def test_review_math():
    import numpy as np
    from agentic_trader.robinhood import review
    rng = np.random.default_rng(1)
    m = np.cumprod(1 + rng.normal(0.0005, 0.01, 300)) * 100
    assert abs(review._beta(m, m) - 1) < 1e-9
    p = review._projection(m)
    assert p and p["band5"] > 0
    assert review._label(review._sentiment({"num_buy_ratings": 10, "num_hold_ratings": 0, "num_sell_ratings": 0}, 0.2, 0.4, 50)) == "bullish"
    assert review._big(5.0e12) == "$5.00T"


# ---- internal live paper trading -------------------------------------------------
def _pt(tmp_path, quotes_fn, analyze_fn, clock):
    from datetime import datetime
    from agentic_trader import paper_live as pl

    class Data:
        def quotes(self, syms):
            return {s: quotes_fn(s) for s in syms}

        def bars(self, syms, interval, days, **kw):
            return {s: [{"close": 100 + i * 0.1} for i in range(120)] for s in syms}

        def vix(self):
            return 17.0

    class Note:
        sent = []

        def post(self, ch, text, image_path=None):
            self.sent.append((ch, text))

    cfg = pl.Cfg()
    n = Note()
    n.sent = []
    return pl.PaperTrader(Data(), n, pl.Store(mirror=tmp_path / "s.json", storage=False), cfg, clock, analyze_fn), n


def _q(price, as_of):
    return {"price": price, "bid": price * 0.9995, "ask": price * 1.0005, "as_of": as_of, "session": "regular",
            "prev_close": price, "change_pct": 0.0}


def test_paper_live_cycle_fees_and_summaries(tmp_path):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from agentic_trader import paper_live as pl
    ET = ZoneInfo("America/New_York")
    clk = {"t": datetime(2026, 10, 14, 9, 40, tzinfo=ET)}  # Wednesday
    px = {"NVDA": 200.0}
    tr, note = _pt(tmp_path, lambda s: _q(px.get(s, 120.0), clk["t"]),
                   lambda syms: {"NVDA": {"signal_score": 0.5, "rsi14": 55, "realized_vol_ann": 0.35}}, lambda: clk["t"])
    assert tr.step() == "open"
    held = tr.s["positions"]
    assert "NVDA" in held and held["NVDA"]["sleeve"] == "day"
    assert {"VOO", "QQQ", "SCHD", "VXUS"} <= set(held)  # core sleeve deployed
    assert "SH" in held  # VIX 17 -> normal regime -> 5% hedge
    assert not note.sent  # first half-hour slot is 10:00
    clk["t"] = datetime(2026, 10, 14, 10, 0, tzinfo=ET)
    tr.step()
    assert note.sent and note.sent[0][0] == "realtime"
    assert "Profit/Loss (net of fees):\n" in note.sent[0][1] and "Holdings maintained:" in note.sent[0][1]
    # day stop-out is a loss that includes the sell fee
    clk["t"] = datetime(2026, 10, 14, 10, 5, tzinfo=ET)
    px["NVDA"] = 195.0
    tr.step()
    assert "NVDA" not in tr.s["positions"] and tr.s["fees_total"] >= 0.01
    last = [x for x in tr.s["trades"] if x["sym"] == "NVDA"][-1]
    assert last["realized"] < 0 and "stop" in last["reason"]
    # equity = start + realized + unrealized, with fees already deducted from cash
    eq = tr.equity({s: _q(px.get(s, 120.0), clk["t"]) for s in tr.universe()})
    assert abs(eq - tr.s["start_cash"]) < 15
    # flatten + end of day summary goes to the updates channel exactly once
    clk["t"] = datetime(2026, 10, 14, 16, 5, tzinfo=ET)
    assert tr.step() == "close" and tr.step() == "close"
    ups = [m for ch, m in note.sent if ch == "updates"]
    assert len(ups) == 1 and "DAILY SUMMARY" in ups[0] and "Holdings let go:" in ups[0]
    # state persists and reloads
    from agentic_trader.paper_live import Store
    assert Store(mirror=tmp_path / "s.json", storage=False).load()["fees_total"] == tr.s["fees_total"]


def test_paper_live_idle_when_closed_and_no_account_access(tmp_path):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from pathlib import Path
    ET = ZoneInfo("America/New_York")
    t = datetime(2026, 10, 17, 11, 0, tzinfo=ET)  # Saturday
    tr, note = _pt(tmp_path, lambda s: _q(100.0, t), lambda s: {}, lambda: t)
    assert tr.step() == "idle" and not tr.s["positions"] and not note.sent
    src = (Path(__file__).resolve().parents[1] / "agentic_trader" / "paper_live.py").read_text()
    assert "robinhood.account" not in src and "robinhood import orders" not in src and "call_account" not in src


def test_fees_and_regime():
    from agentic_trader import paper_live as pl
    assert pl.sell_fees(1.0, 50.0) == 0.01
    assert pl.sell_fees(100.0, 20000.0) > 0.4
    assert pl.classify_regime(14, 0.10, False)["hedge_target"] == 0.0
    assert pl.classify_regime(35, 0.2, True)["hedge_target"] == 0.25


def test_tables_and_splitter():
    from agentic_trader.tables import FENCE, split_message, table, to_telegram_html, holdings_tables
    t = table(["A", "B"], [["x", "1"], ["yy", "22"]], title="T")
    assert t.startswith("T") and FENCE in t
    big = "\n\n".join([table(["A"], [["r%d" % i] for i in range(30)])] * 6)
    for chunk in split_message(big, 900):
        assert chunk.count(FENCE) % 2 == 0
    assert "<pre>" in to_telegram_html(t) and "<" not in to_telegram_html("a<b").replace("&lt;", "")
    assert holdings_tables([]) == ""
    assert "VOO" in holdings_tables([{"ticker": "VOO", "weight": 50, "sector": "Core"}])


def test_pdt_rule_2026(tmp_path):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from agentic_trader import paper_live as pl
    t = datetime(2026, 10, 15, 11, 0, tzinfo=ZoneInfo("America/New_York"))
    cfg = pl.Cfg()
    st = pl.Store(mirror=tmp_path / "s.json", storage=False)
    tr = pl.PaperTrader(type("D", (), {})(), type("N", (), {"post": lambda *a: None})(), st, cfg, lambda: t, lambda s: {})
    assert tr.s["start_cash"] == 5000 and not tr.pdt_limited()
    q = _q(100, t)
    for i in range(4):
        assert tr.buy("AAPL", 100, "day", "x", q, t) and tr.sell("AAPL", 1, "x", q, t)
    assert tr.day_trades_5d(t) == 4
    tr.cfg.account_type = "cash"
    tr.s["equity_log"] = [[t.isoformat(), 5000]]
    assert tr.pdt_limited()
    tr.buy("AAPL", 100, "day", "x", q, t)
    assert not tr.sell("AAPL", 1, "x", q, t) and tr.pdt_blocked == 1


def test_session_chart_half_hour_series_and_png(tmp_path):
    from datetime import date, datetime
    from agentic_trader import session_chart as sc
    day = date(2026, 10, 16)
    slots = sc.session_slots(day)
    assert len(slots) == 14 and slots[0].strftime("%H:%M") == "09:30" and slots[-1].strftime("%H:%M") == "16:00"
    log = [[slots[0].isoformat(), 5000.0], [slots[2].isoformat(), 5050.0], [slots[-1].isoformat(), 5100.0]]
    port = sc.portfolio_series(log, 5000.0, slots)
    assert port[0] == 0 and abs(port[2] - 0.01) < 1e-9 and abs(port[-1] - 0.02) < 1e-9
    bars = [{"ts": s, "open": 100.0, "close": 101.0} for s in slots[:-1]]
    bench = sc.benchmark_series(bars, 100.0, slots)
    assert bench[0] == 0 and abs(bench[-1] - 0.01) < 1e-9
    png = sc.build_chart(log, 5000.0, {"SPY": bars, "DIA": bars}, {"SPY": 100.0, "DIA": 100.0}, day, tmp_path)
    assert png and Path(png).stat().st_size > 1000


def test_day_rank_blends_regression_and_sentiment():
    from agentic_trader.paper_live import PaperTrader
    base = {"signal_score": 0.3}
    good = {"signal_score": 0.3, "scorecard": {"ic": 0.2}}
    assert PaperTrader.day_rank(good, 1.0) > PaperTrader.day_rank(base) > PaperTrader.day_rank(base, -1.0)


def test_options_income_never_naked_and_wheel(tmp_path):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from agentic_trader import paper_live as pl
    ET = ZoneInfo("America/New_York")
    t = datetime(2026, 10, 22, 11, 0, tzinfo=ET)
    tr = pl.PaperTrader(type("D", (), {})(), type("N", (), {"post": lambda *a: None})(),
                        pl.Store(mirror=tmp_path / "s.json", storage=False), pl.Cfg(), lambda: t, lambda s: {})
    inc = tr.income
    put = {"id": "p1", "strike": 20.0, "exp": "2026-10-30", "type": "put"}
    q = {"bid": 0.40, "ask": 0.45, "mark": 0.42}
    # cash-secured put: reserves strike x 100, premium credited net of fee
    assert inc.sell_to_open("put", "SOFI", put, q, 1, t)
    assert inc.collateral() == 2000 and tr.free_cash() < tr.s["cash"] and not inc.naked_violations()
    # cannot sell a put the free cash does not secure
    big = {"id": "p2", "strike": 60.0, "exp": "2026-10-30", "type": "put"}
    assert not inc.sell_to_open("put", "XYZ", big, q, 1, t)
    # naked call refused (no shares)
    call = {"id": "c1", "strike": 22.0, "exp": "2026-10-30", "type": "call"}
    assert not inc.sell_to_open("call", "SOFI", call, q, 1, t)
    # put assigned at expiry -> 100 income shares, premium kept
    cash0 = tr.s["cash"]
    inc.settle(inc.opts[0], 19.0, t)
    assert tr.s["positions"]["SOFI"]["qty"] == 100 and abs(tr.s["cash"] - (cash0 - 2000)) < 1e-6 and not inc.opts
    # covered call now allowed, shares locked while it is open
    assert inc.sell_to_open("call", "SOFI", call, q, 1, t) and not inc.naked_violations()
    assert not tr.sell("SOFI", 100, "x", _q(19, t), t)
    # called away: shares sold at strike, position gone
    inc.settle(inc.opts[0], 23.0, t)
    assert "SOFI" not in tr.s["positions"] and not inc.opts
    assert tr.s["realized_total"] > 0
    assert tr.goal_line("Day", 0.03, 0.02, 0.05).endswith("(on target)")
