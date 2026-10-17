"""Compares quant values and cross-referenced evidence across every ticker in a comparison request."""
from orchestrator.quant_evidence_builder import headline_tone
from orchestrator.quant_summary_reviewer import _number, _stance, _value

RATING_KEYS = (
    ("recommendation", "model recommendation"),
    ("predictive_rating", "predictive rating"),
    ("forecast_rating", "forecast rating"),
    ("forecast_consensus", "forecast consensus"),
    ("momentum_rating", "momentum"),
    ("financial_strength_rating", "financial strength"),
    ("stability_rating", "stability"),
)

# (metric key, label, higher is better)
NUMERIC_DIMENSIONS = (
    ("forecast_30d", "30-day forecast", True),
    ("forecast_90d", "90-day forecast", True),
    ("prediction_pct", "model predicted move", True),
    ("beta", "beta (lower = steadier)", False),
)


def _pct(value):
    return f"{value:+.1f}%"


class QuantComparisonReviewer:

    def build(self, company_metrics, evidence_by_ticker=None):
        """Return a 'Quant Comparison Summary' section, or '' when fewer than two tickers have quant data."""
        if not isinstance(company_metrics, dict):
            return ""
        evidence_by_ticker = evidence_by_ticker if isinstance(evidence_by_ticker, dict) else {}
        profiles = {
            ticker: self._profile(metrics, evidence_by_ticker.get(ticker) or {})
            for ticker, metrics in company_metrics.items()
            if isinstance(metrics, dict) and metrics
        }
        profiles = {t: p for t, p in profiles.items() if p["quant_votes"] or p["checks"]}
        if len(profiles) < 2:
            return ""

        lines = ["**Quant Comparison Summary**"]
        lines += self._dimension_lines(company_metrics, profiles)
        lines += self._ticker_lines(profiles)
        lines.append(self._verdict(profiles))
        return "\n".join(lines)

    def _profile(self, metrics, evidence):
        votes = [
            (label, _stance(_value(metrics, key)))
            for key, label in RATING_KEYS
            if _value(metrics, key) not in (None, "", "N/A")
        ]
        checks = self._cross_checks(evidence)
        quant_score = sum(v for _, v in votes)
        check_score = sum(v for _, v in checks)
        return {
            "quant_votes": votes,
            "checks": checks,
            "quant_score": quant_score,
            "check_score": check_score,
            "total": quant_score + check_score,
            "evidence": evidence,
            "metrics": metrics,
        }

    @staticmethod
    def _cross_checks(evidence):
        checks = []
        analysts = evidence.get("analysts")
        if analysts and analysts.get("n"):
            net = (analysts["buy"] - analysts["sell"]) / analysts["n"]
            checks.append(("analyst ratings", 1 if net > 0.3 else -1 if net < 0 else 0))
        upside = _number(evidence.get("target_upside"))
        if upside is not None:
            checks.append(("price target", 1 if upside > 5 else -1 if upside < -5 else 0))
        live = evidence.get("live_quant") or {}
        signal = _number(live.get("signal_score"))
        if signal is not None:
            checks.append(("live signal", 1 if signal > 0.15 else -1 if signal < -0.15 else 0))
        web = evidence.get("web") or []
        if web:
            tone = sum(headline_tone(item.get("text") or item.get("title")) for item in web)
            checks.append(("headline tone", 1 if tone > 0 else -1 if tone < 0 else 0))
        return checks

    def _dimension_lines(self, company_metrics, profiles):
        lines = []
        for key, label, higher_better in NUMERIC_DIMENSIONS:
            values = {
                t: _number(_value(company_metrics[t], key))
                for t in profiles
            }
            values = {t: v for t, v in values.items() if v is not None}
            if len(values) < 2:
                continue
            ranked = sorted(values, key=values.get, reverse=higher_better)
            fmt = (lambda v: f"{v:.2f}") if key == "beta" else _pct
            lines.append(
                f"- **{label.capitalize()}:** " + " > ".join(f"{t} ({fmt(values[t])})" for t in ranked)
            )

        upsides = {
            t: _number(p["evidence"].get("target_upside")) for t, p in profiles.items()
        }
        upsides = {t: v for t, v in upsides.items() if v is not None}
        if len(upsides) >= 2:
            ranked = sorted(upsides, key=upsides.get, reverse=True)
            lines.append(
                "- **Analyst price-target upside (Robinhood):** "
                + " > ".join(f"{t} ({_pct(upsides[t])})" for t in ranked)
            )

        for key, label in (("financial_strength_rating", "Financial strength"), ("momentum_rating", "Momentum")):
            grouped = {t: _value(company_metrics[t], key) for t in profiles}
            grouped = {t: v for t, v in grouped.items() if v not in (None, "", "N/A")}
            if len(grouped) >= 2:
                lines.append(f"- **{label}:** " + ", ".join(f"{t} {v}" for t, v in grouped.items()))
        return lines

    def _ticker_lines(self, profiles):
        lines = []
        for ticker, p in sorted(profiles.items(), key=lambda item: item[1]["total"], reverse=True):
            positives = [l for l, v in p["quant_votes"] + p["checks"] if v > 0]
            negatives = [l for l, v in p["quant_votes"] + p["checks"] if v < 0]
            parts = []
            if positives:
                parts.append("supportive: " + ", ".join(positives))
            if negatives:
                parts.append("cautionary: " + ", ".join(negatives))
            live = p["evidence"].get("live_quant") or {}
            ic, hit = _number(live.get("ic")), _number(live.get("hit_rate"))
            if (ic is not None and ic < 0.03) or (hit is not None and hit < 0.52):
                parts.append("live model shows little predictive edge, so treat its call with caution")
            agree = sum(1 for _, v in p["checks"] if v > 0), sum(1 for _, v in p["checks"] if v < 0)
            cross = (
                f"cross-reference: {agree[0]} supportive / {agree[1]} cautionary"
                if p["checks"] else "no cross-reference data"
            )
            lines.append(
                f"- **{ticker}** (quant {p['quant_score']:+d}, cross-reference {p['check_score']:+d}): "
                + "; ".join(parts + [cross])
            )
        return lines

    def _verdict(self, profiles):
        ranked = sorted(profiles.items(), key=lambda item: item[1]["total"], reverse=True)
        top, bottom = ranked[0], ranked[-1]
        if top[1]["total"] == bottom[1]["total"]:
            return ("**Cross-ticker verdict:** the quant values and cross-referenced evidence do not separate "
                    "these tickers; none shows a clear edge.")
        confirmed = top[1]["quant_score"] > 0 and top[1]["check_score"] > 0
        text = (
            f"**Cross-ticker verdict:** {top[0]} has the strongest combined signal "
            f"({top[1]['total']:+d}) and {bottom[0]} the weakest ({bottom[1]['total']:+d}). "
        )
        text += (
            f"{top[0]}'s quant lean is confirmed by independent evidence."
            if confirmed else
            f"{top[0]}'s lead rests mostly on "
            f"{'the quant model' if top[1]['quant_score'] >= top[1]['check_score'] else 'cross-referenced evidence'}"
            ", so treat it as a tentative edge."
        )
        return text
