"""CLI: python -m agentic_trader <command>"""
from __future__ import annotations

import argparse
import json

from . import compute
from .config import Settings


def main() -> None:
    ap = argparse.ArgumentParser(prog="agentic_trader", description="Paper-trading agentic bot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sim = sub.add_parser("simulate", help="replay one mock session (fast) incl. Discord summaries")
    sim.add_argument("--ticks", type=int, default=None)
    sim.add_argument("--delay", type=float, default=0.0)
    sim.add_argument("--shock", type=float, default=None, help="inject a SPY move (e.g. -0.02) mid-session")
    sub.add_parser("run", help="live loop on the configured provider during market hours")
    imp = sub.add_parser("improve", help="retrain regression gate + parameter sweep")
    imp.add_argument("--dry-run", action="store_true")
    sub.add_parser("rebalance", help="force an ETF sleeve rebalance now")
    sub.add_parser("discord-test", help="post test messages to the realtime and updates channels")
    sub.add_parser("status", help="show paper account")
    pl = sub.add_parser("paper-live", help="internal paper trading on live Robinhood data; Discord summaries")
    pl.add_argument("--once", action="store_true", help="run a single cycle and exit")
    pl.add_argument("--status", action="store_true", help="print stored paper account and exit")
    pl.add_argument("--reset", action="store_true", help="discard stored paper account and restart at start cash")
    rl = sub.add_parser("rh-login", help="sign in to Robinhood MCP in your browser (OAuth); saves tokens to .env")
    rl.add_argument("--manual", action="store_true", help="browser is on another machine: paste the redirect URL back")
    rr = sub.add_parser("rh-research", help="live quote + analyst consensus + earnings for symbols (read-only)")
    rr.add_argument("symbols", nargs="+")
    rq = sub.add_parser("rh-quant", help="live-quote quant metrics + prediction scorecard; pushes to gaming PC if online")
    rq.add_argument("symbols", nargs="+")
    sub.add_parser("rh-tools", help="list Robinhood MCP tools (read-only, no calls)")
    rc = sub.add_parser("rh-call", help="call ONE allow-listed read-only Robinhood tool")
    rc.add_argument("tool")
    rc.add_argument("--args", default="{}", help="JSON arguments")
    a = ap.parse_args()
    s = Settings.from_env()

    if a.cmd == "paper-live":
        from . import paper_live
        if a.status:
            print(paper_live.status_text())
            return
        bot = paper_live.build()
        if a.reset:
            bot.s = paper_live.new_state(bot.cfg, bot.clock())
            bot.store.save(bot.s)
        print(bot.step()) if a.once else bot.run_forever()
        return

    if a.cmd == "rh-quant":
        from . import gaming_pc
        res = gaming_pc.quant(a.symbols)
        for sym, m in res["local"].items():
            sc = m.get("scorecard", {})
            print(f"{sym}: px {m.get('price')} score {m.get('signal_score', 0):+.2f} rsi {m.get('rsi14') or 0:.0f} "
                  f"bb_z {m.get('bb_z', 0):+.2f} vwap {m.get('vwap_dev_pct', 0):+.2%} vol {m.get('realized_vol_ann', 0):.0%} "
                  f"beta {m.get('beta_vs_spy') or 0:.2f} | OOS IC {sc.get('ic', 0):+.3f} hit {sc.get('hit_rate', 0):.1%} "
                  f"rmse/naive {sc.get('rmse_vs_naive') or 0:.3f}" if "error" not in m else f"{sym}: {m['error']}")
        g = res["gaming_pc"]
        print("gaming PC:", g["status"], f"({len(g.get('results', []))} results)", g.get("error") or "")
        return
    if a.cmd == "rh-research":
        from .robinhood.research import describe, snapshot
        for sym, snap in snapshot(a.symbols).items():
            print(describe(sym, snap))
        return
    if a.cmd.startswith("rh-"):
        from .robinhood import oauth
        from .robinhood.mcp_client import RobinhoodMCP
        if a.cmd == "rh-login":
            oauth.login(open_browser=not a.manual, manual=a.manual)
            return
        c = RobinhoodMCP(allow={a.tool} if a.cmd == "rh-call" else None)
        info = c.initialize()
        if a.cmd == "rh-tools":
            print("server:", info.get("serverInfo"))
            for t in c.list_tools():
                from .robinhood.mcp_client import SAFE_TOOLS
                flag = "" if t["name"] in SAFE_TOOLS else " [not callable]"
                print(f"- {t['name']}{flag}: {(t.get('description') or '')[:120]}\n    schema: {json.dumps(t.get('inputSchema', {}).get('properties', {}))[:300]}")
        else:
            print(json.dumps(c.call(a.tool, json.loads(a.args)), indent=1)[:6000])
        return

    if a.cmd == "improve":
        from . import improve
        print(json.dumps(improve.run(s, dry_run=a.dry_run), indent=1, default=str))
        return
    if a.cmd == "discord-test":
        from .notify.discord import DiscordNotifier
        n = DiscordNotifier(s)
        print("live" if n.live else "dry-run (no DISCORD_BOT_TOKEN)", "| compute:", compute.BACKEND)
        n.post("realtime", "🧪 Agentic_Trader test: realtime channel OK")
        n.post("updates", "🧪 Agentic_Trader test: daily-updates channel OK")
        return

    from .engine import Engine
    e = Engine(s)
    if a.cmd == "simulate":
        if a.shock is not None and hasattr(e.provider, "inject_shock"):
            e.provider.cursor += 120
            e.provider.inject_shock("SPY", a.shock)
        e.run_simulation(a.ticks, a.delay)
    elif a.cmd == "run":
        e.run_live()
    elif a.cmd == "rebalance":
        px = e.prices()
        e.rebalance_etf(e.provider.now(), px, force=True)
    status = {"cash": round(e.broker.cash, 2), "equity": round(e.equity(e.prices()), 2),
              "positions": e.broker.positions, "realized": e.broker.realized}
    print(json.dumps(status, indent=1))


if __name__ == "__main__":
    main()
