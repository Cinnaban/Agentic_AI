"""Dependency-free stdio MCP server exposing the research pipeline and paper-trader status to the Hermes Agent.

Read-only: no order placement is exposed. Run with the project venv (Python 3.9).
"""
import json
import re
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "Agentic_Trader"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

PROTOCOL = "2024-11-05"
_router = None
PROTO_OUT = sys.stdout
sys.stdout = sys.stderr

TOOLS = [
    {
        "name": "research_question",
        "description": (
            "Answer any research, finance, stock, ETF, comparison, news or general-knowledge question with the "
            "local multi-agent pipeline. Pass the user's message unchanged. Returns the finished, formatted "
            "answer: return it to the user exactly as given, including any MEDIA: lines."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"question": {"type": "string", "description": "The user's message, verbatim."}},
            "required": ["question"],
        },
    },
    {
        "name": "paper_trader_status",
        "description": "Status of the internal paper-trading account (positions, P&L, desk activity). Read only.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _load_env(path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _get_router():
    global _router
    if _router is None:
        _load_env(ROOT / ".env")
        from integrations.messaging.message_router import MessageRouter
        from orchestrator.hermes import Hermes
        _router = MessageRouter(Hermes())
    return _router


def research_parts(question, source="hermes-agent"):
    from integrations.messaging.response_formatter import ResponseFormatter

    router = _get_router()
    result = router.route(router.normalize_message(source=source, text=question))
    text = ResponseFormatter().format(result)
    return text, [a["path"] for a in ResponseFormatter.get_attachments(result)]


def research(question, source="hermes-agent"):
    text, media = research_parts(question, source)
    if media:
        text += "\n\n" + "\n".join("MEDIA:" + path for path in media)
    return text


def call_tool(name, arguments):
    if name == "research_question":
        question = str((arguments or {}).get("question", "")).strip()
        if not question:
            raise ValueError("question is required")
        return research(question)
    if name == "paper_trader_status":
        from agentic_trader import paper_live
        return paper_live.status_text()
    raise ValueError("unknown tool: " + str(name))


def _reply(msg_id, result=None, error=None):
    body = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        body["error"] = error
    else:
        body["result"] = result
    PROTO_OUT.write(json.dumps(body) + "\n")
    PROTO_OUT.flush()


def handle(message):
    method = message.get("method")
    msg_id = message.get("id")
    if msg_id is None:
        return
    if method == "initialize":
        _reply(msg_id, {
            "protocolVersion": PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "agentic-research", "version": "1.0"},
        })
    elif method == "tools/list":
        _reply(msg_id, {"tools": TOOLS})
    elif method == "tools/call":
        params = message.get("params") or {}
        try:
            text = call_tool(params.get("name"), params.get("arguments"))
            _reply(msg_id, {"content": [{"type": "text", "text": text}], "isError": False})
        except Exception as exc:
            _reply(msg_id, {"content": [{"type": "text", "text": "Error: " + str(exc)}], "isError": True})
    elif method == "ping":
        _reply(msg_id, {})
    else:
        _reply(msg_id, error={"code": -32601, "message": "method not found"})


ORDER_COMMANDS = ("buy", "sell")


def run_command(text, identity):
    """Deterministic Robinhood/paper commands (same functions as the old Telegram bot). Never reaches an LLM."""
    from integrations.messaging import telegram_robinhood as rh

    parts = re.sub(r"^(/\w+)@\w+", r"\1", text.strip()).split()
    name, args = parts[0].lstrip("/").lower(), parts[1:]
    if name in ("rh", "robinhood", "help_rh"):
        return rh.HELP
    if name in ("portfolio", "positions"):
        return rh._portfolio()
    if name == "paper":
        return rh._paper()
    if name == "review":
        return rh._review([a.strip(",").upper() for a in args if re.fullmatch(r"[A-Za-z.\-,]{1,12}", a)])
    if name in ORDER_COMMANDS:
        return rh._order(text, identity)
    if name == "confirm":
        return rh._confirm(args[0] if args else "", identity)
    raise ValueError("unsupported command")


WATCHDOG_SECONDS = 1200
GENERAL_WATCHDOG_SECONDS = 420


COMPANY_WORDS = re.compile(
    r"\b(analy[sz]e|analysis|evaluate|portfolio|stocks?|etfs?|tickers?|shares?|valuation|earnings|"
    r"mutual funds?|invest\w*)\b",
    re.IGNORECASE,
)
TICKER = re.compile(r"\$[A-Za-z]{1,5}\b|\b[A-Z]{3,5}\b")
CAPS_WORDS = {"FPS", "RTS", "MOBA", "RPG", "MMO", "NFL", "NBA", "MLB", "NHL", "USA", "THE", "AND"}


def _is_company_question(question):
    """Company, ETF and portfolio analyses are slow by design; everything else gets the shorter cap."""
    if COMPANY_WORDS.search(question):
        return True
    return any(t not in CAPS_WORDS for t in TICKER.findall(question))


def _arm_watchdog(question=""):
    """A hung pipeline must answer instead of leaving 'Processing...' forever; the stack goes to a log."""
    import faulthandler
    import threading

    log_path = os.path.expanduser("~/.hermes/logs/front-door-hangs.log")
    log_file = open(log_path, "a")
    limit = WATCHDOG_SECONDS if _is_company_question(question) else GENERAL_WATCHDOG_SECONDS
    faulthandler.dump_traceback_later(limit - 5, file=log_file)

    def expire():
        PROTO_OUT.write(json.dumps({
            "text": "That analysis took too long and was stopped. Try a narrower question.",
            "media": [],
        }) + "\n")
        PROTO_OUT.flush()
        os._exit(0)

    timer = threading.Timer(limit, expire)
    timer.daemon = True
    timer.start()


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--ask":
        _arm_watchdog(sys.argv[2])
    if len(sys.argv) > 3 and sys.argv[1] == "--cmd":
        try:
            PROTO_OUT.write(json.dumps({"text": run_command(sys.argv[2], sys.argv[3]), "media": []}) + "\n")
        except Exception as exc:
            PROTO_OUT.write(json.dumps({"text": "Request failed: " + str(exc)[:200], "media": []}) + "\n")
        PROTO_OUT.flush()
        return
    if len(sys.argv) > 2 and sys.argv[1] == "--ask":
        # One-shot mode for the Hermes gateway plugin: prints one JSON line to the real stdout
        source = sys.argv[3] if len(sys.argv) > 3 else "hermes-agent"
        try:
            text, media = research_parts(sys.argv[2], source)
            PROTO_OUT.write(json.dumps({"text": text, "media": media}) + "\n")
        except Exception as exc:
            import traceback
            with open(os.path.expanduser("~/.hermes/logs/front-door-errors.log"), "a") as log_file:
                log_file.write(traceback.format_exc() + "\n---\n")
            PROTO_OUT.write(json.dumps({"text": "Analysis failed: " + str(exc), "media": []}) + "\n")
        PROTO_OUT.flush()
        return
    for line in sys.stdin:
        line = line.strip()
        if line:
            try:
                handle(json.loads(line))
            except Exception as exc:
                print("mcp error:", repr(exc), file=sys.stderr)


if __name__ == "__main__":
    main()
