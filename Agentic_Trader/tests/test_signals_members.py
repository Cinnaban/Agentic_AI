from agentic_trader.growth_members import members
from agentic_trader.market_signals import MarketSignals, score_feed
from tests.test_desk import Data, REG, T, _q, trader


def _article(sym, score, rel=0.9):
    return {"ticker_sentiment": [{"ticker": sym, "relevance_score": str(rel), "ticker_sentiment_score": str(score)}]}


class FakeAV:
    daily_limit = 25

    def __init__(self, used=0, feed=None):
        self.used, self.feed, self.calls = used, feed or [], []

    def configured(self):
        return True

    def used_today(self):
        return self.used

    def call(self, function, ttl=None, **params):
        self.calls.append((function, params))
        return {"feed": self.feed}

    def economic(self, function, interval=None):
        return {"rows": [{"date": "2026-10-01", "value": "3.5"}]}


def test_score_feed_weights_by_relevance_and_ignores_irrelevant():
    feed = [_article("AAA", -0.6), _article("AAA", -0.4), _article("AAA", -0.5), _article("BBB", 0.9, rel=0.05)]
    out = score_feed(feed, ["AAA", "BBB"])
    assert round(out["AAA"]["score"], 2) == -0.5 and out["AAA"]["n"] == 3 and "BBB" not in out


def test_bearish_needs_enough_articles_and_groups_merge(monkeypatch):
    monkeypatch.setenv("PAPER_NEWS_SIGNAL", "1")
    av = FakeAV(feed=[_article("AAA", -0.6)] * 3 + [_article("BBB", -0.6)])
    ms = MarketSignals(av=av, enabled=True)
    ms.refresh(["AAA"], "growth")
    ms.refresh(["BBB"], "day")
    ms.refresh(["AAA"], "growth")  # inside the ttl: no third call
    assert len(av.calls) == 2 and ms.bearish("AAA") and not ms.bearish("BBB")


def test_budget_reserve_and_disabled_fail_open(monkeypatch):
    monkeypatch.setenv("PAPER_NEWS_SIGNAL", "1")
    av = FakeAV(used=20, feed=[_article("AAA", -0.9)] * 3)
    ms = MarketSignals(av=av, enabled=True)
    ms.refresh(["AAA"])
    assert not av.calls and not ms.bearish("AAA")
    off = MarketSignals(av=FakeAV(), enabled=False)
    off.refresh(["AAA"])
    assert not off.bearish("AAA") and off.cash_rate() == 0.04
    assert MarketSignals(av=FakeAV(), enabled=True).cash_rate() == 0.035


def _closes(start, end, n=300):
    return [start + (end - start) * i / (n - 1) for i in range(n)]


def test_growth_members_flag_a_falling_etf_and_prefer_the_rising_one():
    closes = {"UP": _closes(100, 150), "DOWN": _closes(150, 100), "FLAT": _closes(100, 101)}
    m = members(closes, {s: c[-1] for s, c in closes.items()}, 0.04)
    assert m["UP"]["score"] > m["FLAT"]["score"] > m["DOWN"]["score"]
    assert m["DOWN"]["bearish"] and not m["UP"]["bearish"] and m["UP"]["above200"]
    assert members({"X": _closes(1, 2, 100)}, {}, 0.04) == {}


def test_day_desk_skips_symbols_reporting_earnings_today(tmp_path, monkeypatch):
    earn = [{"symbol": "AAA", "report": {"date": T.date().isoformat(), "timing": "pm"}}]
    tr = trader(tmp_path, Data(earnings=earn), monkeypatch)
    assert tr.desk.day._earnings_today(T) == {"AAA"}
    monkeypatch.setattr(tr.cfg, "skip_earnings_day", False)
    tr.desk.day._earn = None
    assert tr.desk.day._earnings_today(T) == set()


def test_vrp_agent_needs_a_vol_premium_and_news_veto(tmp_path, monkeypatch):
    chains = {"AAA": {"strikes": [9.0], "bid": lambda k: 0.30}}
    tr = trader(tmp_path, Data(chains), monkeypatch, PAPER_OPTION_SYMBOLS="AAA", PAPER_OPTION_MAX_POSITIONS=3)
    agent = next(a for a in tr.desk.options.agents if a.name == "vrp_puts")
    monkeypatch.setattr(tr.quant, "get", lambda sym, mode: {"rv_ann": 0.4, "rv_recent_ann": 0.2})
    assert round(agent._vrp("AAA", 0.45), 2) == 1.5 and agent._vrp("AAA", None) is None
    assert agent.MIN_VRP == 1.15 and agent.DELTA_RANGE == (0.10, 0.25)
    quotes = {"AAA": _q(10)}
    tr.signals.news["AAA"] = {"score": -0.6, "n": 5}
    tr.desk.options.run(quotes, T, tr.equity(quotes), tr.desk.orchestrator.plan(quotes, T, 5000, REG).mandates["options"])
    assert not tr.s["options"]
