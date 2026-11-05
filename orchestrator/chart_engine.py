"""Generic chart generation: turns a chart request (and follow-ups) into a PNG.

Data sources: yfinance first, Alpha Vantage to fill missing fiscal years and
economic series. Nothing is invented; missing values are left as gaps and listed.
"""
import json
import os
import re
import tempfile
import threading
import time
from datetime import date, datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from orchestrator.table_format import table  # noqa: E402

_PLOT_LOCK = threading.Lock()
STATE_PATH = os.path.join(tempfile.gettempdir(), "agentic_chart_state.json")
STATE_TTL_SECONDS = 6 * 3600

INTENT = re.compile(
    r"\b(chart|charts|charting|graph|graphs|plot|plots|plotting|visuali[sz]e|"
    r"visuali[sz]ation|diagram|infographic)\b", re.I)
UPDATE_WORDS = re.compile(
    r"\b(add|also|include|update|change|modify|second|secondary|overlay|combine|"
    r"with|instead|replace|swap|remove|drop|only|just)\b", re.I)
REPLACE_WORDS = re.compile(r"\b(instead|replace|swap|only|just)\b", re.I)

# key -> (label, kind, aliases); kinds: money (bars, $), ratio (line, x), pct (line, %)
METRICS = {
    "revenue": ("Revenue", "money", r"revenues?|sales|top[- ]line"),
    "net_income": ("Net Profit", "money", r"net (?:profit|income|earnings)|profits?|earnings"),
    "ebitda": ("EBITDA", "money", r"ebitda"),
    "gross_profit": ("Gross Profit", "money", r"gross (?:profit|income)"),
    "operating_income": ("Operating Income", "money", r"operating (?:income|profit)|ebit"),
    "fcf": ("Free Cash Flow", "money", r"free cash ?flow|fcf"),
    "eps": ("Diluted EPS", "eps", r"eps|earnings per share"),
    "pe": ("P/E Ratio", "ratio", r"p/?e(?: ratio)?|price[- ](?:to[- ])?earnings|multiple"),
    "net_margin": ("Net Margin", "pct", r"net margins?|profit margins?"),
    "gross_margin": ("Gross Margin", "pct", r"gross margins?"),
    "price": ("Share Price", "price", r"(?:share |stock )?prices?|closing|close"),
    "return": ("Total Return", "pct_series", r"returns?|performance|growth"),
}
# Order matters: specific phrases are matched before generic ones.
METRIC_ORDER = ["gross_margin", "net_margin", "gross_profit", "operating_income", "ebitda",
                "fcf", "net_income", "revenue", "pe", "eps", "return", "price"]

ECONOMIC = {
    "CPI": ("Consumer Price Index", r"cpi|consumer price"),
    "INFLATION": ("Inflation", r"inflation"),
    "FEDERAL_FUNDS_RATE": ("Federal Funds Rate", r"fed(?:eral)? funds|interest rates?|fed rate"),
    "UNEMPLOYMENT": ("Unemployment Rate", r"unemployment"),
    "REAL_GDP": ("Real GDP", r"gdp"),
    "TREASURY_YIELD": ("10Y Treasury Yield", r"treasury|yields?"),
}

STOPWORDS = {
    "PE", "EPS", "EBITDA", "ROE", "ROI", "FCF", "ETF", "ETFS", "GDP", "CEO", "CPI", "USD", "AI",
    "US", "USA", "YOY", "QOQ", "IPO", "SEC", "FED", "ATH", "TTM", "EV", "NET", "AND", "THE", "FOR",
    "VS", "WITH", "ADD", "OF", "TO", "IN", "ON", "AS", "A", "I", "II", "Q1", "Q2", "Q3", "Q4",
}
NAME_STOP = {
    "chart", "graph", "plot", "show", "make", "create", "generate", "update", "draw", "give",
    "visualize", "visualise", "please", "can", "could", "you", "me", "the", "a", "an", "and",
    "for", "of", "to", "in", "on", "with", "vs", "versus", "compare", "between", "from", "last",
    "past", "since", "year", "years", "month", "months", "bar", "line", "second", "axis", "revenue",
    "ebitda", "profit", "price", "stock", "stocks", "i", "want", "need", "like", "also", "add",
    "image", "images", "picture", "based", "data", "source", "sources", "reference", "references",
    "dollars", "billions", "billion", "this", "that", "it", "its", "their", "against", "over",
    "time", "annual", "yearly", "quarterly", "ratio", "earnings", "income", "growth", "return",
    "performance", "inflation", "unemployment", "treasury", "cpi", "gdp", "pe", "eps", "fcf",
    "margin", "margins", "net", "gross", "operating", "free", "cash", "flow", "fed", "federal",
    "funds", "interest", "rate", "rates", "yield", "yields", "multiple", "what", "how", "has",
    "have", "is", "are", "was", "were", "been", "did", "do", "does", "my", "our", "your",
}


def is_chart_request(message):
    return bool(INTENT.search(str(message or "")))


# ---------- state (persisted because each front-door question may be a new process) ----------

def _load_state():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(key, spec):
    state = {k: v for k, v in _load_state().items()
             if time.time() - float(v.get("ts", 0)) < STATE_TTL_SECONDS}
    state[str(key)] = {"ts": time.time(), "spec": spec}
    try:
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
        os.replace(tmp, STATE_PATH)
    except OSError:
        pass


def _last_spec(key):
    entry = _load_state().get(str(key))
    if entry and time.time() - float(entry.get("ts", 0)) < STATE_TTL_SECONDS:
        return entry.get("spec")
    return None


# ---------- parsing ----------

def parse_metrics(message):
    text = str(message or "").lower()
    found = []
    for key in METRIC_ORDER:
        match = re.search(r"\b(?:%s)\b" % METRICS[key][2], text)
        if match:
            found.append((match.start(), key))
    # A specific phrase ("gross profit") consumes the generic word ("profit").
    keys = {k for _, k in found}
    if "gross_profit" in keys or "gross_margin" in keys or "net_margin" in keys:
        if not re.search(r"\bnet (?:profit|income)\b", text) and "net_income" in keys \
                and not re.search(r"\b(?:net income|net profit|earnings)\b", text):
            keys.discard("net_income")
    if "operating_income" in keys and "ebitda" in keys and not re.search(r"\bebit\b", text):
        keys.discard("operating_income")
    if "eps" in keys and "pe" in keys and not re.search(r"\beps\b|earnings per share", text):
        keys.discard("eps")
    if "net_income" in keys and "eps" in keys and re.search(r"earnings per share", text):
        keys.discard("net_income")
    ordered = [k for pos, k in sorted(found) if k in keys]
    return list(dict.fromkeys(ordered))


def parse_economic(message):
    text = str(message or "").lower()
    return [fn for fn, (_, pattern) in ECONOMIC.items() if re.search(r"\b(?:%s)\b" % pattern, text)]


def parse_period(message, default_years, annual=False):
    text = str(message or "").lower()
    this_year = date.today().year
    last = this_year - 1 if annual else this_year  # latest complete fiscal year
    match = re.search(r"\b((?:19|20)\d{2})\s*(?:-|–|to|through|until)\s*((?:19|20)\d{2})\b", text)
    if match:
        a, b = sorted((int(match.group(1)), int(match.group(2))))
        return a, min(b, this_year)
    match = re.search(r"\b(?:since|from)\s+((?:19|20)\d{2})\b", text)
    if match:
        return int(match.group(1)), last
    match = re.search(r"\b(?:last|past|previous)\s+(\d{1,2})\s*(year|yr|month)s?\b", text)
    if match:
        n = int(match.group(1))
        years = max(1, round(n / 12)) if match.group(2) == "month" else n
        return last - years + 1, last
    if re.search(r"\bytd|year to date\b", text):
        return this_year, this_year
    return last - default_years + 1, last


def parse_tickers(message, lookup=None):
    """Explicit tickers ($X / ALLCAPS) and capitalised company names resolved by search."""
    text = str(message or "")
    text_no_ratio = re.sub(r"\b[A-Za-z]/[A-Za-z]\b", " ", text)
    tickers = []
    for token in re.findall(r"\$([A-Za-z.\-]{1,6})\b", text):
        tickers.append(token.upper())
    for token in re.findall(r"\b[A-Z]{2,5}(?:[.-][A-Z]{1,2})?\b", text_no_ratio):
        if token not in STOPWORDS and token.upper() not in {t.upper() for t in NAME_STOP}:
            tickers.append(token)
    names = []
    for token in re.findall(r"\b[A-Z][a-z]{2,}(?:'s)?\b", text_no_ratio):
        word = token.replace("'s", "")
        if word.lower() not in NAME_STOP:
            names.append(word)
    # Lowercase company names after a chart verb are not guessed; capitalised words only.
    if lookup is None and names:
        from data.providers.company_ticker_lookup import CompanyTickerLookup
        lookup = CompanyTickerLookup()
    for name in dict.fromkeys(names):
        try:
            results = lookup.search(name) or []
        except Exception:
            results = []
        for candidate in results:
            first = re.split(r"[\s.,]+", str(candidate.get("name") or "").strip())[:1]
            if first and first[0].lower() == name.lower() \
                    and candidate.get("quote_type") in {"EQUITY", "ETF"}:
                tickers.append(candidate["symbol"])
                break
    return list(dict.fromkeys(tickers))


def build_spec(message, previous=None, lookup=None):
    economic = parse_economic(message)
    metrics = parse_metrics(message)
    tickers = parse_tickers(message, lookup=lookup)
    follow_up = bool(previous) and not tickers and not economic
    if previous and not tickers and not economic:
        tickers = list(previous.get("tickers", []))
    if previous and (follow_up or (not tickers and not economic)):
        old = list(previous.get("metrics", []))
        if not metrics:
            metrics = old
        elif not REPLACE_WORDS.search(str(message)) and UPDATE_WORDS.search(str(message)):
            metrics = list(dict.fromkeys(old + metrics))
    if economic:
        metrics = []
    default_years = 1 if (metrics and set(metrics) <= {"price", "return"}) else 5
    annual = bool(metrics) and not set(metrics) <= {"price", "return"}
    start, end = parse_period(message, default_years, annual=annual)
    if previous and follow_up and not re.search(r"\b(?:19|20)\d{2}\b|\blast\b|\bpast\b|\bytd\b", str(message), re.I):
        start, end = previous.get("start", start), previous.get("end", end)
    if tickers and not metrics and not economic:
        metrics = ["price"]
        start, end = parse_period(message, 1)
    return {"tickers": tickers[:5], "metrics": metrics[:4], "economic": economic[:2],
            "start": start, "end": end}


# ---------- data ----------

def _row(df, *names):
    for name in names:
        if name in df.index:
            return df.loc[name]
    return None


def fetch_annual(ticker, start, end, av_client=None):
    """{year: {metric: value}} plus the list of source labels used."""
    import yfinance as yf
    data, sources = {}, []
    t = yf.Ticker(ticker)

    def put(year, key, value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return
        if value != value:
            return
        data.setdefault(year, {})
        data[year].setdefault(key, value)

    ends = {}
    try:
        inc = t.income_stmt
        cash = t.cashflow
        if inc is not None and not inc.empty:
            sources.append("Yahoo Finance")
            for col in inc.columns:
                ends[col.year] = col
            for key, names in (("revenue", ("Total Revenue",)), ("net_income", ("Net Income",)),
                               ("ebitda", ("EBITDA",)), ("gross_profit", ("Gross Profit",)),
                               ("operating_income", ("Operating Income",)),
                               ("eps", ("Diluted EPS",))):
                series = _row(inc, *names)
                if series is not None:
                    for col, value in series.items():
                        put(col.year, key, value)
        if cash is not None and not cash.empty:
            series = _row(cash, "Free Cash Flow")
            if series is not None:
                for col, value in series.items():
                    put(col.year, "fcf", value)
    except Exception:
        pass

    wanted = range(start, end + 1)
    need_income = any("revenue" not in data.get(y, {}) for y in wanted)
    need_eps = any("eps" not in data.get(y, {}) for y in wanted)
    if need_income or need_eps:
        av = av_client or _av_client()
        if av is not None and av.configured():
            try:
                report = (av.call("INCOME_STATEMENT", ttl=7 * 86400, symbol=ticker) or {}) \
                    if need_income else {}
                used = False
                for item in report.get("annualReports", []):
                    year = int(str(item.get("fiscalDateEnding", "0000"))[:4])
                    ends.setdefault(year, datetime.strptime(item["fiscalDateEnding"], "%Y-%m-%d"))
                    for key, field in (("revenue", "totalRevenue"), ("net_income", "netIncome"),
                                       ("ebitda", "ebitda"), ("gross_profit", "grossProfit"),
                                       ("operating_income", "operatingIncome")):
                        before = data.get(year, {}).get(key)
                        put(year, key, item.get(field))
                        used = used or before is None and key in data.get(year, {})
                earnings = (av.call("EARNINGS", ttl=7 * 86400, symbol=ticker) or {}) if need_eps else {}
                for item in earnings.get("annualEarnings", []):
                    year = int(str(item.get("fiscalDateEnding", "0000"))[:4])
                    before = data.get(year, {}).get("eps")
                    put(year, "eps", item.get("reportedEPS"))
                    used = used or before is None and "eps" in data.get(year, {})
                if used:
                    sources.append("Alpha Vantage")
            except Exception:
                pass

    return data, ends, sources


def _av_client():
    try:
        import sys
        trader = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Agentic_Trader")
        if trader not in sys.path:
            sys.path.append(trader)
        from agentic_trader.market_apis.alpha_vantage import AlphaVantage
        return AlphaVantage()
    except Exception:
        return None


def year_end_prices(ticker, start, end):
    """{year: close on/before the last trading day of that year} (split-adjusted)."""
    import yfinance as yf
    try:
        hist = yf.Ticker(ticker).history(start=f"{start - 1}-12-01", auto_adjust=False)
    except Exception:
        return {}
    out = {}
    for stamp, close in hist["Close"].items():
        out[stamp.year] = float(close)
    return out


def price_series(ticker, start, end):
    import yfinance as yf
    try:
        hist = yf.Ticker(ticker).history(start=f"{start}-01-01", end=f"{end + 1}-01-01")
    except Exception:
        return []
    return [(stamp.to_pydatetime().replace(tzinfo=None), float(v)) for stamp, v in hist["Close"].items()]


def economic_series(function, start, end, av_client=None):
    av = av_client or _av_client()
    if av is None or not av.configured():
        return None, []
    kwargs = {"ttl": 86400}
    if function in {"CPI", "REAL_GDP", "FEDERAL_FUNDS_RATE", "TREASURY_YIELD"}:
        kwargs["interval"] = "monthly" if function != "REAL_GDP" else "annual"
    if function == "TREASURY_YIELD":
        kwargs.update(interval="monthly", maturity="10year")
    payload = av.call(function, **kwargs) or {}
    rows = []
    for item in payload.get("data", []):
        try:
            when = datetime.strptime(item["date"], "%Y-%m-%d")
            rows.append((when, float(item["value"])))
        except (KeyError, ValueError, TypeError):
            continue
    rows = sorted(r for r in rows if start <= r[0].year <= end)
    return payload.get("unit", ""), rows


def compute_fundamentals(ticker, spec, av_client=None):
    """Per-year values for each requested fundamental metric; returns (values, sources, notes)."""
    start, end = spec["start"], spec["end"]
    data, ends, sources = fetch_annual(ticker, start, end, av_client)
    prices = year_end_prices(ticker, start, end) if any(
        m in ("pe",) for m in spec["metrics"]) else {}
    if prices:
        sources.append("Yahoo Finance prices")
    values = {m: {} for m in spec["metrics"]}
    for year in range(start, end + 1):
        row = data.get(year, {})
        for m in spec["metrics"]:
            if m == "pe":
                eps = row.get("eps")
                price = prices.get(year)
                if eps and eps > 0 and price:
                    values[m][year] = price / eps
            elif m == "net_margin":
                if row.get("net_income") is not None and row.get("revenue"):
                    values[m][year] = row["net_income"] / row["revenue"] * 100
            elif m == "gross_margin":
                if row.get("gross_profit") is not None and row.get("revenue"):
                    values[m][year] = row["gross_profit"] / row["revenue"] * 100
            elif m in row:
                values[m][year] = row[m]
    return values, list(dict.fromkeys(sources)), data


# ---------- rendering ----------

BG, FG, GRID = "#0f1115", "#e8e8e8", "#2a2d34"
PALETTE = ["#4f8df5", "#f5a742", "#4fd18b", "#e0605e", "#b07cf0"]


def _fmt_money(value, _pos=None):
    v = abs(value)
    sign = "-" if value < 0 else ""
    if v >= 1e12:
        return f"{sign}${v / 1e12:.1f}T"
    if v >= 1e9:
        return f"{sign}${v / 1e9:.0f}B"
    if v >= 1e6:
        return f"{sign}${v / 1e6:.0f}M"
    return f"{sign}${v:,.0f}"


def _style(ax, title, subtitle):
    ax.set_facecolor(BG)
    ax.figure.patch.set_facecolor(BG)
    ax.set_title(title + "\n", color=FG, fontsize=15, fontweight="bold", loc="left")
    ax.text(0, 1.02, subtitle, transform=ax.transAxes, color="#9aa0aa", fontsize=9)
    ax.tick_params(colors=FG)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def _new_path():
    handle, path = tempfile.mkstemp(prefix="performance_chart_", suffix=".png")
    os.close(handle)
    return path


def render_fundamentals(spec, series, sources):
    """series: {ticker: {metric: {year: value}}}. Money -> bars (left), ratios/pct -> lines (right)."""
    metrics = spec["metrics"]
    bars = [m for m in metrics if METRICS[m][1] == "money"]
    lines = [m for m in metrics if METRICS[m][1] in ("ratio", "pct", "eps")]
    if not bars and lines:  # only ratios: draw them as the main lines
        primary_lines, secondary_lines = lines, []
    else:
        primary_lines, secondary_lines = [], lines
    years = list(range(spec["start"], spec["end"] + 1))
    tickers = spec["tickers"]
    title = f"{', '.join(tickers)}: " + " vs ".join(METRICS[m][0] for m in metrics)
    subtitle = f"{spec['start']}–{spec['end']} · Source: {', '.join(sources) or 'n/a'}"
    with _PLOT_LOCK:
        fig, ax = plt.subplots(figsize=(11, 6.2), dpi=130)
        try:
            _style(ax, title, subtitle)
            ax2 = None
            handles = []
            n_bars = max(1, len(bars) * len(tickers))
            width = 0.8 / n_bars
            color_i = 0
            slot = 0
            for ticker in tickers:
                for m in bars:
                    vals = [series[ticker][m].get(y) for y in years]
                    xs = [i - 0.4 + width * (slot + 0.5) for i in range(len(years))]
                    color = PALETTE[color_i % len(PALETTE)]
                    pts = [(x, v) for x, v in zip(xs, vals) if v is not None]
                    if pts:
                        b = ax.bar([p[0] for p in pts], [p[1] for p in pts], width=width * 0.92,
                                   color=color, label=f"{ticker} {METRICS[m][0]}")
                        handles.append(b)
                        for x, v in pts:
                            ax.text(x, v, _fmt_money(v), ha="center", va="bottom" if v >= 0 else "top",
                                    color=FG, fontsize=7)
                    slot += 1
                    color_i += 1
            if bars:
                ax.yaxis.set_major_formatter(FuncFormatter(_fmt_money))
                ax.set_ylabel(" / ".join(METRICS[m][0] for m in bars) + " ($)", color=FG)
            target_lines = secondary_lines or primary_lines
            if secondary_lines:
                ax2 = ax.twinx()
                for spine in ax2.spines.values():
                    spine.set_color(GRID)
                ax2.tick_params(colors=FG)
                line_ax = ax2
            else:
                line_ax = ax
            for ticker in tickers:
                for m in target_lines:
                    vals = [series[ticker][m].get(y) for y in years]
                    pts = [(i, v) for i, v in enumerate(vals) if v is not None]
                    if not pts:
                        continue
                    color = PALETTE[color_i % len(PALETTE)]
                    suffix = "x" if METRICS[m][1] == "ratio" else "%" if METRICS[m][1] == "pct" else ""
                    ln, = line_ax.plot([p[0] for p in pts], [p[1] for p in pts], color=color,
                                       marker="o", linewidth=2.2, label=f"{ticker} {METRICS[m][0]}")
                    handles.append(ln)
                    for x, v in pts:
                        line_ax.annotate(f"{v:.1f}{suffix}", (x, v), textcoords="offset points",
                                         xytext=(0, 9), ha="center", color=color, fontsize=8,
                                         bbox={"boxstyle": "round,pad=0.2", "fc": BG, "ec": "none", "alpha": 0.85})
                    color_i += 1
            if target_lines:
                labels = " / ".join(METRICS[m][0] for m in target_lines)
                line_ax.set_ylabel(labels, color=FG)
                if not primary_lines and line_ax is ax2:
                    line_ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:.0f}"
                                                      + ("x" if "pe" in target_lines else "")))
            ax.set_xticks(range(len(years)))
            ax.set_xticklabels([str(y) for y in years])
            ax.set_xlim(-0.6, len(years) - 0.4)
            labels = [h.get_label() for h in handles]
            if handles:
                leg = ax.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, -0.07),
                                ncol=min(4, len(handles)), facecolor=BG, edgecolor=GRID,
                                labelcolor=FG, fontsize=9)
                leg.set_zorder(10)
            fig.tight_layout()
            path = _new_path()
            fig.savefig(path, facecolor=BG)
            return path
        finally:
            plt.close(fig)


def render_timeseries(title, subtitle, curves, ylabel, pct=False):
    """curves: {label: [(datetime, value)]}"""
    with _PLOT_LOCK:
        fig, ax = plt.subplots(figsize=(11, 6.2), dpi=130)
        try:
            _style(ax, title, subtitle)
            for i, (label, pts) in enumerate(curves.items()):
                if pts:
                    ax.plot([p[0] for p in pts], [p[1] for p in pts], color=PALETTE[i % len(PALETTE)],
                            linewidth=2, label=label)
            ax.set_ylabel(ylabel, color=FG)
            if pct:
                ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:+.0f}%"))
            ax.legend(facecolor=BG, edgecolor=GRID, labelcolor=FG, fontsize=9)
            fig.autofmt_xdate()
            fig.tight_layout()
            path = _new_path()
            fig.savefig(path, facecolor=BG)
            return path
        finally:
            plt.close(fig)


# ---------- orchestration ----------

def _fmt_cell(metric, value):
    if value is None:
        return "n/a"
    kind = METRICS[metric][1]
    if kind == "money":
        return _fmt_money(value)
    if kind == "ratio":
        return f"{value:.1f}x"
    if kind == "pct":
        return f"{value:.1f}%"
    return f"{value:.2f}"


class ChartEngine:

    def __init__(self, av_client=None, lookup=None):
        self.av_client = av_client
        self.lookup = lookup

    def handle(self, message, conversation_key="default"):
        """Returns a result dict, or None when the message is not a chart request."""
        message = str(message or "")
        previous = _last_spec(conversation_key)
        if not is_chart_request(message):
            return None
        spec = build_spec(message, previous=previous, lookup=self.lookup)
        if not spec["tickers"] and not spec["economic"]:
            return {"status": "completed",
                    "response": ("Tell me what to chart, for example: "
                                 "`Chart AMZN EBITDA vs P/E ratio 2021-2025`, "
                                 "`Plot NVDA and AMD revenue since 2020`, or `Graph CPI since 2019`.")}
        try:
            result = self._build(spec)
        except Exception as error:
            return {"status": "completed",
                    "response": f"I couldn't build that chart: {error}"}
        if result.get("attachments"):
            _save_state(conversation_key, spec)
        return result

    def _build(self, spec):
        if spec["economic"]:
            return self._economic(spec)
        if set(spec["metrics"]) <= {"price", "return"}:
            return self._prices(spec)
        return self._fundamentals(spec)

    def overview(self, ticker, years=5):
        """EBITDA (net profit when EBITDA is unavailable, e.g. banks) vs P/E chart for one ticker.

        Returns {"path", "caption", "metric", "gaps"} or None when no data exists."""
        end = date.today().year - 1
        spec = {"tickers": [ticker], "metrics": ["ebitda", "pe"], "economic": [],
                "start": end - years + 1, "end": end}
        values, sources, _ = compute_fundamentals(ticker, spec, self.av_client)
        if not values["ebitda"]:
            spec["metrics"] = ["net_income", "pe"]
            values, sources, _ = compute_fundamentals(ticker, spec, self.av_client)
        if not values[spec["metrics"][0]]:
            return None
        series = {ticker: values}
        path = render_fundamentals(spec, series, list(dict.fromkeys(sources)))
        gaps = [str(y) for y in range(spec["start"], spec["end"] + 1) if y not in values["pe"]]
        return {"path": path, "metric": METRICS[spec["metrics"][0]][0], "gaps": gaps,
                "caption": f"{ticker}: {METRICS[spec['metrics'][0]][0]} vs P/E ratio "
                           f"({spec['start']}–{spec['end']})"}

    def _fundamentals(self, spec):
        series, sources, notes, rows = {}, [], [], []
        for ticker in spec["tickers"]:
            values, used, _data = compute_fundamentals(ticker, spec, self.av_client)
            series[ticker] = values
            sources += used
            for m in spec["metrics"]:
                missing = [str(y) for y in range(spec["start"], spec["end"] + 1) if y not in values[m]]
                if missing and len(missing) == len(range(spec["start"], spec["end"] + 1)):
                    notes.append(f"{ticker} {METRICS[m][0]}: no data available")
                elif missing:
                    notes.append(f"{ticker} {METRICS[m][0]}: no data for {', '.join(missing)}")
        if not any(v for s in series.values() for v in s.values()):
            raise ValueError("no financial data was returned for " + ", ".join(spec["tickers"]))
        sources = list(dict.fromkeys(sources))
        path = render_fundamentals(spec, series, sources)
        years = list(range(spec["start"], spec["end"] + 1))
        headers = ["Metric"] + [str(y) for y in years]
        for ticker in spec["tickers"]:
            for m in spec["metrics"]:
                label = f"{ticker} {METRICS[m][0]}" if len(spec["tickers"]) > 1 else METRICS[m][0]
                rows.append([label] + [_fmt_cell(m, series[ticker][m].get(y)) for y in years])
        text = (f"**{', '.join(spec['tickers'])}: " + " vs ".join(METRICS[m][0] for m in spec["metrics"])
                + f"** ({spec['start']}–{spec['end']})\n" + table(headers, rows)
                + f"\nSources: {', '.join(sources) or 'n/a'}.")
        if "pe" in spec["metrics"]:
            text += "\nP/E = fiscal year-end close ÷ diluted EPS (shown only when EPS is positive)."
        if notes:
            text += "\nGaps: " + "; ".join(notes) + "."
        text += "\nTip: ask me to \"add\" or \"remove\" a metric, or change the period, to update this chart."
        return self._result(text, path, "Chart: " + ", ".join(spec["tickers"]))

    def _prices(self, spec):
        curves = {}
        for ticker in spec["tickers"]:
            pts = price_series(ticker, spec["start"], spec["end"])
            if not pts:
                continue
            if "return" in spec["metrics"] or len(spec["tickers"]) > 1:
                base = pts[0][1]
                pts = [(d, (v / base - 1) * 100) for d, v in pts]
            curves[ticker] = pts
        if not curves:
            raise ValueError("no price history was returned for " + ", ".join(spec["tickers"]))
        is_return = "return" in spec["metrics"] or len(spec["tickers"]) > 1
        title = ("Total return: " if is_return else "Share price: ") + ", ".join(curves)
        path = render_timeseries(
            title, f"{spec['start']}–{spec['end']} · Source: Yahoo Finance",
            curves, "Change since start (%)" if is_return else "Close ($)", pct=is_return)
        rows = [[t, f"{p[0][1]:+.1f}%" if is_return else f"${p[0][1]:.2f}",
                 f"{p[-1][1]:+.1f}%" if is_return else f"${p[-1][1]:.2f}"] for t, p in curves.items()]
        text = (f"**{title}** ({spec['start']}–{spec['end']})\n"
                + table(["Ticker", "Start", "Latest"], rows) + "\nSource: Yahoo Finance.")
        missing = [t for t in spec["tickers"] if t not in curves]
        if missing:
            text += "\nNo price data for: " + ", ".join(missing) + "."
        return self._result(text, path, title)

    def _economic(self, spec):
        curves, units, sources = {}, [], "Alpha Vantage"
        for function in spec["economic"]:
            unit, rows = economic_series(function, spec["start"], spec["end"], self.av_client)
            if rows:
                curves[ECONOMIC[function][0]] = rows
                units.append(unit)
        if not curves:
            raise ValueError("Alpha Vantage returned no data (key missing or daily quota used)")
        title = " vs ".join(curves)
        path = render_timeseries(title, f"{spec['start']}–{spec['end']} · Source: {sources}",
                                 curves, units[0] if units else "")
        latest = [[k, v[-1][0].strftime("%Y-%m"), f"{v[-1][1]:.2f}"] for k, v in curves.items()]
        text = (f"**{title}** ({spec['start']}–{spec['end']})\n"
                + table(["Series", "Latest period", "Value"], latest) + f"\nSource: {sources}.")
        return self._result(text, path, title)

    @staticmethod
    def _result(text, path, caption):
        return {"status": "completed", "response": text, "chart": True,
                "attachments": [{"path": path, "filename": os.path.basename(path),
                                 "caption": caption, "type": "image"}]}
