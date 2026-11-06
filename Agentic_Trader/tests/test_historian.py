import json
import sqlite3
from datetime import timedelta

import pytest

from agentic_trader import grafana_export
from agentic_trader.desk import agent_of
from agentic_trader.historian import Historian, briefing_lines
from tests.test_desk import Data, REG, T, _q, trader


def _close(day_offset, sym, realized, sleeve="day", strat="ORB", hour=11):
    ts = (T - timedelta(days=day_offset)).replace(hour=hour).isoformat()
    return {"ts": ts, "side": "sell", "sym": sym, "sleeve": sleeve, "strat": strat, "qty": 1, "px": 1, "fee": 0,
            "value": 1, "realized": realized, "closed": True}


def _opt_close(day_offset, sym, realized, strat="yield_puts"):
    ts = (T - timedelta(days=day_offset)).isoformat()
    return {"ts": ts, "side": "option", "sym": sym, "sleeve": "income", "strat": strat, "qty": 1, "px": 0.1, "fee": 0,
            "value": 0, "desc": f"BUY TO CLOSE {sym}", "realized": realized}


def _hist(tr):
    return Historian(tr.cfg)


def test_briefing_summarizes_yesterday_week_and_history_per_team(tmp_path, monkeypatch):
    tr = trader(tmp_path, Data(), monkeypatch)
    trades = [_close(1, "MSFT", 8.0), _close(1, "AMD", -3.0), _close(4, "AAPL", 2.0, strat="PULLBACK"),
              _close(40, "NVDA", -5.0), _opt_close(1, "F", 6.0)]
    b = _hist(tr).build(trades, T, agent_of, 5000, {})
    day = b["teams"]["day"]
    assert b["last_day"] == (T - timedelta(days=1)).date().isoformat()
    assert day["yesterday"]["closed"] == 2 and day["yesterday"]["net"] == 5.0
    assert day["yesterday"]["best"] == ["MSFT", 8.0] and day["yesterday"]["worst"] == ["AMD", -3.0]
    assert day["week"]["closed"] == 3 and day["history"]["closed"] == 4
    assert b["teams"]["options"]["yesterday"]["net"] == 6.0
    assert b["teams"]["growth"]["history"]["closed"] == 0
    assert any("history is thin" in x for x in day["lines"])


def test_symbols_with_repeated_losses_are_avoided_and_winners_favored(tmp_path, monkeypatch):
    tr = trader(tmp_path, Data(), monkeypatch)
    trades = [_close(i, "NVDA", -6.0) for i in (1, 2, 3)] + [_close(i, "MSFT", 4.0) for i in (1, 2, 3)]
    trades += [_close(1, "AMD", -6.0), _close(2, "AMD", -6.0)]  # only two trades: too thin to act on
    day = _hist(tr).build(trades, T, agent_of, 5000, {})["teams"]["day"]
    assert "NVDA" in day["avoid"] and "MSFT" in day["favored"] and "AMD" not in day["avoid"]
    assert "ORB|NVDA" in day["avoid_strat"]
    assert any(x.startswith("avoiding: NVDA") for x in day["lines"])


def test_trivial_losses_are_not_enough_to_avoid(tmp_path, monkeypatch):
    tr = trader(tmp_path, Data(), monkeypatch)
    trades = [_close(i, "NVDA", -0.5) for i in (1, 2, 3)]  # -$1.50 on a $5,000 account
    assert not _hist(tr).build(trades, T, agent_of, 5000, {})["teams"]["day"]["avoid"]


def test_market_line_uses_recorded_spy_closes(tmp_path, monkeypatch):
    tr = trader(tmp_path, Data(), monkeypatch)
    bench = {(T - timedelta(days=d)).date().isoformat(): 700.0 - d for d in range(0, 8)}
    bench[(T - timedelta(days=1)).date().isoformat()] = 690.0
    b = _hist(tr).build([], T, agent_of, 5000, bench)
    assert "SPY" in b["market"]["line"] and b["market"]["spy_yesterday_pct"] == pytest.approx((690 / 698 - 1) * 100)


def test_orchestrator_hands_each_team_its_briefing(tmp_path, monkeypatch):
    tr = trader(tmp_path, Data(), monkeypatch)
    tr.s["trades"] += [_close(i, "NVDA", -6.0) for i in (1, 2, 3)]
    plan = tr.desk.orchestrator.plan({}, T, 5000, REG)
    assert "NVDA" in plan.mandates["day"].brief["avoid"]
    assert plan.mandates["growth"].brief["avoid"] == {}
    assert tr.s["desk"]["briefing"]["teams"]["day"]["history"]["closed"] == 3
    assert any("Desk briefing" in line for line in briefing_lines(tr.s["desk"]["briefing"]))


def test_briefing_can_be_switched_off(tmp_path, monkeypatch):
    tr = trader(tmp_path, Data(), monkeypatch, PAPER_BRIEFING=0)
    tr.s["trades"] += [_close(i, "NVDA", -6.0) for i in (1, 2, 3)]
    plan = tr.desk.orchestrator.plan({}, T, 5000, REG)
    assert plan.mandates["day"].brief == {} and "briefing" not in tr.s["desk"]


def test_day_agent_skips_avoided_symbol_and_favors_proven_one(tmp_path, monkeypatch):
    from tests.test_desk import _snap
    tr = trader(tmp_path, Data(), monkeypatch, PAPER_DAY_SYMBOLS="AAA,BBB", PAPER_QUANT_GATE="0")
    snaps = {"SPY": _snap(price=500, vwap=499), "AAA": _snap(), "BBB": _snap()}
    monkeypatch.setattr(type(tr.desk.day), "_snapshots", lambda self, q, t: snaps)
    quotes = {s: _q(100) for s in snaps}
    tr.s["trades"] += [_close(i, "AAA", -6.0) for i in (1, 2, 3)] + [_close(i, "BBB", 5.0) for i in (1, 2, 3)]
    equity = tr.equity(quotes)
    mandate = tr.desk.orchestrator.plan(quotes, T, equity, REG).mandates["day"]
    tr.desk.day.run(quotes, T, equity, mandate, REG, (11, 0))
    assert "AAA" not in tr.s["positions"] and "BBB" in tr.s["positions"]
    entry = next(x for x in tr.s["trades"] if x["sym"] == "BBB" and x["side"] == "buy")
    assert "briefing favors BBB" in entry["reason"]


def test_options_agent_skips_avoided_symbol(tmp_path, monkeypatch):
    from agentic_trader.options_agents import YieldPuts
    chains = {"F": {"strikes": [9.0, 9.5], "bid": lambda k: 0.30}}
    tr = trader(tmp_path, Data(chains=chains), monkeypatch, PAPER_OPTION_SYMBOLS="F", PAPER_QUANT_GATE="0")
    agent = YieldPuts(tr)
    agent.brief = {"avoid": {"F": "3 closed in 30d, net -$30.00, win rate 0%"}}
    out = agent.run({"F": _q(10)}, T, 5000, 2000, 2000)
    assert out["opened"] == 0 and "weak recent results" in out["note"]
    agent.brief = {}
    tr.s.pop("opt_scan_yield_puts", None)
    assert agent.run({"F": _q(10)}, T, 5000, 2000, 2000)["opened"] == 1


def test_briefing_exports_to_grafana(tmp_path, monkeypatch):
    tr = trader(tmp_path, Data(), monkeypatch)
    tr.s["trades"] += [_close(i, "NVDA", -6.0) for i in (1, 2, 3)]
    tr.desk.orchestrator.plan({}, T, 5000, REG)
    src, dst = tmp_path / "state.json", tmp_path / "out.db"
    src.write_text(json.dumps(tr.s))
    grafana_export.export(src, dst)
    rows = sqlite3.connect(dst).execute("SELECT team, period, closed, avoid FROM briefing WHERE team='day'").fetchall()
    assert {r[1] for r in rows} == {"yesterday", "week", "history"}
    assert any(r[1] == "history" and r[2] == 3 and "NVDA" in r[3] for r in rows)
