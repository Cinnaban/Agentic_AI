#!/usr/bin/env python3
"""
Local Improvement Agent - Runs on Mac Mini to self-review and iteratively improve.

This agent runs locally on the Mac Mini and:
1. Monitors its own paper trader performance
2. Analyzes metrics for degradation
3. Queries Hermes pipeline for improvement recommendations
4. Applies or logs recommendations for review
5. Repeats iteratively

Usage:
    python run_local_improvement_agent.py --check-status
    python run_local_improvement_agent.py --improve
    python run_local_improvement_agent.py --monitor
    python run_local_improvement_agent.py --history
"""

import json
import logging
import re
import sys
import time
import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from enum import Enum


class PerformanceSignal(Enum):
    """Performance signals that trigger improvements."""
    NORMAL = "normal"
    WARNING = "warning"
    ALERT = "alert"
    CRITICAL = "critical"


@dataclass
class PerformanceMetrics:
    """Parsed paper trader performance metrics."""
    total_pnl: float
    daily_pnl: float
    win_rate: float
    num_trades: int
    max_drawdown: float
    timestamp: datetime
    signal: PerformanceSignal


def setup_logging(log_file: Optional[str] = None) -> logging.Logger:
    """Configure logging."""
    log_level = "INFO"
    
    logger = logging.getLogger("LocalImprovementAgent")
    logger.setLevel(getattr(logging, log_level))
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(getattr(logging, log_level))
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


class LocalImprovementAgent:
    """Agent that runs on Mac Mini to review and improve paper trader."""
    
    def __init__(
        self,
        check_interval_minutes: int = 60,
        alert_threshold_drawdown: float = 5.0,
        alert_threshold_daily_pnl: float = -100.0,
        critical_threshold_loss: float = -500.0,
        log_file: Optional[str] = None,
    ):
        """Initialize the local improvement agent."""
        self.name = "LocalImprovementAgent"
        self.logger = setup_logging(log_file)
        
        # Performance thresholds
        self.alert_threshold_drawdown = alert_threshold_drawdown
        self.alert_threshold_daily_pnl = alert_threshold_daily_pnl
        self.critical_threshold_loss = critical_threshold_loss
        
        # Timing
        self.check_interval = timedelta(minutes=check_interval_minutes)
        self.last_check = None
        self.last_improvement = None
        
        # Historical tracking
        self.metric_history: List[PerformanceMetrics] = []
        self.max_history = 100
        
        self.logger.info(f"LocalImprovementAgent initialized")
        self.logger.info(f"Check interval: {check_interval_minutes} minutes")
        self.logger.info(f"Alert thresholds: drawdown={alert_threshold_drawdown}%, daily_pnl=${alert_threshold_daily_pnl}")
    
    def get_paper_trader_status(self) -> str:
        """Get paper trader status directly (no SSH)."""
        try:
            # Import directly - we're running on Mac Mini with environment ready
            from Agentic_Trader.agentic_trader import paper_live
            status = paper_live.status_text()
            return status
        except Exception as e:
            self.logger.error(f"Failed to get paper trader status: {e}")
            raise
    
    def query_hermes_research(self, question: str) -> str:
        """Query Hermes research pipeline directly."""
        try:
            from integrations.messaging.message_router import MessageRouter
            from orchestrator.hermes import Hermes
            from integrations.messaging.response_formatter import ResponseFormatter
            
            router = MessageRouter(Hermes())
            result = router.route(router.normalize_message(source="local-improvement-agent", text=question))
            text = ResponseFormatter().format(result)
            
            # Append media links if any
            media = ResponseFormatter.get_attachments(result)
            if media:
                text += "\n\n" + "\n".join("MEDIA:" + a["path"] for a in media)
            
            return text
        except Exception as e:
            self.logger.error(f"Failed to query Hermes: {e}")
            raise
    
    def parse_status(self, status_text: str) -> Optional[PerformanceMetrics]:
        """Parse paper trader status text into metrics."""
        try:
            metrics = {
                "total_pnl": 0.0,
                "daily_pnl": 0.0,
                "win_rate": 0.0,
                "num_trades": 0,
                "max_drawdown": 0.0,
            }
            
            patterns = {
                "total_pnl": r"Total P&L:?\s*[\$]?([-\d.]+)",
                "daily_pnl": r"Daily P&L:?\s*[\$]?([-\d.]+)",
                "win_rate": r"Win Rate:?\s*([\d.]+)%",
                "num_trades": r"Trades?:?\s*(\d+)",
                "max_drawdown": r"Max Drawdown:?\s*([\d.]+)%",
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, status_text, re.IGNORECASE)
                if match:
                    value = float(match.group(1))
                    metrics[key] = value
            
            # Determine signal
            signal = PerformanceSignal.NORMAL
            if metrics["max_drawdown"] > self.alert_threshold_drawdown:
                signal = PerformanceSignal.WARNING
            if metrics["daily_pnl"] < self.alert_threshold_daily_pnl:
                signal = PerformanceSignal.ALERT
            if metrics["total_pnl"] < self.critical_threshold_loss:
                signal = PerformanceSignal.CRITICAL
            
            return PerformanceMetrics(
                total_pnl=metrics["total_pnl"],
                daily_pnl=metrics["daily_pnl"],
                win_rate=metrics["win_rate"],
                num_trades=metrics["num_trades"],
                max_drawdown=metrics["max_drawdown"],
                timestamp=datetime.now(),
                signal=signal,
            )
        except Exception as e:
            self.logger.error(f"Failed to parse status: {e}")
            return None
    
    def check_status(self) -> Dict[str, Any]:
        """Check paper trader status."""
        self.logger.info("Checking paper trader status...")
        
        try:
            status_text = self.get_paper_trader_status()
            metrics = self.parse_status(status_text)
            
            if not metrics:
                return {"error": "Could not parse metrics"}
            
            self.last_check = datetime.now()
            self.metric_history.append(metrics)
            if len(self.metric_history) > self.max_history:
                self.metric_history.pop(0)
            
            result = {
                "timestamp": metrics.timestamp.isoformat(),
                "total_pnl": metrics.total_pnl,
                "daily_pnl": metrics.daily_pnl,
                "win_rate": metrics.win_rate,
                "num_trades": metrics.num_trades,
                "max_drawdown": metrics.max_drawdown,
                "signal": metrics.signal.value,
                "status_text": status_text,
            }
            
            # Log summary
            self.logger.info(f"Status: {metrics.signal.value} | P&L: ${metrics.total_pnl:.2f} | Drawdown: {metrics.max_drawdown:.1f}%")
            
            return result
        
        except Exception as e:
            self.logger.error(f"Status check failed: {e}")
            return {"error": str(e)}
    
    def trigger_improvement(self) -> Dict[str, Any]:
        """Analyze performance and trigger improvements."""
        if not self.metric_history:
            msg = "No performance history. Run check_status first."
            self.logger.warning(msg)
            return {"error": msg}
        
        metrics = self.metric_history[-1]
        
        if metrics.signal == PerformanceSignal.NORMAL:
            msg = "Performance is healthy. No improvements needed."
            self.logger.info(msg)
            return {"status": msg}
        
        self.logger.info(f"Triggering improvement analysis for {metrics.signal.value} signal")
        
        # Build query
        query = (
            f"Paper trading strategy performance:\n"
            f"- Total P&L: ${metrics.total_pnl:.2f}\n"
            f"- Daily P&L: ${metrics.daily_pnl:.2f}\n"
            f"- Win Rate: {metrics.win_rate:.1f}%\n"
            f"- Max Drawdown: {metrics.max_drawdown:.1f}%\n"
            f"- Trades: {metrics.num_trades}\n\n"
            f"Analyze market conditions and suggest specific improvements to:\n"
            f"1. Entry/exit criteria\n"
            f"2. Position sizing\n"
            f"3. Risk management\n"
            f"4. Market timing\n"
            f"Provide actionable recommendations with implementation details."
        )
        
        try:
            recommendation = self.query_hermes_research(query)
            self.last_improvement = datetime.now()
            
            self.logger.info("Improvement analysis complete. Recommendation:")
            self.logger.info(recommendation)
            
            return {
                "trigger_signal": metrics.signal.value,
                "recommendation": recommendation,
                "timestamp": datetime.now().isoformat(),
            }
        
        except Exception as e:
            self.logger.error(f"Improvement analysis failed: {e}")
            return {"error": str(e)}
    
    def print_status(self, data: Dict[str, Any]) -> None:
        """Pretty print status."""
        if "error" in data:
            print(f"\n❌ Error: {data['error']}\n")
            return
        
        print("\n" + "="*70)
        print("PAPER TRADER STATUS")
        print("="*70)
        print(f"Timestamp: {data.get('timestamp', 'N/A')}")
        print(f"Total P&L: ${data.get('total_pnl', 0):.2f}")
        print(f"Daily P&L: ${data.get('daily_pnl', 0):.2f}")
        print(f"Win Rate: {data.get('win_rate', 0):.1f}%")
        print(f"Trades: {data.get('num_trades', 0)}")
        print(f"Max Drawdown: {data.get('max_drawdown', 0):.1f}%")
        print(f"Signal: {data.get('signal', 'unknown').upper()}")
        print("="*70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Local Improvement Agent - Self-review on Mac Mini"
    )
    parser.add_argument("--check-status", action="store_true", help="Check status once")
    parser.add_argument("--improve", action="store_true", help="Trigger improvement analysis")
    parser.add_argument("--monitor", action="store_true", help="Continuous monitoring")
    parser.add_argument("--history", action="store_true", help="Show performance history")
    parser.add_argument("--interval", type=int, default=60, help="Check interval (minutes)")
    parser.add_argument("--log-file", default="logs/local_improvement_agent.log")
    
    args = parser.parse_args()
    
    agent = LocalImprovementAgent(
        check_interval_minutes=args.interval,
        log_file=args.log_file,
    )
    
    if args.check_status:
        data = agent.check_status()
        agent.print_status(data)
    
    elif args.improve:
        data = agent.trigger_improvement()
        print(json.dumps(data, indent=2, default=str))
    
    elif args.history:
        print(f"\nPerformance History ({len(agent.metric_history)} entries):")
        for i, m in enumerate(agent.metric_history[-10:], 1):  # Last 10
            print(f"{i}. {m.timestamp.strftime('%Y-%m-%d %H:%M')} | "
                  f"P&L: ${m.total_pnl:>8.2f} | "
                  f"Drawdown: {m.max_drawdown:>5.1f}% | "
                  f"Signal: {m.signal.value}")
        print()
    
    elif args.monitor:
        agent.logger.info("Starting continuous monitoring...")
        check_count = 0
        
        try:
            while True:
                check_count += 1
                agent.logger.info(f"\n--- Check #{check_count} ---")
                
                # Check status
                status = agent.check_status()
                agent.print_status(status)
                
                # Trigger improvement if needed
                if status.get("signal") in ("alert", "critical"):
                    agent.logger.info("Performance alert detected - triggering analysis")
                    improvement = agent.trigger_improvement()
                    agent.print_status(improvement)
                
                # Wait for next check
                agent.logger.info(f"Next check in {args.interval} minutes...")
                time.sleep(agent.check_interval.total_seconds())
        
        except KeyboardInterrupt:
            agent.logger.info("\nMonitoring stopped by user")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
