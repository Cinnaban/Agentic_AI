"""End-of-day chart: paper portfolio vs S&P 500 (SPY) and Dow Jones (DIA), return % every half hour."""
from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
BENCHMARKS = {"S&P 500 (SPY)": "SPY", "Dow Jones (DIA)": "DIA"}


def session_slots(day, open_hm=(9, 30), close_hm=(16, 0)):
    """Half-hour timestamps from the open to the close, inclusive."""
    t = datetime(day.year, day.month, day.day, *open_hm, tzinfo=ET)
    end = datetime(day.year, day.month, day.day, *close_hm, tzinfo=ET)
    out = []
    while t <= end:
        out.append(t)
        t += timedelta(minutes=30)
    return out


def portfolio_series(equity_log, base, slots):
    """Return per slot from the last equity sample at or before it (None before the first sample)."""
    pts = sorted((datetime.fromisoformat(ts).astimezone(ET), eq) for ts, eq in equity_log)
    out = []
    for slot in slots:
        eligible = [eq for ts, eq in pts if ts <= slot + timedelta(minutes=2)]
        out.append((eligible[-1] / base - 1) if eligible and base else None)
    return out


def benchmark_series(bars, prev_close, slots):
    """30-minute bars -> return vs previous close. A slot's value is the close of the bar that ended there;
    the open slot uses the first bar's open."""
    if not bars or not prev_close:
        return [None] * len(slots)
    by_start = {b["ts"].astimezone(ET): b for b in bars if b.get("ts")}
    out = []
    for i, slot in enumerate(slots):
        if i == 0:
            b = by_start.get(slot)
            px = b and b.get("open")
        else:
            b = by_start.get(slot - timedelta(minutes=30))
            px = b and b.get("close")
        out.append((px / prev_close - 1) if px else None)
    return out


def build_chart(equity_log, base_equity, bench_bars, bench_prev, day, out_dir=None):
    """Render the chart and return its PNG path, or None when there is nothing to plot."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    slots = session_slots(day)
    today_log = [x for x in equity_log if x[0][:10] == day.isoformat()]
    series = {"Paper portfolio": portfolio_series(today_log, base_equity, slots)}
    for label, sym in BENCHMARKS.items():
        series[label] = benchmark_series(bench_bars.get(sym), bench_prev.get(sym), slots)
    if not any(v is not None for vals in series.values() for v in vals):
        return None

    fig, ax = plt.subplots(figsize=(10, 5.5))
    xs = list(range(len(slots)))
    styles = {"Paper portfolio": ("#1b9e77", 2.8), "S&P 500 (SPY)": ("#1f77b4", 1.8), "Dow Jones (DIA)": ("#d95f02", 1.8)}
    for label, vals in series.items():
        pts = [(x, v * 100) for x, v in zip(xs, vals) if v is not None]
        if pts:
            color, width = styles[label]
            ax.plot(*zip(*pts), marker="o", markersize=4, linewidth=width, color=color, label=label)
    ax.axhline(0, color="#888", linewidth=0.8)
    ax.set_xticks(xs)
    ax.set_xticklabels([s.strftime("%H:%M") for s in slots], rotation=45, ha="right")
    ax.set_xlabel("Time (ET), every half hour from open to close")
    ax.set_ylabel("Return (%)")
    ax.set_title(f"Paper portfolio vs S&P 500 and Dow Jones - {day.strftime('%a %b %d, %Y')}")
    ax.grid(alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    path = Path(out_dir or tempfile.gettempdir()) / f"paper_session_{day.isoformat()}.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return str(path)
