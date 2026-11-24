# Local Improvement Agent

Automatic self-review and iterative improvement system for paper trading strategies.

## Overview

The Local Improvement Agent monitors paper trader performance, analyzes metrics, and queries the Hermes research pipeline for improvement recommendations. It runs locally on the same machine as the paper trader.

```
Paper Trader          Local Improvement Agent
     ↓                        ↓
  Runs trades     Monitors performance
     │                        │
     └────────────────────────┘
              Every 60 minutes:
              • Check P&L/drawdown
              • If performance degrades
              • Query Hermes for improvements
              • Log recommendations
```

## Features

- ✅ **Local monitoring** - Direct access to paper trader status
- ✅ **Performance analysis** - Detects degradation with configurable thresholds
- ✅ **AI recommendations** - Queries Hermes research pipeline for improvements
- ✅ **24/7 operation** - Runs continuously via launchd (macOS)
- ✅ **Full logging** - All activity logged for review
- ✅ **Easy configuration** - Adjust thresholds and intervals as needed

## Quick Start

### 1. Test Locally

```bash
cd /path/to/Agentic_AI

# Check status once
python run_local_improvement_agent.py --check-status

# Generate improvement recommendations
python run_local_improvement_agent.py --improve

# Monitor for 1 hour (Ctrl+C to stop)
python run_local_improvement_agent.py --monitor
```

### 2. Install as Background Service (macOS)

```bash
# Copy plist to launchd
cp com.agentic.local-improvement-agent.plist ~/Library/LaunchAgents/

# Load and start
launchctl load ~/Library/LaunchAgents/com.agentic.local-improvement-agent.plist

# Verify running
launchctl list | grep local-improvement
```

### 3. Monitor Logs

```bash
# Real-time log
tail -f logs/local_improvement_agent.log

# View recent activity
tail -100 logs/local_improvement_agent.log
```

## Commands

```bash
# Check paper trader status once
python run_local_improvement_agent.py --check-status

# Analyze and get improvement recommendations
python run_local_improvement_agent.py --improve

# Continuous monitoring (runs until Ctrl+C)
python run_local_improvement_agent.py --monitor

# View performance history
python run_local_improvement_agent.py --history

# Custom check interval (e.g., 30 minutes)
python run_local_improvement_agent.py --monitor --interval 30

# Custom log file location
python run_local_improvement_agent.py --monitor --log-file /path/to/logfile
```

## Performance Signals

The agent monitors these conditions and generates signals:

| Signal | Trigger | Action |
|--------|---------|--------|
| **NORMAL** | Drawdown < 5%, Daily P&L > -$100 | Continue monitoring |
| **WARNING** | Drawdown > 5% | Monitor closely |
| **ALERT** | Daily P&L < -$100 | Trigger analysis |
| **CRITICAL** | Total P&L < -$500 | Priority analysis |

Thresholds can be customized via CLI arguments (see source code).

## Managing the Service (macOS)

```bash
# View status
launchctl list | grep local-improvement

# Stop service
launchctl unload ~/Library/LaunchAgents/com.agentic.local-improvement-agent.plist

# Start service
launchctl load ~/Library/LaunchAgents/com.agentic.local-improvement-agent.plist

# Restart service
launchctl unload ~/Library/LaunchAgents/com.agentic.local-improvement-agent.plist
sleep 2
launchctl load ~/Library/LaunchAgents/com.agentic.local-improvement-agent.plist
```

## Configuration

Edit `com.agentic.local-improvement-agent.plist` to modify:

- **Check interval**: Change `--interval 60` (in minutes)
- **Log location**: Modify `--log-file` path
- **Working directory**: Update if Agentic_AI is in different location

Then reload:
```bash
launchctl unload ~/Library/LaunchAgents/com.agentic.local-improvement-agent.plist
launchctl load ~/Library/LaunchAgents/com.agentic.local-improvement-agent.plist
```

## Expected Log Output

### Normal operation
```
2024-11-23 10:30:46 [INFO] Checking paper trader status...
2024-11-23 10:30:47 [INFO] Status: normal | P&L: $1234.56 | Drawdown: 2.3%
```

### Alert triggered
```
2024-11-23 10:30:46 [INFO] Checking paper trader status...
2024-11-23 10:30:47 [INFO] Status: alert | P&L: $234.56 | Drawdown: 6.8%
2024-11-23 10:30:47 [INFO] Performance alert detected - triggering analysis
2024-11-23 10:30:52 [INFO] Improvement analysis complete. Recommendation:
2024-11-23 10:30:52 [INFO] Based on market analysis... recommend changing...
```

## Logs

```
logs/
├─ local_improvement_agent.log       (main activity log)
├─ local_improvement_agent_stdout.log (stdout from service)
└─ local_improvement_agent_stderr.log (errors from service)
```

## Troubleshooting

### Service won't start
```bash
# Check error output
tail -f logs/local_improvement_agent_stderr.log

# Validate plist syntax
plutil -lint ~/Library/LaunchAgents/com.agentic.local-improvement-agent.plist

# Verify file permissions
ls -la ~/Library/LaunchAgents/com.agentic.local-improvement-agent.plist
chmod 644 ~/Library/LaunchAgents/com.agentic.local-improvement-agent.plist
```

### Import errors
```bash
# Install requirements
pip install -r requirements.txt

# Or install specific modules
pip install numpy pandas
```

### High CPU usage
```bash
# Increase check interval in plist
# Edit: --interval 60 to --interval 120
# Then reload service (see Managing the Service section above)
```

## Implementation Details

The agent:
1. Calls `paper_live.status_text()` for paper trader status
2. Parses metrics using regex patterns
3. Compares against performance thresholds
4. Calls Hermes research pipeline locally when performance degrades
5. Logs all metrics, signals, and recommendations
6. Maintains historical metrics in memory (100 entry buffer)
7. Repeats every configured interval

## Architecture

```
LocalImprovementAgent
│
├─ get_paper_trader_status()
│  └─ Calls: paper_live.status_text()
│
├─ parse_status()
│  └─ Extracts metrics via regex
│
├─ query_hermes_research()
│  └─ Calls: MessageRouter(Hermes()).route(query)
│
├─ check_status()
│  └─ Fetches and analyzes current metrics
│
├─ trigger_improvement()
│  └─ Builds query and gets Hermes recommendations
│
└─ Performance Signal Determination
   └─ normal / warning / alert / critical
```

## Files

- `run_local_improvement_agent.py` - Main agent script
- `com.agentic.local-improvement-agent.plist` - launchd configuration
- `logs/` - Log directory (created automatically)

## Requirements

- Python 3.9+
- Paper trader running locally
- Hermes agents available locally
- macOS (for launchd) or adaptation for other platforms

## Development

The agent runs in a single thread and is designed to be lightweight. Each check cycle typically takes <1 second (unless Hermes analysis is triggered, which may take 5-30 seconds).

Memory usage is minimal (~50MB resident). Historical metric buffer is limited to 100 entries (~1MB).

## License

Same as Agentic_AI repository

## Support

For issues:
1. Check error logs: `tail -f logs/local_improvement_agent_stderr.log`
2. Verify paper trader is running
3. Test manually: `python run_local_improvement_agent.py --check-status`
4. Review source code comments in `run_local_improvement_agent.py`
