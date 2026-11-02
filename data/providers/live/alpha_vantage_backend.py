"""Alpha Vantage as a live-market evidence backend: economic, forex, commodity, market-mover and stock/ETF data.

Only fires when the question is relevant (a ticker, a currency pair, an economic indicator, market movers), so
irrelevant questions cost no API requests. The free tier is small, so everything is cached in shared_storage and
counted against a daily budget (see agentic_trader.market_apis.alpha_vantage); premium-only endpoints are skipped
after the first refusal. Results are API data (rank 1, after the real-time Robinhood quote) and are never scraped.
"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

TRADER_DIR = Path(__file__).resolve().parents[3] / "Agentic_Trader"

CURRENCIES = {"USD", "EUR", "JPY", "GBP", "CHF", "CAD", "AUD", "NZD", "CNY", "MXN", "INR", "KRW", "BRL", "SEK", "NOK",
              "SGD", "HKD", "ZAR", "TRY", "BTC", "ETH"}
CURRENCY_WORDS = {"euro": "EUR", "yen": "JPY", "pound": "GBP", "sterling": "GBP", "swiss franc": "CHF", "franc": "CHF",
                  "canadian dollar": "CAD", "loonie": "CAD", "australian dollar": "AUD", "aussie": "AUD",
                  "new zealand dollar": "NZD", "yuan": "CNY", "renminbi": "CNY", "peso": "MXN", "rupee": "INR",
                  "bitcoin": "BTC", "ethereum": "ETH"}
FX_CONTEXT = re.compile(r"\b(forex|fx|currency|currencies|exchange rate|dollar|usd|vs|versus|against|strength|weak)\b", re.I)

# regex -> (function, params, label)
ECONOMIC = [
    (r"\b(cpi|inflation|consumer prices?|cost of living)\b", "CPI", {"interval": "monthly"}, "US CPI"),
    (r"\b(gdp|economic growth|recession)\b", "REAL_GDP", {"interval": "quarterly"}, "US real GDP"),
    (r"\b(unemployment|jobless|labor market|labour market)\b", "UNEMPLOYMENT", {}, "US unemployment rate"),
    (r"\b(payrolls?|jobs report|nonfarm)\b", "NONFARM_PAYROLL", {}, "US nonfarm payrolls"),
    (r"\b(fed funds|federal funds|interest rates?|rate cuts?|rate hikes?|fomc|the fed|federal reserve|monetary policy)\b",
     "FEDERAL_FUNDS_RATE", {"interval": "monthly"}, "Federal funds rate"),
    (r"\b(treasury|treasuries|yields?|bonds?|10[- ]?year)\b", "TREASURY_YIELD", {"interval": "monthly", "maturity": "10year"},
     "10-year Treasury yield"),
    (r"\bretail sales\b", "RETAIL_SALES", {}, "US retail sales"),
    (r"\b(oil|crude|wti)\b", "WTI", {"interval": "daily"}, "WTI crude oil"),
    (r"\bbrent\b", "BRENT", {"interval": "daily"}, "Brent crude oil"),
    (r"\bnatural gas\b", "NATURAL_GAS", {"interval": "daily"}, "Natural gas"),
    (r"\bcopper\b", "COPPER", {"interval": "monthly"}, "Copper"),
]
BROAD_ECONOMY = re.compile(r"\b(economy|economic|macro|macroeconomic|economic outlook|market outlook)\b", re.I)
BROAD_SET = ("CPI", "FEDERAL_FUNDS_RATE", "UNEMPLOYMENT")
MOVERS = re.compile(r"\b(top gainers?|top losers?|market movers?|biggest movers?|most active|gainers and losers)\b", re.I)
DOC = "https://www.alphavantage.co/documentation/#"
MAX_SERIES = 3


def _num(x, digits=2):
    try:
        return f"{float(x):,.{digits}f}"
    except (TypeError, ValueError):
        return str(x)


class AlphaVantageBackend:

    SOURCE = "Alpha Vantage"

    def __init__(self, client=None):
        self._client = client

    @property
    def client(self):
        if self._client is None:
            if str(TRADER_DIR) not in sys.path:
                sys.path.append(str(TRADER_DIR))
            from agentic_trader.market_apis.alpha_vantage import AlphaVantage
            self._client = AlphaVantage()
        return self._client

    # ---- relevance
    @staticmethod
    def forex_pairs(query):
        text = str(query or "")
        found = []
        for a, b in re.findall(r"\b([A-Za-z]{3})\s*[/\-]?\s*([A-Za-z]{3})\b", text):
            a, b = a.upper(), b.upper()
            if a in CURRENCIES and b in CURRENCIES and a != b and (a, b) not in found:
                found.append((a, b))
        if found:
            return found[:2]
        lower = text.lower()
        names = []
        for word, code in sorted(CURRENCY_WORDS.items(), key=lambda kv: -len(kv[0])):
            if re.search(rf"\b{re.escape(word)}s?\b", lower) and code not in names:
                names.append(code)
        if not names or not FX_CONTEXT.search(text):
            return []
        if len(names) == 1:
            names.append("USD" if names[0] != "USD" else "EUR")
        return [(names[0], names[1])]

    @staticmethod
    def economic_series(query):
        text = re.sub(r"\b(dividend|earnings|free cash flow|fcf) yields?\b|\byield on cost\b", " ", str(query or ""), flags=re.I)
        picked = [(fn, params, label) for rx, fn, params, label in ECONOMIC if re.search(rx, text, re.I)]
        if not picked and BROAD_ECONOMY.search(text):
            picked = [(fn, params, label) for _, fn, params, label in ECONOMIC if fn in BROAD_SET]
        seen, out = set(), []
        for item in picked:
            if item[0] not in seen:
                seen.add(item[0])
                out.append(item)
        return out[:MAX_SERIES]

    @staticmethod
    def symbol(company, query):
        if isinstance(company, dict):
            for key in ("ticker", "symbol"):
                value = company.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip().upper()
        m = re.search(r"\$([A-Za-z]{1,5})\b", str(query or ""))
        return m.group(1).upper() if m else None

    # ---- formatting
    @staticmethod
    def _result(title, summary, key, data):
        return {"title": f"{title} (Alpha Vantage)", "source": AlphaVantageBackend.SOURCE, "summary": summary,
                "published_at": datetime.now(timezone.utc).isoformat(), "source_type": "live_market",
                "no_scrape": True, "url": DOC + key, "data": data}

    def _series_result(self, fn, params, label):
        s = self.client.economic(fn, **params)
        rows = [r for r in s["rows"] if r.get("value") not in (None, ".", "")]
        if not rows:
            return None
        latest = rows[0]
        parts = [f"{label}: {_num(latest['value'])} {s['unit']} as of {latest['date']}"]
        if len(rows) > 1:
            prev = rows[1]
            change = float(latest["value"]) - float(prev["value"])
            parts.append(f"{change:+.2f} vs prior reading ({prev['date']})")
        if fn == "CPI" and len(rows) > 12:
            yoy = float(latest["value"]) / float(rows[12]["value"]) - 1
            parts.append(f"{yoy:+.1%} year over year")
        return self._result(label, "; ".join(parts) + ".", fn, {"series": fn, "latest": latest, "recent": rows[:6]})

    def _fx_result(self, a, b):
        r = self.client.fx_rate(a, b)
        if not r or not r.get("5. Exchange Rate"):
            return None
        rate = float(r["5. Exchange Rate"])
        text = (f"{a}/{b} exchange rate {rate:.4f} ({r.get('6. Last Refreshed', '')} UTC); "
                f"bid {_num(r.get('8. Bid Price'), 4)}, ask {_num(r.get('9. Ask Price'), 4)}.")
        return self._result(f"{a}/{b} exchange rate", text, "CURRENCY_EXCHANGE_RATE",
                            {"pair": f"{a}/{b}", "rate": rate, "as_of": r.get("6. Last Refreshed")})

    def _movers_result(self):
        d = self.client.movers()
        if not d or not d.get("top_gainers"):
            return None

        def fmt(rows):
            return ", ".join(f"{x['ticker']} {x['change_percentage']}" for x in rows[:5])
        text = (f"US market movers ({d.get('last_updated', '')}): top gainers {fmt(d['top_gainers'])}; "
                f"top losers {fmt(d.get('top_losers', []))}; most active {fmt(d.get('most_actively_traded', []))}.")
        return self._result("US market movers", text, "TOP_GAINERS_LOSERS", {"last_updated": d.get("last_updated")})

    def _stock_results(self, symbol, company):
        out = []
        q = self.client.quote(symbol)
        if q and q.get("05. price"):
            text = (f"{symbol} last price ${_num(q['05. price'])} ({q.get('10. change percent', '')} on "
                    f"{q.get('07. latest trading day', '')}), previous close ${_num(q.get('08. previous close'))}, "
                    f"volume {int(float(q.get('06. volume') or 0)):,}. Delayed API data: prefer the real-time broker quote.")
            out.append(self._result(f"{symbol} quote", text, "GLOBAL_QUOTE", {"symbol": symbol, "price": float(q["05. price"])}))
        is_etf = isinstance(company, dict) and company.get("entity_type") == "etf"
        o = self.client.etf_profile(symbol) if is_etf else self.client.overview(symbol)
        if o and is_etf:
            top = ", ".join(f"{h.get('symbol')} {float(h.get('weight', 0)):.1%}" for h in (o.get("holdings") or [])[:5])
            out.append(self._result(f"{symbol} ETF profile",
                                    f"{symbol} net assets ${_num(o.get('net_assets'), 0)}, expense ratio {o.get('net_expense_ratio')}, "
                                    f"top holdings {top}.", "ETF_PROFILE", {"symbol": symbol}))
        elif o:
            text = (f"{symbol} {o.get('Name', '')}: sector {o.get('Sector')}, industry {o.get('Industry')}; P/E {o.get('PERatio')}, "
                    f"forward P/E {o.get('ForwardPE')}, EPS {o.get('EPS')}, profit margin {o.get('ProfitMargin')}, "
                    f"analyst target ${o.get('AnalystTargetPrice')}, beta {o.get('Beta')}, 52-week range "
                    f"${o.get('52WeekLow')}-${o.get('52WeekHigh')}.")
            out.append(self._result(f"{symbol} fundamentals", text, "OVERVIEW", {"symbol": symbol}))
        return out

    # ---- entry point used by LiveMarketProvider and the generic evidence path
    def search(self, company, query):
        if not self.client.configured():
            return []
        jobs = []
        symbol = self.symbol(company, query)
        if symbol:
            jobs.append(lambda: self._stock_results(symbol, company))
        for a, b in self.forex_pairs(query):
            jobs.append(lambda a=a, b=b: [self._fx_result(a, b)])
        for fn, params, label in self.economic_series(query):
            jobs.append(lambda fn=fn, params=params, label=label: [self._series_result(fn, params, label)])
        if MOVERS.search(str(query or "")):
            jobs.append(lambda: [self._movers_result()])
        results = []
        for job in jobs:
            try:
                results.extend(r for r in job() if r)
            except Exception as exc:
                print("ALPHA VANTAGE SKIPPED:", repr(exc))
        return results
