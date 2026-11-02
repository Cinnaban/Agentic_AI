"""World Bank Open Data as an evidence backend for country, political, demographic and global economic queries.

No key needed. Fires only when a country (or an explicit global/world scope) is combined with an economic,
demographic or governance topic, so unrelated questions cost no requests. Results are API data (rank 1, below the
real-time Robinhood quote) and are never scraped.
"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

TRADER_DIR = Path(__file__).resolve().parents[3] / "Agentic_Trader"

ALIASES = {"US": "US", "USA": "US", "AMERICA": "US", "UNITED STATES": "US", "UK": "GB", "BRITAIN": "GB",
           "ENGLAND": "GB", "RUSSIA": "RU", "SOUTH KOREA": "KR", "KOREA": "KR", "VIETNAM": "VN", "IRAN": "IR",
           "EGYPT": "EG", "TURKEY": "TR", "TURKIYE": "TR", "TAIWAN": "TW", "HONG KONG": "HK", "UAE": "AE",
           "CZECHIA": "CZ", "VENEZUELA": "VE", "SYRIA": "SY", "LAOS": "LA", "SLOVAKIA": "SK", "KYRGYZSTAN": "KG"}
AMBIGUOUS = {"GEORGIA", "JORDAN", "CHAD", "NIGER", "TURKEY", "MALTA"}  # also common non-country words/places

# regex -> (indicator code, label, kind) ; kind picks number formatting
INDICATORS = [
    (r"\b(gdp growth|economic growth|growth rate|recession)\b", "NY.GDP.MKTP.KD.ZG", "GDP growth", "pct"),
    (r"\b(gdp|output|economy size|economic size)\b", "NY.GDP.MKTP.CD", "GDP (current US$)", "usd"),
    (r"\b(gdp per capita|income per capita|living standards?|wealth|rich|poor)\b", "NY.GDP.PCAP.CD", "GDP per capita (US$)", "usd"),
    (r"\b(inflation|cpi|prices|cost of living)\b", "FP.CPI.TOTL.ZG", "Inflation (CPI)", "pct"),
    (r"\b(unemployment|jobless|jobs|labou?r)\b", "SL.UEM.TOTL.ZS", "Unemployment", "pct"),
    (r"\b(population|demograph\w*|people|inhabitants)\b", "SP.POP.TOTL", "Population", "num"),
    (r"\b(pop(ulation)? growth|birth rate|fertility|demograph\w*)\b", "SP.POP.GROW", "Population growth", "pct"),
    (r"\b(life expectancy|aging|ageing|health)\b", "SP.DYN.LE00.IN", "Life expectancy (years)", "dec"),
    (r"\b(urban\w*|cities)\b", "SP.URB.TOTL.IN.ZS", "Urban population share", "pct"),
    (r"\b(debt|deficit|fiscal)\b", "GC.DOD.TOTL.GD.ZS", "Central government debt (% of GDP)", "pct"),
    (r"\b(trade|exports?|imports?|tariffs?)\b", "NE.TRD.GNFS.ZS", "Trade (% of GDP)", "pct"),
    (r"\b(foreign investment|fdi)\b", "BX.KLT.DINV.WD.GD.ZS", "Foreign direct investment, net inflows (% of GDP)", "pct"),
    (r"\b(interest rates?|lending rate)\b", "FR.INR.LEND", "Lending interest rate", "pct"),
    (r"\b(exchange rate|currency)\b", "PA.NUS.FCRF", "Official exchange rate (LCU per US$)", "dec"),
    (r"\b(market cap\w*|stock market|equity market)\b", "CM.MKT.LCAP.GD.ZS", "Listed companies' market cap (% of GDP)", "pct"),
    (r"\b(political|politics|stability|governance|government|corruption|rule of law|regime|geopolit\w*|risk)\b",
     "GOV_WGI_PV.EST", "Political stability index (-2.5 weak to 2.5 strong)", "dec"),
    (r"\b(political|politics|governance|government|regime)\b", "GOV_WGI_GE.EST", "Government effectiveness index (-2.5 to 2.5)", "dec"),
    (r"\b(corruption|governance|political)\b", "GOV_WGI_CC.EST", "Control of corruption index (-2.5 to 2.5)", "dec"),
]
BROAD = ("NY.GDP.MKTP.KD.ZG", "FP.CPI.TOTL.ZG", "SL.UEM.TOTL.ZS")  # "country" / "economy" with no specific topic
COUNTRY_TOPIC = re.compile(r"\b(country|nation|economy|economic|political|politics|market|markets|invest\w*|risk|outlook)\b", re.I)
GLOBAL_SCOPE = re.compile(r"\b(global|world|worldwide|international|emerging markets?)\b", re.I)
MAX_SERIES = 4
MAX_COUNTRIES = 3
DOC = "https://data.worldbank.org/indicator/"


def _fmt(value, kind):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if kind == "pct":
        return f"{v:.2f}%"
    if kind == "usd":
        for div, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
            if abs(v) >= div:
                return f"${v / div:,.2f}{suffix}"
        return f"${v:,.0f}"
    if kind == "num":
        return f"{v:,.0f}"
    return f"{v:,.2f}"


class WorldBankBackend:

    SOURCE = "World Bank"

    def __init__(self, client=None):
        self._client = client

    @property
    def client(self):
        if self._client is None:
            if str(TRADER_DIR) not in sys.path:
                sys.path.append(str(TRADER_DIR))
            from agentic_trader.market_apis.world_bank import WorldBank
            self._client = WorldBank()
        return self._client

    # ---- relevance
    def find_countries(self, query):
        text = str(query or "")
        upper = text.upper()
        found, spans = [], []
        names = dict(ALIASES)
        for iso, name in self.client.countries().items():
            names.setdefault(name.upper(), iso)
        for name in sorted(names, key=len, reverse=True):
            iso = names[name]
            if name in AMBIGUOUS and not re.search(r"\b(in|of|for|to|from)\s+" + name.title() + r"\b", text):
                continue
            if len(name) <= 3:  # short aliases only match as capitalised words (US, UK, UAE)
                m = re.search(r"\b" + name + r"\b", text)
            else:
                m = re.search(r"\b" + re.escape(name) + r"\b", upper)
            if m and not any(s <= m.start() < e for s, e in spans) and iso not in found:
                spans.append((m.start(), m.end()))
                found.append(iso)
        return found[:MAX_COUNTRIES]

    @staticmethod
    def indicators(query):
        text = str(query or "")
        picked, seen = [], set()
        for pattern, code, label, kind in INDICATORS:
            if re.search(pattern, text, re.I) and code not in seen:
                seen.add(code)
                picked.append((code, label, kind))
        if not picked and COUNTRY_TOPIC.search(text):
            lookup = {c: (c, l, k) for _, c, l, k in INDICATORS}
            picked = [lookup[c] for c in BROAD]
        return picked[:MAX_SERIES]

    # ---- formatting
    def _result(self, iso, name, series):
        lines = []
        for label, kind, rows in series:
            latest = rows[0]
            line = f"{label}: {_fmt(latest['value'], kind)} ({latest['date']})"
            if len(rows) > 1:
                line += f"; {rows[1]['date']}: {_fmt(rows[1]['value'], kind)}; {rows[-1]['date']}: {_fmt(rows[-1]['value'], kind)}"
            lines.append(line)
        return {"title": f"{name} economic, demographic and governance indicators (World Bank)",
                "source": self.SOURCE, "summary": f"{name}: " + " | ".join(lines),
                "published_at": datetime.now(timezone.utc).isoformat(), "source_type": "live_market", "no_scrape": True,
                "url": f"https://data.worldbank.org/country/{iso.lower()}",
                "data": {"country": iso, "indicators": [{"label": l, "rows": r} for l, _, r in series]}}

    # ---- entry point used by LiveMarketProvider and the generic evidence path
    def search(self, company, query):
        text = str(query or "")
        indicators = self.indicators(text)
        if not indicators:
            return []
        countries = self.find_countries(text)
        if not countries and GLOBAL_SCOPE.search(text):
            countries = ["WLD"]
        results = []
        for iso in countries:
            series = []
            for code, label, kind in indicators:
                try:
                    data = self.client.indicator(iso, code)
                except Exception as exc:
                    print("WORLD BANK SKIPPED:", repr(exc))
                    continue
                if data and data.get("rows"):
                    series.append((label, kind, data["rows"]))
            if series:
                name = (data or {}).get("country") or self.client.countries().get(iso, iso)
                results.append(self._result(iso, name, series))
        return results
