from datetime import datetime
from zoneinfo import ZoneInfo

from agentic_trader import paper_live as pl

ET = ZoneInfo("America/New_York")
T = datetime(2026, 10, 22, 11, 0, tzinfo=ET)
REG = {"name": "normal", "level": 0, "vix": 17.0, "spy_vol20": 0.1, "hedge_target": 0.0, "day_scale": 1.0,
       "spy_below_ma50": False}


class Data:
    def __init__(self, chains=None, earnings=None, bars=None):
        self.chains, self._earn, self._bars = chains or {}, earnings or [], bars or {}

    def earnings(self, days):
        return self._earn

    def option_expirations(self, sym):
        return ["2026-10-30"] if sym in self.chains else []

    def option_contracts(self, sym, exp, kind):
        return [{"id": f"{sym}-{k}", "strike": k, "exp": exp, "type": kind} for k in self.chains[sym]["strikes"]]

    def option_quotes(self, ids):
        out = {}
        for i in ids:
            sym, k = i.rsplit("-", 1)
            bid = self.chains[sym]["bid"](float(k))
            out[i] = {"bid": bid, "ask": bid + 0.02, "mark": bid, "oi": 500, "delta": -0.2}
        return out

    def bars(self, syms, interval, days, **kw):
        return {s: [{"close": self._bars.get(s, 100) + i * 0.1} for i in range(120)] for s in syms}

    def quotes(self, syms):
        return {s: _q(100) for s in syms}


def _q(price):
    return {"price": price, "bid": price * 0.9995, "ask": price * 1.0005, "as_of": T.isoformat(), "session": "regular",
            "prev_close": price, "change_pct": 0.0}


def trader(tmp_path, data, monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, str(v))
    n = type("N", (), {"post": lambda *a, **k: None})()
    return pl.PaperTrader(data, n, pl.Store(mirror=tmp_path / "s.json", storage=False), pl.Cfg(), lambda: T, lambda s: {})


def test_orchestrator_banks_goal_and_never_lifts_caps(tmp_path, monkeypatch):
    tr = trader(tmp_path, Data(), monkeypatch)
    orch = tr.desk.orchestrator
    tr.s["day"]["open_equity"] = tr.s["week"]["open_equity"] = 5000
    behind = orch.plan({}, T, 5005, REG)
    assert behind.mandates["day"].allow_new and behind.mandates["options"].allow_new
    assert behind.mandates["options"].budget_pct == tr.cfg.opt_pct
    hit = orch.plan({}, T, 5000 * (1 + tr.cfg.daily_max + 0.001), REG)
    assert not hit.mandates["day"].allow_new and not hit.mandates["options"].allow_new
    assert hit.stance == "risk-off"
    down = orch.plan({}, T, 4850, REG)
    assert not down.mandates["day"].allow_new and down.mandates["options"].scale == 0.5
    stress = orch.plan({}, T, 5000, {**REG, "name": "high", "day_scale": 0.4})
    assert stress.mandates["options"].scale == 0.4 and stress.mandates["day"].scale == 0.4
    assert tr.s["desk"]["stance"] == "reduced"


def test_options_agent_ranks_skips_earnings_and_stays_secured(tmp_path, monkeypatch):
    chains = {
        "AAA": {"strikes": [9.0, 9.5], "bid": lambda k: 0.10},  # lower yield
        "BBB": {"strikes": [9.0, 9.5], "bid": lambda k: 0.30},  # best yield
        "CCC": {"strikes": [9.0, 9.5], "bid": lambda k: 0.50},  # earnings before expiry
    }
    data = Data(chains, earnings=[{"symbol": "CCC", "report": {"date": "2026-10-27", "timing": "pm"}}])
    tr = trader(tmp_path, data, monkeypatch, PAPER_OPTION_SYMBOLS="AAA,BBB,CCC", PAPER_OPTION_MAX_POSITIONS=1)
    quotes = {s: _q(10) for s in ("AAA", "BBB", "CCC")}
    tr.desk.options.run(quotes, T, tr.equity(quotes), tr.desk.orchestrator.plan(quotes, T, 5000, REG).mandates["options"])
    assert [(o["sym"], o["type"]) for o in tr.s["options"]] == [("BBB", "put")]
    assert not tr.income.naked_violations() and tr.income.collateral() <= tr.s["cash"]
    assert "opened 1 put" in tr.s["desk"]["options_note"]


def test_options_agent_holds_when_orchestrator_says_so(tmp_path, monkeypatch):
    chains = {"AAA": {"strikes": [9.0], "bid": lambda k: 0.30}}
    tr = trader(tmp_path, Data(chains), monkeypatch, PAPER_OPTION_SYMBOLS="AAA")
    tr.s["day"]["open_equity"] = 4000  # day already far above its goal
    plan = tr.desk.orchestrator.plan({}, T, 5000, REG)
    tr.desk.options.run({"AAA": _q(10)}, T, 5000, plan.mandates["options"])
    assert not tr.s["options"] and "no new options" in tr.s["desk"]["options_note"]


def test_growth_agent_buys_to_weights_and_rebalances(tmp_path, monkeypatch):
    tr = trader(tmp_path, Data(), monkeypatch, PAPER_ETFS="VOO,QQQ", PAPER_GROWTH_WEIGHTS="VOO:0.75,QQQ:0.25")
    quotes = {"VOO": _q(112.0), "QQQ": _q(112.0)}
    equity = tr.equity(quotes)
    mandate = tr.desk.orchestrator.plan(quotes, T, equity, REG).mandates["growth"]
    def day_run():
        tr.s["day"].pop("single", None)  # a new trading day
        before = len(tr.s["trades"])
        tr.desk.growth.run(quotes, T, equity, mandate, REG)
        tr.desk.growth.run(quotes, T, equity, mandate, REG)  # same day: must not trade again
        return tr.s["trades"][before:]

    assert len(day_run()) == 1  # exactly one action per day
    for _ in range(4):
        assert len(day_run()) <= 1
    voo, qqq = (tr.s["positions"][s]["qty"] * 112.0 for s in ("VOO", "QQQ"))
    assert voo > qqq * 2.5
    # a position far above its target weight is trimmed back (one trade, on a later day)
    tr.s["positions"]["QQQ"]["qty"] *= 3
    new = day_run()
    assert len(new) == 1 and new[0]["side"] == "sell" and new[0]["sym"] == "QQQ" and "rebalance" in new[0]["reason"]


def test_attribution_and_summary_lines(tmp_path, monkeypatch):
    tr = trader(tmp_path, Data(), monkeypatch)
    tr.s["trades"] += [
        {"ts": T.isoformat(), "side": "sell", "sym": "AAPL", "sleeve": "day", "realized": 5.0, "fee": 0, "qty": 1,
         "px": 1, "value": 1, "reason": "x"},
        {"ts": T.isoformat(), "side": "option", "sym": "NU", "realized": 2.0, "fee": 0, "qty": 1, "px": 0.3,
         "desc": "SELL TO OPEN NU", "reason": "x"},
    ]
    tr.desk.orchestrator.plan({}, T, 5000, REG)
    rows = tr.desk.orchestrator.attribution({}, T)
    assert rows["day"]["today"] == 5.0 and rows["options"]["today"] == 2.0 and rows["growth"]["today"] == 0.0
    text = "\n".join(tr.desk_lines({}, 5000, T))
    assert "Orchestrator" in text and "Options agent" in text and "Growth agent" in text and "Day agent" in text


def test_options_manager_splits_agents_by_delta_and_tags_trades(tmp_path, monkeypatch):
    chains = {"AAA": {"strikes": [9.0], "bid": lambda k: 0.30}, "BBB": {"strikes": [9.0], "bid": lambda k: 0.30}}
    tr = trader(tmp_path, Data(chains), monkeypatch, PAPER_OPTION_SYMBOLS="AAA,BBB", PAPER_OPTION_MAX_POSITIONS=3)
    quotes = {s: _q(10) for s in ("AAA", "BBB")}
    tr.desk.options.run(quotes, T, tr.equity(quotes), tr.desk.orchestrator.plan(quotes, T, 5000, REG).mandates["options"])
    # fake delta is 0.2: only the yield agent's 0.15-0.35 band accepts it; the defensive agent (<=0.15) does not
    assert {o["strat"] for o in tr.s["options"]} == {"yield_puts"}
    rep = tr.s["desk"]["options_agents"]
    assert set(rep) == {"yield_puts", "defensive_puts", "vrp_puts", "put_spreads", "covered_calls"} and rep["yield_puts"]["open"] == len(tr.s["options"])
    assert all(x.get("strat") == "yield_puts" for x in tr.s["trades"] if x["side"] == "option")
    assert not tr.income.naked_violations()


def _snap(**kw):
    m = dict(price=100.0, vwap=99.5, ema9=100.0, ema21=99.0, rsi=60, rsi_prev=58, atr5=0.3, atr5_pct=0.003,
             daily_atr_pct=0.025, or_high=99.8, or_low=98.5, or_done=True, rvol=1.5, last_close=100.0,
             last_low=99.7, day_open=99.0, day_high=100.0, day_low=98.5, daily_ma20=98.0, daily_ma50=95.0,
             prev_close=98.8, above_vwap_share=0.8)
    m.update(kw)
    return m


def test_day_team_agents_run_own_strategy_inside_shared_budget(tmp_path, monkeypatch):
    tr = trader(tmp_path, Data(), monkeypatch, PAPER_DAY_SYMBOLS="AAA,BBB,CCC,DDD")
    spy = _snap(price=500, vwap=499)
    snaps = {"SPY": spy, "AAA": _snap(), "BBB": _snap(), "CCC": _snap(), "DDD": _snap()}
    monkeypatch.setattr(type(tr.desk.day), "_snapshots", lambda self, q, t: snaps)
    quotes = {s: _q(100) for s in snaps}
    equity = tr.equity(quotes)
    mandate = tr.desk.orchestrator.plan(quotes, T, equity, REG).mandates["day"]
    tr.desk.day.run(quotes, T, equity, mandate, REG, (11, 0))
    held = tr.s["positions"]
    strats = [p["strat"] for p in held.values()]
    assert len(strats) == len(set(strats)) >= 2  # each agent holds at most one position, each with its own strategy
    assert all(p["stop_px"] < 100 for p in held.values())  # every entry carries a stop
    deployed = sum(p["qty"] * 100 for p in held.values())
    assert deployed <= equity * tr.cfg.day_pct * 1.01
    rep = tr.s["desk"]["day_agents"]
    assert set(rep) == {"ORB", "PULLBACK", "MOMENTUM", "REVERSION"}
    assert all(x.get("strat") for x in tr.s["trades"] if x["side"] == "buy")


def test_reversion_is_independent_of_trend_strategies():
    from agentic_trader import day_strategy as ds
    c = pl.Cfg()
    dip = _snap(price=98.9, vwap=99.8, ema9=99.2, ema21=99.6, rsi=36, rsi_prev=30, day_low=98.7, last_low=98.7,
                last_close=98.95)
    assert ds.reversion(dip, c)[0][0] == "REVERSION"
    assert ds.orb(dip, c)[0] is None and ds.momentum(dip, c)[0] is None


def test_quant_veto_blocks_puts_and_is_reported(tmp_path, monkeypatch):
    from agentic_trader.options_agents import YieldPuts
    chains = {"F": {"strikes": [9.0, 9.5], "bid": lambda k: 0.05}}
    tr = trader(tmp_path, Data(chains=chains), monkeypatch, PAPER_OPTION_SYMBOLS="F")
    quotes = {"F": _q(10)}
    tr.quant.ensure(["F"], "options")
    assert (tmp_path / "quant_suite.json").exists()  # persisted next to the state file, not the real one
    tr.quant.cache[("options", "F")][1].update(veto=True, score=-0.7)
    assert "quant veto" in YieldPuts(tr).run(quotes, T, 5000, 2000, 2000)["note"]
    assert tr.quant.verdict("F", "options")[0] is True
    assert any("Quant gate" in line for line in tr.quant.lines(tr.s))


def test_day_team_skips_quant_vetoed_names_and_logs_quant_note(tmp_path, monkeypatch):
    tr = trader(tmp_path, Data(), monkeypatch, PAPER_DAY_SYMBOLS="AAA,BBB")
    snaps = {"SPY": _snap(price=500, vwap=499), "AAA": _snap(), "BBB": _snap()}
    monkeypatch.setattr(type(tr.desk.day), "_snapshots", lambda self, q, t: snaps)
    quotes = {s: _q(100) for s in snaps}
    tr.quant.ensure(["AAA", "BBB"], "day")
    tr.quant.cache[("day", "AAA")][1].update(veto=True, score=-0.8)
    equity = tr.equity(quotes)
    mandate = tr.desk.orchestrator.plan(quotes, T, equity, REG).mandates["day"]
    tr.desk.day.run(quotes, T, equity, mandate, REG, (11, 0))
    assert "AAA" not in tr.s["positions"] and "BBB" in tr.s["positions"]
    assert "quant" in next(x for x in tr.s["trades"] if x["sym"] == "BBB")["reason"]


def test_puts_skip_tiny_credits_and_recent_stopouts(tmp_path, monkeypatch):
    from agentic_trader.options_agents import YieldPuts
    tr = trader(tmp_path, Data(chains={"F": {"strikes": [9.0, 9.5], "bid": lambda k: 0.06}}), monkeypatch,
                PAPER_OPTION_SYMBOLS="F", PAPER_QUANT_GATE="0")
    quotes = {"F": _q(10)}
    assert YieldPuts(tr).run(quotes, T, 5000, 2000, 2000)["opened"] == 0  # $0.06 is under the $0.10 credit floor

    tr = trader(tmp_path, Data(chains={"F": {"strikes": [9.0, 9.5], "bid": lambda k: 0.30}}), monkeypatch,
                PAPER_OPTION_SYMBOLS="F", PAPER_QUANT_GATE="0")
    tr.s["opt_stopouts"] = {"F": "2026-10-21"}
    note = YieldPuts(tr).run(quotes, T, 5000, 2000, 2000)
    assert note["opened"] == 0 and "cooling down" in note["note"]
    tr.s["opt_stopouts"] = {"F": "2026-10-15"}
    tr.s.pop("opt_scan_yield_puts", None)
    assert YieldPuts(tr).run(quotes, T, 5000, 2000, 2000)["opened"] == 1


def test_puts_judge_drops_relative_to_the_market_and_share_idle_budget(tmp_path, monkeypatch):
    from agentic_trader.options_agents import YieldPuts
    chains = {"F": {"strikes": [9.0, 9.5], "bid": lambda k: 0.30}}

    def scan(spy_chg, stock_chg, slice_, team=0.0):
        tr = trader(tmp_path, Data(chains=chains), monkeypatch, PAPER_OPTION_SYMBOLS="F", PAPER_QUANT_GATE="0")
        quotes = {"F": dict(_q(10), change_pct=stock_chg), "SPY": dict(_q(500), change_pct=spy_chg)}
        return YieldPuts(tr).run(quotes, T, 5000, slice_, 2000, team)

    assert scan(0.0, -0.035, 2000)["opened"] == 0            # idiosyncratic drop: still skipped
    assert scan(-0.03, -0.035, 2000)["opened"] == 1          # market-wide drop: not a falling knife
    assert scan(-0.03, -0.08, 2000)["opened"] == 0           # far worse than the market: skipped
    assert scan(0.0, 0.0, 500)["opened"] == 0                # $900 collateral does not fit a $500 slice
    assert scan(0.0, 0.0, 500, team=2000)["opened"] == 1     # but fits half of the team budget
