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
    tr.desk.growth.run(quotes, T, equity, mandate, REG)
    voo, qqq = (tr.s["positions"][s]["qty"] * 112.0 for s in ("VOO", "QQQ"))
    assert voo > qqq * 2.5
    # a position far above its target weight is trimmed back
    tr.s["positions"]["QQQ"]["qty"] *= 3
    tr.desk.growth.run(quotes, T, equity, mandate, REG)
    assert any(x["side"] == "sell" and x["sym"] == "QQQ" and "rebalance" in x["reason"] for x in tr.s["trades"])


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
