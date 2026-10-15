#!/bin/bash
# Internal paper trader: live Robinhood market data (read-only), simulated fills, Discord summaries.
set -e
PROJECT_ROOT="/Users/bunnyhouse_mastercontrol/Agentic_AI"
cd "$PROJECT_ROOT"
set -a
source "$PROJECT_ROOT/.env"
set +a
export PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/Agentic_Trader"
export PYTHONUNBUFFERED=1
export TRADING_MODE=paper
cd "$PROJECT_ROOT/Agentic_Trader"
exec /Users/bunnyhouse_mastercontrol/.venv/bin/python -W ignore -m agentic_trader paper-live
