import json
import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest

from agentic_trader import grafana_export
from agentic_trader.day_agents import DayDesk
from agentic_trader.paper_live import PaperTrader
from tests.test_desk import Data, REG, T, _q, _snap, trader


def _setup(tmp_path, monkeypatch):
    tr = trader(tmp_path, Data(), monkeypatch, PAPER_DAY_SYMBOLS="AAA,BBB,CCC,DDD",
                PAPER_QUANT_GATE=0, PAPER_NEWS_SIGNAL=0, PAPER_SIGNAL_RANK=0)
    quotes = {s: _q(100) for s in ("SPY", "AAA", "BBB", "CCC", "DDD")}
    snapshots = {s: _snap(last_close=100.1, last_low=99.5) for s in quotes}
    monkeypatch.setattr(DayDesk, "_snapshots", lambda self, q, t: snapshots)
    return tr, quotes


def test_comparison_accounts_are_isolated_and_start_with_equal_budget(tmp_path, monkeypatch):
    tr, quotes = _setup(tmp_path, monkeypatch)
    tr.day_comparison.run(quotes, T, REG)
    experiment = tr.s["day_comparison"]
    multi, single = experiment["teams"]["multi"], experiment["teams"]["single"]
    assert multi["start_cash"] == single["start_cash"] == tr.cfg.start_cash
    assert experiment["budget_pct"] == tr.cfg.day_pct
    assert len([x for x in multi["trades"] if x["side"] == "buy"]) >= 2
    assert len(single["trades"]) == 1 and single["trades"][0]["strat"] == "PULLBACK"
    assert tr.s["cash"] == tr.cfg.start_cash and not tr.s["trades"] and not tr.s["positions"]
    assert multi is not single and multi["positions"] is not single["positions"]


def test_one_entry_limit_survives_exit_and_restart(tmp_path, monkeypatch):
    tr, quotes = _setup(tmp_path, monkeypatch)
    tr.day_comparison.run(quotes, T, REG)
    single = tr.s["day_comparison"]["teams"]["single"]
    sym = next(iter(single["positions"]))
    stopped = dict(quotes)
    stopped[sym] = _q(99)
    tr.day_comparison.run(stopped, T + timedelta(minutes=2), REG)
    assert not single["positions"]
    assert [t["side"] for t in single["trades"]] == ["buy", "sell"]
    tr.store.save(tr.s)
    reloaded = PaperTrader(tr.data, tr.n, tr.store, tr.cfg, lambda: T, tr.analyze)
    reloaded.day_comparison.run(quotes, T + timedelta(minutes=4), REG)
    saved = reloaded.s["day_comparison"]["teams"]["single"]
    assert [t["side"] for t in saved["trades"]] == ["buy", "sell"]
    assert "team cap of 1 entries" in saved["desk"]["day_note"]
    reloaded.day_comparison.run(quotes, T + timedelta(days=1), REG)
    assert sum(t["side"] == "buy" for t in saved["trades"]) == 2
    assert saved["cash"] != pytest.approx(reloaded.s["day_comparison"]["teams"]["multi"]["cash"])


def test_no_setup_means_no_trade_and_snapshot_failure_keeps_exits(tmp_path, monkeypatch):
    tr, quotes = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(DayDesk, "_snapshots", lambda self, q, t: {})
    tr.day_comparison.run(quotes, T, REG)
    single = tr.s["day_comparison"]["teams"]["single"]
    assert not single["trades"]
    monkeypatch.setattr(DayDesk, "_snapshots", lambda self, q, t: {s: _snap(last_close=100.1, last_low=99.5) for s in quotes})
    tr.day_comparison.run(quotes, T + timedelta(minutes=2), REG)
    assert single["positions"]

    def fail(*args):
        raise RuntimeError("market data unavailable")

    monkeypatch.setattr(DayDesk, "_snapshots", fail)
    tr.day_comparison.run(quotes, T.replace(hour=15, minute=50), REG)
    assert not single["positions"]
    assert "market data unavailable" in tr.s["day_comparison"]["last_error"]
    assert single["trades"][-1]["side"] == "sell"


def test_idle_initialization_persists_without_trading(tmp_path, monkeypatch):
    tr, quotes = _setup(tmp_path, monkeypatch)
    tr.clock = lambda: T + timedelta(days=3)
    assert tr.step() == "idle"
    saved = json.loads(tr.store.mirror.read_text())
    assert set(saved["day_comparison"]["teams"]) == {"multi", "single"}
    assert all(not account["trades"] for account in saved["day_comparison"]["teams"].values())
    assert not saved["trades"]


def test_open_cycle_runs_and_persists_both_teams(tmp_path, monkeypatch):
    tr, quotes = _setup(tmp_path, monkeypatch)
    tr.data.quotes = lambda symbols: quotes
    tr.phase = lambda t, q: "open"
    tr.volatility = lambda: REG
    tr.rank.refresh = lambda *args: None
    tr.desk.day.run = lambda *args: None
    tr.desk.growth.run = lambda *args: None
    tr.cfg.opt_enabled = False
    tr.maybe_post_half_hour = lambda *args: None
    assert tr.step() == "open"
    saved = json.loads(tr.store.mirror.read_text())
    assert all(account["trades"] for account in saved["day_comparison"]["teams"].values())
    assert not saved["trades"]


def test_export_contains_separate_comparison_accounts(tmp_path, monkeypatch):
    tr, quotes = _setup(tmp_path, monkeypatch)
    tr.day_comparison.run(quotes, T, REG)
    source, target = tmp_path / "source.json", tmp_path / "test.db"
    source.write_text(json.dumps(tr.s))
    grafana_export.export(source, target)
    with sqlite3.connect(target) as db:
        accounts = db.execute("SELECT team, start_cash, budget_pct FROM comparison_accounts ORDER BY team").fetchall()
        assert accounts == [("multi", 5000.0, tr.cfg.day_pct), ("single", 5000.0, tr.cfg.day_pct)]
        assert db.execute("SELECT COUNT(DISTINCT team) FROM comparison_equity").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM comparison_trades WHERE team='single' AND side='buy'").fetchone()[0] == 1
        dashboard = json.loads((Path(__file__).parents[1] / "grafana/dashboards/paper_trader.json").read_text())
        panels = [p for p in dashboard["panels"] if p["id"] in (47, 48, 49, 50)]
        assert len(panels) == 4
        assert all(db.execute(p["targets"][0]["rawQueryText"]).fetchall() for p in panels)
