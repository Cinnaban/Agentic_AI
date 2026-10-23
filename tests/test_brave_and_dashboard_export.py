import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from data.providers.live import premium_sources as ps

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Agentic_Trader"))


class BraveSearchTests(unittest.TestCase):

    def test_disabled_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            backend = ps.BraveSearchBackend()
            self.assertFalse(backend.is_configured())
            self.assertEqual(backend.search("x"), [])

    def test_parses_web_results(self):
        with patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "k"}):
            backend = ps.BraveSearchBackend()
        response = MagicMock(status_code=200)
        response.json.return_value = {"web": {"results": [
            {"title": "MTG", "url": "https://a.com", "description": "news"}]}}
        with patch.object(ps.requests, "get", return_value=response) as get:
            rows = backend.search("mtg")
        self.assertEqual(rows[0]["source"], "Brave Search")
        self.assertEqual(get.call_args.kwargs["headers"]["X-Subscription-Token"], "k")


class GrafanaExportTests(unittest.TestCase):

    def test_export_builds_tables(self):
        from agentic_trader import grafana_export

        state = {
            "start_cash": 5000, "cash": 4000, "realized_total": 5, "fees_total": 0.1,
            "regime": {"name": "normal"},
            "positions": {"VOO": {"qty": 1, "avg": 100, "sleeve": "core"}},
            "equity_log": [["2026-10-15T10:00:00-04:00", 5000], ["2026-10-15T15:00:00-04:00", 5050]],
            "trades": [{"ts": "2026-10-15T11:00:00-04:00", "side": "sell", "sym": "AAPL", "qty": 1,
                        "px": 10, "fee": 0.01, "sleeve": "day", "reason": "x", "value": 10, "realized": 5}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / "s.json", Path(tmp) / "t.db"
            source.write_text(json.dumps(state))
            self.assertEqual(grafana_export.export(source, target)["trades"], 1)
            db = sqlite3.connect(target)
            self.assertAlmostEqual(db.execute("SELECT return_pct FROM daily").fetchone()[0], 1.0)
            self.assertEqual(db.execute("SELECT symbol FROM positions").fetchone()[0], "VOO")


if __name__ == "__main__":
    unittest.main()
