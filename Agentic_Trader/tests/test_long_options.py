import json
import sqlite3

import pytest

from agentic_trader import grafana_export
from agentic_trader.options_agents import LongOptionAgent
from agentic_trader.paper_longopts import max_loss
from agentic_trader.paper_options import UnlimitedRiskRefused
from tests.test_desk import Data, REG, T, _q, trader

CHAINS = {"SPY": {"strikes": [98.0, 99.0, 100.0, 101.0, 102.0, 103.0], "bid": lambda k: max(0.1, 3.0 - abs(k - 100) * 0.9)}}


def _tr(tmp_path, monkeypatch, **env):
    env = {"PAPER_LONG_OPTION_MAX_DTE": 10, "PAPER_LONG_OPTION_SYMBOLS": "SPY", "PAPER_QUANT_GATE": "0", **env}
    return trader(tmp_path, Data(CHAINS), monkeypatch, **env)


def _contracts(tr, kind="call"):
    d = tr.data
    cs = {c["strike"]: c for c in d.option_contracts("SPY", "2026-10-30", kind)}
    qs = d.option_quotes([c["id"] for c in cs.values()])
    return cs, qs


def _snap(up=True):
    base = {"or_done": True, "atr5": 0.2, "rsi": 55, "vwap": 100.0, "or_high": 100.5, "or_low": 99.5}
    return {**base, "price": 101.0, "ema9": 101.0, "ema21": 100.5} if up else {**base, "price": 99.0, "ema9": 99.0, "ema21": 99.5}


def test_buying_a_call_caps_loss_at_the_debit_and_settles_in_cash(tmp_path, monkeypatch):
    tr = _tr(tmp_path, monkeypatch)
    cs, qs = _contracts(tr)
    cash = tr.s["cash"]
    assert tr.longopts.buy_to_open("SPY", "call", cs[100.0], qs[cs[100.0]["id"]], 2, T, strat="long_options")
    o = tr.longopts.opts[0]
    assert max_loss(o) == pytest.approx(o["debit"] * 200 + o["fee_open"])
    assert tr.s["cash"] == pytest.approx(cash - o["debit"] * 200 - o["fee_open"])
    assert tr.equity({"SPY": _q(100)}) == pytest.approx(cash - o["fee_open"])  # marked at the debit paid
    tr.longopts.settle(o, 99.0, T)  # out of the money: loses exactly the premium and fees
    assert not tr.longopts.opts and "SPY" not in tr.s["positions"]
    assert tr.s["trades"][-1]["realized"] == pytest.approx(-(o["debit"] * 200 + o["fee_open"]))


def test_debit_spread_is_capped_by_the_debit_and_limited_by_the_short_leg(tmp_path, monkeypatch):
    tr = _tr(tmp_path, monkeypatch)
    cs, qs = _contracts(tr)
    assert tr.longopts.buy_to_open("SPY", "call", cs[100.0], qs[cs[100.0]["id"]], 1, T, short=cs[102.0],
                                   short_q=qs[cs[102.0]["id"]])
    o = tr.longopts.opts[0]
    assert o["kind"] == "call_debit_spread" and o["debit"] < 2.0
    tr.longopts.settle(o, 110.0, T)  # far in the money: capped at the width
    assert tr.s["trades"][-1]["px"] == 2.0 and tr.s["trades"][-1]["realized"] > 0


def test_short_or_inverted_positions_are_refused(tmp_path, monkeypatch):
    tr = _tr(tmp_path, monkeypatch)
    cs, qs = _contracts(tr)
    lq = qs[cs[100.0]["id"]]
    with pytest.raises(UnlimitedRiskRefused):  # short leg closer to the money than the long leg
        tr.longopts.buy_to_open("SPY", "call", cs[100.0], lq, 1, T, short=cs[99.0], short_q=qs[cs[99.0]["id"]])
    with pytest.raises(UnlimitedRiskRefused):  # a spread that would be opened for a credit
        tr.longopts.buy_to_open("SPY", "call", cs[103.0], qs[cs[103.0]["id"]], 1, T, short=cs[102.0] | {"strike": 104.0},
                                short_q={"bid": 5.0})
    with pytest.raises(UnlimitedRiskRefused):
        tr.longopts.buy_to_open("SPY", "straddle", cs[100.0], lq, 1, T)
    assert not tr.longopts.opts and max_loss({"kind": "naked_call", "debit": 1, "qty": 1}) is None


def test_exits_stop_trail_take_profit_and_expiry_close(tmp_path, monkeypatch):
    tr = _tr(tmp_path, monkeypatch)
    cs, qs = _contracts(tr)
    tr.longopts.buy_to_open("SPY", "call", cs[100.0], qs[cs[100.0]["id"]], 1, T)
    o = tr.longopts.opts[0]
    cid = o["id"]
    quote = lambda mark: {cid: {"bid": mark, "ask": mark + 0.02, "mark": mark, "oi": 500}}
    d = o["debit"]
    monkeypatch.setattr(tr.data, "option_quotes", lambda ids: quote(d * 0.4), raising=False)
    tr.longopts.manage(T)  # down 60% > 50% stop
    assert not tr.longopts.opts and "stop" in tr.s["trades"][-1]["reason"]
    tr.longopts.buy_to_open("SPY", "call", cs[100.0], qs[cid], 1, T)
    monkeypatch.setattr(tr.data, "option_quotes", lambda ids: quote(d * 3.5), raising=False)
    tr.longopts.manage(T)
    assert not tr.longopts.opts and "took profit" in tr.s["trades"][-1]["reason"]
    tr.longopts.buy_to_open("SPY", "call", cs[100.0], qs[cid], 1, T)
    for mark in (d * 1.8, d * 1.1):  # run up, then give back more than 35% of the peak
        monkeypatch.setattr(tr.data, "option_quotes", lambda ids, m=mark: quote(m), raising=False)
        tr.longopts.manage(T)
    assert not tr.longopts.opts and "trailing" in tr.s["trades"][-1]["reason"]
    tr.longopts.buy_to_open("SPY", "call", cs[100.0], qs[cid], 1, T)
    tr.longopts.opts[0]["exp"] = T.date().isoformat()
    monkeypatch.setattr(tr.data, "option_quotes", lambda ids: quote(d), raising=False)
    tr.longopts.manage(T.replace(hour=15, minute=50))
    assert not tr.longopts.opts and "bell" in tr.s["trades"][-1]["reason"]


def test_agent_buys_a_call_on_a_breakout_and_a_put_on_a_breakdown(tmp_path, monkeypatch):
    for up, kind in ((True, "call"), (False, "put")):
        tr = _tr(tmp_path, monkeypatch)
        monkeypatch.setattr(LongOptionAgent, "_snapshots", lambda self, syms, q, t: {"SPY": _snap(up)})
        quotes = {"SPY": _q(100)}
        mandate = tr.desk.orchestrator.plan(quotes, T, 5000, REG).mandates["options"]
        tr.desk.options.run(quotes, T, tr.equity(quotes), mandate)
        longs = tr.longopts.opts
        assert [o["type"] for o in longs] == [kind] and longs[0]["strat"] == "long_options"
        assert max_loss(longs[0]) <= 5000 * 0.5 * 0.10 + 1  # per-trade cap: 10% of the options budget
        assert not tr.income.naked_violations()


def test_agent_uses_a_debit_spread_when_a_single_leg_is_too_expensive(tmp_path, monkeypatch):
    tr = _tr(tmp_path, monkeypatch, PAPER_LONG_OPTION_TRADE_PCT=0.05)  # $125 per trade; the ATM call costs ~$300
    monkeypatch.setattr(LongOptionAgent, "_snapshots", lambda self, syms, q, t: {"SPY": _snap(True)})
    quotes = {"SPY": _q(100)}
    mandate = tr.desk.orchestrator.plan(quotes, T, 5000, REG).mandates["options"]
    tr.desk.options.run(quotes, T, tr.equity(quotes), mandate)
    o = tr.longopts.opts[0]
    assert o["kind"] == "call_debit_spread" and max_loss(o) <= 5000 * 0.5 * 0.05 + 1


def test_agent_respects_briefing_no_setup_and_the_off_switch(tmp_path, monkeypatch):
    tr = _tr(tmp_path, monkeypatch)
    agent = LongOptionAgent(tr)
    monkeypatch.setattr(LongOptionAgent, "_snapshots", lambda self, syms, q, t: {"SPY": _snap(True)})
    agent.brief = {"avoid": {"SPY": "3 closed in 30d, net -$30.00, win rate 0%"}}
    out = agent.run({"SPY": _q(100)}, T, 5000, 0, 2000, 2500)
    assert out["opened"] == 0 and "weak recent results" in out["note"]
    agent.brief = {}
    tr.s.pop("opt_scan_long_options")
    monkeypatch.setattr(LongOptionAgent, "_snapshots", lambda self, syms, q, t: {"SPY": None})
    assert "no breakout setup" in agent.run({"SPY": _q(100)}, T, 5000, 0, 2000, 2500)["note"]
    off = _tr(tmp_path, monkeypatch, PAPER_LONG_OPTIONS=0)
    assert LongOptionAgent(off).run({"SPY": _q(100)}, T, 5000, 0, 2000, 2500)["opened"] == 0


def test_long_options_export_to_grafana(tmp_path, monkeypatch):
    tr = _tr(tmp_path, monkeypatch)
    cs, qs = _contracts(tr)
    tr.longopts.buy_to_open("SPY", "call", cs[100.0], qs[cs[100.0]["id"]], 1, T, strat="long_options")
    src, dst = tmp_path / "state.json", tmp_path / "out.db"
    src.write_text(json.dumps(tr.s))
    grafana_export.export(src, dst)
    row = sqlite3.connect(dst).execute("SELECT strat, kind, max_loss FROM options").fetchone()
    assert row[0] == "long_options" and row[1] == "long_call" and row[2] > 0
