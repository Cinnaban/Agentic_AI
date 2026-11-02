"""Quant suite worker for the Gaming PC. Copy the Agentic_Trader folder there and run:

    python -m agentic_trader.quant_worker            (port 8011; set TRADER_QUANT_TOKEN to require a shared token)

Install numpy (and cupy-cuda12x for the NVIDIA GPU; agentic_trader.compute picks it up automatically).
GET /health -> {"status": "online"};  POST /suite {mode, interval, horizon, bars: {SYM: [{close, volume}, ...]}}.
It only does arithmetic on the numbers it is sent: no files, no network, no trading.
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import compute, quant_suite

MAX_BODY = 8_000_000
MAX_SYMBOLS = 60


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body):
        raw = json.dumps(body, default=float).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"status": "online", "backend": compute.BACKEND})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        token = os.getenv("TRADER_QUANT_TOKEN", "")
        if self.path != "/suite":
            return self._send(404, {"error": "not found"})
        if token and self.headers.get("X-Quant-Token") != token:
            return self._send(401, {"error": "bad token"})
        size = int(self.headers.get("Content-Length") or 0)
        if size <= 0 or size > MAX_BODY:
            return self._send(413, {"error": "bad body size"})
        try:
            req = json.loads(self.rfile.read(size))
            bars = req["bars"]
            if len(bars) > MAX_SYMBOLS:
                raise ValueError("too many symbols")
            results = {s: quant_suite.analyze(rows, str(req.get("interval", "day")), int(req.get("horizon", 1)),
                                              str(req.get("mode", "day"))) for s, rows in bars.items()}
        except Exception as exc:
            return self._send(400, {"error": repr(exc)[:200]})
        self._send(200, {"results": results, "backend": compute.BACKEND})


def main():
    port = int(os.getenv("TRADER_QUANT_PORT", "8011"))
    print(f"quant worker on :{port} ({compute.BACKEND})", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
