"""MCP OAuth (dynamic client registration + PKCE) for agent.robinhood.com. Tokens live in the gitignored .env."""
from __future__ import annotations

import base64
import hashlib
import http.server
import os
import secrets
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

import requests

from ..config import PROJECT_ROOT, load_env_files

MCP_URL = "https://agent.robinhood.com/mcp/trading"
META_URL = "https://agent.robinhood.com/.well-known/oauth-authorization-server/mcp/trading"
ENV_FILE = PROJECT_ROOT / ".env"
PORT = 8765
REDIRECT = f"http://127.0.0.1:{PORT}/callback"
KEYS = ("ROBINHOOD_CLIENT_ID", "ROBINHOOD_ACCESS_TOKEN", "ROBINHOOD_REFRESH_TOKEN", "ROBINHOOD_TOKEN_EXPIRES_AT")


def update_env(values: dict[str, str], path: Path = ENV_FILE) -> None:
    lines = path.read_text().splitlines() if path.exists() else []
    seen = set()
    for i, line in enumerate(lines):
        k = line.partition("=")[0].strip()
        if k in values:
            lines[i], _ = f"{k}={values[k]}", seen.add(k)
    lines += [f"{k}={v}" for k, v in values.items() if k not in seen]
    path.write_text("\n".join(lines) + "\n")
    path.chmod(0o600)
    for k, v in values.items():
        os.environ[k] = v


def metadata() -> dict:
    r = requests.get(META_URL, timeout=15)
    r.raise_for_status()
    return r.json()


def register(meta: dict) -> str:
    r = requests.post(meta["registration_endpoint"], timeout=15, json={
        "client_name": "Agentic_Trader (read-only data)", "redirect_uris": [REDIRECT],
        "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
        "token_endpoint_auth_method": "none"})
    if r.status_code >= 300:
        raise RuntimeError(f"Client registration failed: {r.status_code} {r.text[:300]}")
    return r.json()["client_id"]


def _token_request(meta: dict, data: dict) -> dict:
    r = requests.post(meta["token_endpoint"], data=data, timeout=15)
    if r.status_code >= 300:
        raise RuntimeError(f"Token request failed: {r.status_code} {r.text[:300]}")
    t = r.json()
    update_env({
        "ROBINHOOD_ACCESS_TOKEN": t["access_token"],
        "ROBINHOOD_REFRESH_TOKEN": t.get("refresh_token", os.getenv("ROBINHOOD_REFRESH_TOKEN", "")),
        "ROBINHOOD_TOKEN_EXPIRES_AT": str(int(time.time() + int(t.get("expires_in", 3600)) - 60)),
    })
    return t


def _wait_for_callback(url: str, open_browser: bool) -> dict:
    result: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            if urllib.parse.urlparse(self.path).path != "/callback":
                self.send_response(404); self.end_headers(); return
            result.update(q)
            self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers()
            self.wfile.write(b"Agentic_Trader: login received. You can close this tab.")

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    print("Open this URL to sign in (opening your browser):\n" + url)
    if open_browser:
        webbrowser.open(url)
    for _ in range(300):
        if result:
            break
        time.sleep(1)
    server.server_close()
    return result


def login(open_browser: bool = True, manual: bool = False) -> None:
    meta = metadata()
    client_id = os.getenv("ROBINHOOD_CLIENT_ID") or register(meta)
    update_env({"ROBINHOOD_CLIENT_ID": client_id})
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    url = meta["authorization_endpoint"] + "?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT, "state": state,
        "code_challenge": challenge, "code_challenge_method": "S256", "scope": "internal"})
    result: dict = {}
    if manual:
        print("Open this URL in any browser and sign in:\n" + url)
        print("\nAfter approving, the browser will try to load a http://127.0.0.1:8765/callback?... page that fails to load.")
        pasted = input("Paste that full address-bar URL here: ").strip()
        result.update(dict(urllib.parse.parse_qsl(urllib.parse.urlparse(pasted).query)))
    else:
        result = _wait_for_callback(url, open_browser)
    if result.get("state") != state or "code" not in result:
        raise RuntimeError(f"Login failed or timed out: {result}")
    _token_request(meta, {"grant_type": "authorization_code", "code": result["code"], "redirect_uri": REDIRECT,
                          "client_id": client_id, "code_verifier": verifier})
    print("Signed in. Tokens saved to Agentic_Trader/.env")


def _reload_tokens() -> None:
    """Re-read token keys from .env (another process may have refreshed them)."""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        k, _, v = line.partition("=")
        if k.strip() in KEYS:
            os.environ[k.strip()] = v.strip()


def _fresh() -> str | None:
    tok, exp = os.getenv("ROBINHOOD_ACCESS_TOKEN", ""), float(os.getenv("ROBINHOOD_TOKEN_EXPIRES_AT", "0") or 0)
    return tok if tok and time.time() < exp else None


def access_token() -> str:
    """Return a valid access token, refreshing under a file lock so concurrent processes
    (Discord bot, Telegram bot, trader) never race on a rotating refresh token."""
    import fcntl

    load_env_files()
    _reload_tokens()
    if tok := _fresh():
        return tok
    lock_path = ENV_FILE.with_name(".rh_token.lock")
    with open(lock_path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _reload_tokens()
        if tok := _fresh():
            return tok
        refresh, cid = os.getenv("ROBINHOOD_REFRESH_TOKEN"), os.getenv("ROBINHOOD_CLIENT_ID")
        if not (refresh and cid):
            raise RuntimeError("Not signed in. Run: python -m agentic_trader rh-login")
        return _token_request(metadata(), {"grant_type": "refresh_token", "refresh_token": refresh,
                                           "client_id": cid})["access_token"]


def is_configured() -> bool:
    load_env_files()
    return bool(os.getenv("ROBINHOOD_REFRESH_TOKEN") and os.getenv("ROBINHOOD_CLIENT_ID"))
