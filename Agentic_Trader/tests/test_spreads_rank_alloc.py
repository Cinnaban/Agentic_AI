from datetime import timedelta

import numpy as np
import pytest

from agentic_trader import signal_research as sr
from agentic_trader.paper_options import UnlimitedRiskRefused, max_loss
from tests.test_desk import Data, REG, T, _q, trader


def _spread_trader(tmp_path, monkeypatch):
    chains = {"AAA": {"strikes": [9.0, 8.0], "bid": lambda k: 0.50 if k == 9.0 else 0.10}}
    return trader(tmp_path, Data(chains), monkeypatch, PAPER_OPTION_SYMBOLS="AAA", PAPER_OPTION_MAX_POSITIONS=3)


def test_put_spread_agent_opens_capped_loss_spread(tmp_path, monkeypatch):
    tr = _spread_trader(tmp_path, monkeypatch)
    quotes = {"AAA": _q(10)}
    mandate = tr.desk.orchestrator.plan(quotes, T, 5000, REG).mandates["options"]
    tr.desk.options.run(quotes, T, tr.equity(quotes), mandate)
    spreads = [o for o in tr.s["options"] if o.get("kind") == "put_credit_spread"]
    assert len(spreads) == 1 and spreads[0]["strat"] == "put_spreads"
    o = spreads[0]
    assert o["long_strike"] == 8.0 and o["credit"] == pytest.approx(0.38)
    assert max_loss(o) == pytest.approx((1.0 - 0.38) * 100)  # (width - credit) x 100: finite and small
    assert tr.income.collateral() == 100  # secured by the width, not the full strike
    assert not tr.income.naked_violations()


def test_spread_requires_long_leg_and_settles_in_cash(tmp_path, monkeypatch):
    tr = _spread_trader(tmp_path, monkeypatch)
    inc, d = tr.income, tr.data
    sh, lo = d.option_contracts("AAA", "2026-10-30", "put")
    qs = d.option_quotes([sh["id"], lo["id"]])
    with pytest.raises(UnlimitedRiskRefused):
        inc.sell_credit_spread("AAA", lo, qs[lo["id"]], sh, qs[sh["id"]], 1, T)  # long leg above the short: refused
    assert inc.sell_credit_spread("AAA", sh, qs[sh["id"]], lo, qs[lo["id"]], 1, T, strat="put_spreads")
    cash = tr.s["cash"]
    inc.settle(inc.opts[0], 7.0, T)  # below both strikes: loses the full width, no shares assigned
    assert not inc.opts and "AAA" not in tr.s["positions"]
    assert tr.s["cash"] == pytest.approx(cash - 100)
    assert tr.s["trades"][-1]["realized"] == pytest.approx((0.38 - 1.0) * 100 - 0.0 - tr.s["trades"][-2]["fee"])


def test_removed_long_leg_is_a_violation(tmp_path, monkeypatch):
    tr = _spread_trader(tmp_path, monkeypatch)
    sh, lo = tr.data.option_contracts("AAA", "2026-10-30", "put")
    qs = tr.data.option_quotes([sh["id"], lo["id"]])
    tr.income.sell_credit_spread("AAA", sh, qs[sh["id"]], lo, qs[lo["id"]], 1, T)
    tr.income.opts[0].pop("long_id")
    assert tr.income.naked_violations()


def _series(n=900, drift=0.0004, seed=1):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(drift, 0.015, n)))
    return [{"open": x * 0.999, "high": x * 1.01, "low": x * 0.99, "close": x, "volume": 1e6} for x in c]


def test_research_is_time_split_and_unconfirmed_get_no_weight():
    data = {s: _series(seed=i) for i, s in enumerate(["SPY"] + [f"S{i}" for i in range(14)])}
    res = sr.run(data)
    assert res["tested"] > 50 and res["train_frac"] == 0.6
    ranks = [r["rank"] for r in res["ranking"]]
    assert ranks == sorted(ranks)
    assert all(r["confirmed"] and r["holdout"]["excess_bp"] > 0 for r in res["confirmed_list"])
    assert all(("weight" in r) == (r["tier"] != "none") for r in res["ranking"])
    assert all(r["holdout"]["excess_bp"] > 0 for r in res["priority_list"])


def test_rank_score_uses_only_confirmed_conditions(tmp_path):
    rk = sr.SignalRank(path=tmp_path / "r.json")
    assert rk.score(_series()) == (0.0, [])  # nothing confirmed: neutral
    rk.w = {"Trend>SMA50": 0.5}
    bars = _series(drift=0.002)
    score, hit = rk.score(bars)
    assert score in (0.0, 0.5) and (hit == ["Trend>SMA50"]) == (score == 0.5)


def test_weekly_review_shifts_budget_within_bounds(tmp_path, monkeypatch):
    tr = trader(tmp_path, Data(), monkeypatch)
    orch = tr.desk.orchestrator
    tr.s["day"]["open_equity"] = tr.s["week"]["open_equity"] = 5000
    tr.s["trades"] += [
        {"ts": (T - timedelta(days=1)).isoformat(), "side": "sell", "sym": "AAPL", "sleeve": "day", "realized": 40.0,
         "fee": 0, "qty": 1, "px": 1, "value": 1, "reason": "x"},
        {"ts": (T - timedelta(days=1)).isoformat(), "side": "sell", "sym": "SPY", "sleeve": "core", "realized": -30.0,
         "fee": 0, "qty": 1, "px": 1, "value": 1, "reason": "x"},
    ]
    base = dict(orch.base)
    plan = orch.plan({}, T, 5000, REG)
    mult = tr.s["alloc"]["mult"]
    assert mult["day"] > 1.0 and mult["growth"] < 1.0 and mult["options"] == 1.0  # options had no activity
    assert plan.mandates["day"].budget_pct == pytest.approx(min(0.40, base["day"] * mult["day"]))
    assert any("weekly review" in n for n in plan.notes)
    orch.plan({}, T + timedelta(days=1), 5000, REG)  # reviewed once a week, not every cycle
    assert tr.s["alloc"]["mult"]["day"] == mult["day"]
    for _ in range(30):  # repeated weeks can never leave the floor/ceiling band
        tr.s["alloc"]["ts"] = (T - timedelta(days=8)).isoformat()
        orch.plan({}, T, 5000, REG)
    assert 0.1 <= tr.s["alloc"]["mult"]["growth"] and tr.s["alloc"]["mult"]["day"] <= 1.5
    assert orch.budgets()["day"] <= 0.40


def test_team_that_loses_its_budget_gets_a_smaller_allocation(tmp_path, monkeypatch):
    tr = trader(tmp_path, Data(), monkeypatch)
    orch = tr.desk.orchestrator
    tr.s["day"]["open_equity"] = tr.s["week"]["open_equity"] = 5000
    budget = 5000 * orch.base["options"]
    tr.s["trades"].append({"ts": (T - timedelta(days=1)).isoformat(), "side": "option", "sym": "F", "sleeve": "income",
                           "strat": "yield_puts", "realized": -budget, "fee": 0, "qty": 1, "px": 1, "value": 1,
                           "reason": "x"})
    orch.plan({}, T, 5000, REG)
    assert tr.s["alloc"]["mult"]["options"] == pytest.approx(0.5)  # lost 100% of budget: cut by MAX_CUT


def test_structure_strategies_fire_only_on_their_setup():
    from agentic_trader import day_strategy as ds, paper_live as pl
    from tests.test_desk import _snap
    cfg = pl.Cfg()
    plain = _snap(retest=None, sweep=None, fvg=None, gap_pct=0.0)
    for fn in (ds.retest, ds.sweep, ds.fvg, ds.gapgo):
        assert fn(plain, cfg)[0] is None
    assert ds.retest(_snap(retest=99.5, last_close=100.0, ema9=99.6), cfg)[0][0] == "RETEST"
    assert ds.fvg(_snap(fvg=(99.0, 99.8), last_low=99.7, last_close=100.0, ema9=99.5), cfg)[0][0] == "FVG"
    assert ds.gapgo(_snap(gap_pct=0.03, rvol=3.0, last_close=100.5, or_high=100.0), cfg)[0][0] == "GAPGO"
    assert ds.gapgo(_snap(gap_pct=0.001, rvol=3.0), cfg)[0] is None
