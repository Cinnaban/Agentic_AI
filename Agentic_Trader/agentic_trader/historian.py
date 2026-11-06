"""Desk historian: summarizes the previous trading day, the trailing week and the longer history for the orchestrator,
which hands each team its own briefing as context when it reviews and places trades.

Deterministic and paper-only: it reads the closed-trade log, so every number can be traced to trades. A briefing never
creates a trade. Teams use it in two ways:
  - avoid:   a symbol (or strategy/symbol pair) with enough recent closed trades, a net loss and a low win rate is
             skipped, and the skip is reported;
  - favored: a symbol with enough recent closed trades, a net gain and a high win rate gets a small ranking bonus.
Small samples are noisy, so the thresholds need `min_trades` closed trades inside the window and the briefing says so
when a team has too little history to learn from.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

TEAMS = ("growth", "options", "day")
TEAM_LABELS = {"growth": "Growth", "options": "Options", "day": "Day"}
HISTORY_DAYS = 90
THIN_HISTORY = 5  # closed trades a team needs before its history means anything


def _stats(rows):
    """rows: [(sym, strat, realized)] -> summary dict."""
    n = len(rows)
    if not n:
        return {"closed": 0, "net": 0.0, "wins": 0, "win_rate": None, "profit_factor": None, "best": None, "worst": None}
    net = sum(r for _, _, r in rows)
    wins = sum(1 for _, _, r in rows if r > 0)
    gain, loss = sum(r for _, _, r in rows if r > 0), -sum(r for _, _, r in rows if r < 0)
    best, worst = max(rows, key=lambda x: x[2]), min(rows, key=lambda x: x[2])
    return {"closed": n, "net": round(net, 2), "wins": wins, "win_rate": wins / n,
            "profit_factor": (gain / loss) if loss else None,
            "best": [best[0], round(best[2], 2)] if best[2] > 0 else None,
            "worst": [worst[0], round(worst[2], 2)] if worst[2] < 0 else None}


def _money(v):
    return f"{'-' if v < 0 else '+'}${abs(v):,.2f}"


def _phrase(label, st):
    if not st["closed"]:
        return f"{label}: no closed trades"
    text = f"{label}: {st['closed']} closed, net {_money(st['net'])}, win rate {st['win_rate']:.0%}"
    if st["best"]:
        text += f", best {st['best'][0]} {_money(st['best'][1])}"
    if st["worst"]:
        text += f", worst {st['worst'][0]} {_money(st['worst'][1])}"
    return text


class Historian:
    def __init__(self, cfg):
        self.cfg = cfg
        self._key = None
        self._cached = None

    def build(self, trades, t, agent_of, equity, bench=None):
        """Briefing for the orchestrator: {"teams": {team: {...}}, "lines": [...], "market": {...}, "ts": ...}."""
        key = (len(trades), t.date().isoformat(), t.hour, t.minute // 15)
        if key == self._key and self._cached:
            return self._cached
        today = t.date().isoformat()
        window_start = (t - timedelta(days=self.cfg.brief_days)).isoformat()
        hist_start = (t - timedelta(days=HISTORY_DAYS)).isoformat()
        week_start = (t - timedelta(days=7)).date().isoformat()

        rows = []  # (day, team, strat, sym, realized)
        for x in trades:
            if "realized" not in x:
                continue
            team = agent_of(x)
            if team in TEAMS:
                rows.append((x["ts"][:10], x["ts"], team, x.get("strat") or "", x["sym"], x["realized"]))
        days = sorted({r[0] for r in rows if r[0] < today})
        last_day = days[-1] if days else None

        def pick(team, pred):
            return [(r[4], r[3], r[5]) for r in rows if r[2] == team and pred(r)]

        teams = {}
        for team in TEAMS:
            yday = _stats(pick(team, lambda r: r[0] == last_day))
            week = _stats(pick(team, lambda r: week_start <= r[0] < today))
            hist = _stats(pick(team, lambda r: r[1] >= hist_start))
            avoid, favored, avoid_strat, favored_strat = {}, {}, {}, {}
            recent = pick(team, lambda r: r[1] >= window_start)
            by_sym, by_pair = defaultdict(list), defaultdict(list)
            for sym, strat, real in recent:
                by_sym[sym].append((sym, strat, real))
                if strat:
                    by_pair[f"{strat}|{sym}"].append((sym, strat, real))
            for target_avoid, target_fav, groups in ((avoid, favored, by_sym), (avoid_strat, favored_strat, by_pair)):
                for name, grp in groups.items():
                    st = _stats(grp)
                    if st["closed"] < self.cfg.brief_min_trades:
                        continue
                    why = f"{st['closed']} closed in {self.cfg.brief_days}d, net {_money(st['net'])}, win rate {st['win_rate']:.0%}"
                    if st["net"] < -0.002 * equity and st["win_rate"] <= 0.34:
                        target_avoid[name] = why
                    elif st["net"] > 0 and st["win_rate"] >= 0.60:
                        target_fav[name] = why
            strategies = {}
            for strat in sorted({r[3] for r in rows if r[2] == team and r[3] and r[1] >= hist_start}):
                strategies[strat] = _stats(pick(team, lambda r, s=strat: r[3] == s and r[1] >= hist_start))
            lines = [_phrase(f"Yesterday ({last_day})" if last_day else "Yesterday", yday),
                     _phrase("Last 7 days", week), _phrase(f"History ({HISTORY_DAYS}d)", hist)]
            if hist["closed"] < THIN_HISTORY:
                lines.append(f"history is thin ({hist['closed']} closed trades): treat the numbers as anecdotes")
            if avoid or avoid_strat:
                lines.append("avoiding: " + "; ".join(f"{k.replace('|', ' ')} ({v})" for k, v in {**avoid, **avoid_strat}.items()))
            if favored or favored_strat:
                lines.append("favoring: " + "; ".join(f"{k.replace('|', ' ')} ({v})" for k, v in {**favored, **favored_strat}.items()))
            teams[team] = {"label": TEAM_LABELS[team], "yesterday": yday, "week": week, "history": hist,
                           "strategies": strategies, "avoid": avoid, "favored": favored,
                           "avoid_strat": avoid_strat, "favored_strat": favored_strat, "lines": lines}

        market = self._market(bench or {}, t)
        out = {"ts": t.isoformat(), "last_day": last_day, "market": market, "teams": teams,
               "lines": ([market["line"]] if market.get("line") else [])}
        self._key, self._cached = key, out
        return out

    @staticmethod
    def _market(bench, t):
        """SPY move over the previous session and the trailing week, from the recorded daily closes."""
        today = t.date().isoformat()
        days = sorted(d for d in bench if d < today)
        if len(days) < 2:
            return {}
        last, prev = bench[days[-1]], bench[days[-2]]
        week_ref = next((bench[d] for d in days if d >= (t - timedelta(days=8)).date().isoformat()), None)
        res = {"spy_yesterday_pct": (last / prev - 1) * 100 if prev else None,
               "spy_week_pct": (last / week_ref - 1) * 100 if week_ref else None}
        parts = []
        if res["spy_yesterday_pct"] is not None:
            parts.append(f"SPY {days[-1]} {res['spy_yesterday_pct']:+.2f}%")
        if res["spy_week_pct"] is not None:
            parts.append(f"SPY over the week {res['spy_week_pct']:+.2f}%")
        res["line"] = "Market: " + ", ".join(parts) if parts else ""
        return res


def briefing_lines(brief):
    """Discord/summary block for the daily report."""
    if not brief or not brief.get("teams"):
        return []
    out = ["", "Desk briefing (historian -> orchestrator -> teams):"] + [f"- {x}" for x in brief.get("lines", [])]
    for team in TEAMS:
        info = brief["teams"].get(team)
        if info:
            out.append(f"- {info['label']} team")
            out += [f"  - {x}" for x in info["lines"]]
    return out
