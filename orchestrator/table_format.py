"""Re-exports the shared table helpers from Agentic_Trader so every bot formats tables identically."""
import sys
from pathlib import Path

_TRADER = str(Path(__file__).resolve().parents[1] / "Agentic_Trader")
if _TRADER not in sys.path:
    sys.path.append(_TRADER)

from agentic_trader.tables import (  # noqa: E402,F401
    FENCE, holdings_tables, kv_table, split_message, table, to_telegram_html)
