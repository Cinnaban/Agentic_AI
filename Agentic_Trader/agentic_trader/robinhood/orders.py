"""Guarded order flow for Telegram: propose -> review -> explicit /confirm -> place.

Guards: single agentic account (resolved server-side), equities only (no options/crypto/margin), buy/sell with
market or limit, regular hours, gfd, per-order and per-day USD caps, buys limited to unleveraged buying power,
sells limited to shares held, Robinhood in-app approval must be ON, ROBINHOOD_LIVE_ORDERS must be 'true' to place,
one-time confirm code bound to the requesting Telegram user and expiring in 120s.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import threading
import time
import uuid
from datetime import date
from pathlib import Path

from . import account

STATE = Path(__file__).resolve().parents[2] / "state"
TTL = 120
_pending: dict[str, dict] = {}
_lock = threading.Lock()

ORDER_RE = re.compile(
    r"^/?(buy|sell)\s+\$?([A-Za-z]{1,5})\s+(\$?\d+(?:\.\d+)?)(?:\s*@\s*\$?(\d+(?:\.\d+)?))?\s*$", re.I)


def _cap(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def live_enabled() -> bool:
    return os.getenv("ROBINHOOD_LIVE_ORDERS", "false").strip().lower() == "true"


def _spent_today() -> float:
    try:
        d = json.loads((STATE / "rh_daily.json").read_text())
        return float(d["spent"]) if d["date"] == str(date.today()) else 0.0
    except Exception:
        return 0.0


def _record(usd: float):
    STATE.mkdir(exist_ok=True)
    (STATE / "rh_daily.json").write_text(json.dumps({"date": str(date.today()), "spent": _spent_today() + usd}))


def _audit(event: dict):
    STATE.mkdir(exist_ok=True)
    with (STATE / "rh_orders_audit.jsonl").open("a") as f:
        f.write(json.dumps({"ts": time.time(), **event}) + "\n")


def propose(text: str, user_id) -> str:
    m = ORDER_RE.match(text.strip())
    if not m:
        return "Usage: /buy NVDA $5  |  /buy NVDA 0.02  |  /buy NVDA 0.02 @ 215.50  |  /sell NVDA 0.02 (market or limit, equities only)"
    side, sym, amt, limit = m.group(1).lower(), m.group(2).upper(), m.group(3), m.group(4)
    dollars = amt.startswith("$")
    if dollars and (side == "sell" or limit):
        return "Dollar amounts work only for market buys. Use a share quantity for sells and limit orders."
    acct = account.agentic_account()
    no = acct["account_number"]
    args = {"account_number": no, "symbol": sym, "side": side, "type": "limit" if limit else "market",
            "time_in_force": "gfd", "market_hours": "regular_hours"}
    args["dollar_amount" if dollars else "quantity"] = amt.lstrip("$")
    if limit:
        args["limit_price"] = limit
    review = account.review_order(args)
    if review.get("order_checks"):
        return f"Robinhood flagged this order, not proposing it:\n{json.dumps(review['order_checks'])[:600]}"
    q = review.get("quote_data") or {}
    ask, bid = float(q.get("ask_price") or 0), float(q.get("bid_price") or 0)
    px = float(limit) if limit else (ask if side == "buy" else bid)
    est = float(amt.lstrip("$")) if dollars else float(amt) * px
    pf = account.portfolio(no)
    bp = float((pf.get("buying_power") or {}).get("unleveraged_buying_power") or 0)
    if side == "buy":
        if est > bp + 1e-9:
            return f"Blocked: est. ${est:,.2f} exceeds unleveraged buying power ${bp:,.2f} (no margin)."
    else:
        held = {p["symbol"]: float(p.get("shares_available_for_sells") or 0) for p in account.positions(no)}
        if float(amt) > held.get(sym, 0.0) + 1e-9:
            return f"Blocked: you hold {held.get(sym, 0.0)} {sym} available to sell."
    if est > _cap("ROBINHOOD_MAX_ORDER_USD", 25):
        return f"Blocked: est. ${est:,.2f} is over the per-order cap ${_cap('ROBINHOOD_MAX_ORDER_USD', 25):,.0f}."
    if _spent_today() + est > _cap("ROBINHOOD_MAX_DAILY_USD", 50):
        return "Blocked: daily order cap reached."
    token = secrets.token_hex(3).upper()
    with _lock:
        now = time.time()
        for k in [k for k, v in _pending.items() if v["exp"] < now]:
            del _pending[k]
        _pending[token] = {"args": args, "user": user_id, "exp": now + TTL, "est": est}
    _audit({"event": "proposed", "user": user_id, "args": {k: v for k, v in args.items() if k != "account_number"}, "est": est})
    desc = f"{side.upper()} {sym} {'$' + amt.lstrip('$') if dollars else amt + ' sh'}" + (f" @ {limit}" if limit else " market")
    status = "" if live_enabled() else "\nLIVE ORDERS ARE DISABLED (ROBINHOOD_LIVE_ORDERS=false): confirming will not place anything."
    return (f"Proposed (MCP account, regular hours, day order): {desc}\nEst. ~${est:,.2f} | bid {bid} ask {ask}\n"
            f"{review.get('market_data_disclosure', '')}\nReply /confirm {token} within {TTL}s to submit, or ignore to cancel.{status}")


def confirm(token: str, user_id) -> str:
    token = token.strip().upper()
    with _lock:
        p = _pending.pop(token, None)
    if not p or p["exp"] < time.time():
        return "No valid pending order for that code (expired or already used)."
    if p["user"] != user_id:
        return "That code belongs to a different user."
    if not live_enabled():
        _audit({"event": "confirm_blocked_disabled", "user": user_id})
        return "Live orders are disabled (ROBINHOOD_LIVE_ORDERS is not 'true'). Nothing was placed."
    args = dict(p["args"])
    acct = account.agentic_account()
    if args["account_number"] != acct["account_number"]:
        return "Account mismatch; refusing."
    if not account.approval_required(acct["account_number"]) and os.getenv("ROBINHOOD_ALLOW_NO_APP_APPROVAL", "false").lower() != "true":
        return ("Refusing: 'human must approve trades' is OFF for the MCP account. Turn it on in the Robinhood app "
                "(or set ROBINHOOD_ALLOW_NO_APP_APPROVAL=true to let Telegram confirmation be the only approval).")
    if _spent_today() + p["est"] > _cap("ROBINHOOD_MAX_DAILY_USD", 50):
        return "Blocked: daily order cap reached."
    args["ref_id"] = str(uuid.uuid4())
    res = account.place_order(args)
    body = res["content"][0].get("text", "")
    _audit({"event": "placed", "user": user_id, "error": bool(res.get("isError")), "resp": body[:300]})
    if res.get("isError"):
        return f"Order rejected: {body[:300]}"
    _record(p["est"])
    try:
        d = json.loads(body).get("data", {})
    except ValueError:
        d = {}
    extra = " It now awaits your approval in the Robinhood app." if d.get("customer_approval_required") else ""
    return f"Order submitted: {args['side'].upper()} {args['symbol']}.{extra}\n{body[:300]}"
