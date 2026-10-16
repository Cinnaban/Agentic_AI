"""Explains why each quant metric reads bullish/bearish/good/hold, cross-checked against independent evidence.

Evidence (Robinhood market data, Firecrawl/news pages) comes from QuantEvidenceBuilder; without it the
review falls back to explaining the quant values alone.
"""
from orchestrator.quant_evidence_builder import headline_tone

POSITIVE = {"bullish", "buy", "excellent", "good", "strong", "high"}
NEGATIVE = {"bearish", "sell", "poor", "weak", "low"}
HORIZONS = (
    ("forecast_5d", "5-day"),
    ("forecast_30d", "30-day"),
    ("forecast_90d", "90-day"),
    ("forecast_180d", "180-day"),
)
WORD = {1: "bullish", -1: "bearish", 0: "neutral"}


def _value(metrics, key):
    metric = metrics.get(key)
    return metric.get("value") if isinstance(metric, dict) else None


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _tone(value):
    tokens = str(value).strip().lower().split()
    if any(t in NEGATIVE for t in tokens):
        return "negative"
    if any(t in POSITIVE for t in tokens):
        return "positive"
    return "neutral"


def _stance(value):
    return {"positive": 1, "negative": -1, "neutral": 0}[_tone(value)]


def _sign(value):
    return "positive" if value > 0 else "negative" if value < 0 else "flat"


def _verdict(stance, model):
    if stance == 0 or model == 0:
        return "neutral"
    return "agrees" if stance == model else "conflicts"


class QuantSummaryReviewer:

    def build(self, metrics, evidence=None):
        """Return a 'Quant Summary Review' section, or '' when there are no quant metrics."""
        if not isinstance(metrics, dict):
            return ""
        evidence = evidence if isinstance(evidence, dict) else {}
        self.model = self._model_direction(metrics)
        self.tally = []

        lines = []
        for builder in (
            self._recommendation,
            self._forecast_curve,
            self._forecast_signals,
            self._momentum,
            self._stability,
            self._financial_strength,
            self._catalysts,
            self._conflicts,
            self._cross_reference_verdict,
        ):
            line = builder(metrics, evidence)
            if line:
                lines.append(line)

        if not lines:
            return ""
        return "**Quant Summary Review**\n\n" + "\n".join(f"- {line}" for line in lines)

    # ---- helpers
    @staticmethod
    def _model_direction(metrics):
        rec = _value(metrics, "recommendation")
        if rec is not None and _stance(rec) != 0:
            return _stance(rec)
        prediction = _number(_value(metrics, "prediction_pct"))
        if prediction:
            return 1 if prediction > 0 else -1
        return 0

    def _record(self, label, stance):
        self.tally.append((label, _verdict(stance, self.model)))

    def _analyst_stance(self, evidence):
        a = evidence.get("analysts")
        if not a:
            return None
        net = (a["buy"] - a["sell"]) / a["n"]
        return 1 if net > 0.3 else -1 if net < 0 else 0

    def _cross_checks(self, evidence, which):
        """Cross-check sentences for the given topics, each tagged with its source."""
        notes = []
        a = evidence.get("analysts")
        live = evidence.get("live_quant") or {}

        if "analysts" in which and a:
            stance = self._analyst_stance(evidence)
            notes.append(
                f"Robinhood analysts are {a['buy'] / a['n']:.0%} Buy / {a['hold'] / a['n']:.0%} Hold / "
                f"{a['sell'] / a['n']:.0%} Sell ({a['n']} ratings), a {WORD[stance]} read that "
                f"{self._phrase(stance)}"
            )
            self._record("analyst ratings", stance)

        up = evidence.get("target_upside")
        if "target" in which and up is not None:
            stance = 1 if up > 0.05 else -1 if up < -0.05 else 0
            notes.append(
                f"the mean analyst price target is {up:+.1%} from the current price, a {WORD[stance]} read that "
                f"{self._phrase(stance)}"
            )
            self._record("price target", stance)

        score = live.get("signal_score")
        if "signal" in which and score is not None:
            stance = 1 if score > 0.15 else -1 if score < -0.15 else 0
            notes.append(
                f"Robinhood's live intraday signal is {score:+.2f} ({WORD[stance]}), which "
                f"{self._phrase(stance)}"
            )
            self._record("live signal", stance)

        ic, hit = live.get("ic"), live.get("hit_rate")
        if "trust" in which and ic is not None and hit is not None:
            if ic < 0.03 or hit < 0.52:
                notes.append(
                    f"the walk-forward test on live bars shows little predictive edge (IC {ic:+.2f}, hit rate "
                    f"{hit:.0%}), so the model's direction deserves low trust"
                )
            else:
                notes.append(
                    f"the walk-forward test on live bars shows some edge (IC {ic:+.2f}, hit rate {hit:.0%}), "
                    "which lends moderate support"
                )

        if "momentum" in which and live:
            notes += self._momentum_notes(evidence, live)
        if "volatility" in which and live:
            notes += self._volatility_notes(live)
        if "headlines" in which:
            note = self._headline_note(evidence)
            if note:
                notes.append(note)
        return notes

    def _phrase(self, stance):
        if stance == 0 or self.model == 0:
            return "does not strongly confirm or contradict the model"
        return "supports the model's call" if stance == self.model else "contradicts the model's call"

    @staticmethod
    def _momentum_notes(evidence, live):
        notes = []
        rsi = live.get("rsi14")
        if rsi is not None:
            state = ("stretched/overbought, so further upside may be limited" if rsi >= 70 else
                     "oversold, so a bounce is plausible" if rsi <= 30 else "in a neutral range")
            notes.append(f"live RSI is {rsi:.0f}, {state}")
        vwap = live.get("vwap_dev_pct")
        if vwap is not None:
            notes.append(f"price is {vwap:+.2%} versus VWAP, {'above' if vwap > 0 else 'below'} the day's average trade")
        change = evidence.get("change_pct")
        if change is not None:
            notes.append(f"the stock is {change:+.2%} versus the previous close")
        return notes

    @staticmethod
    def _volatility_notes(live):
        notes = []
        vol, beta = live.get("realized_vol_ann"), live.get("beta_vs_spy")
        if vol is not None:
            notes.append(f"live realized volatility is {vol:.0%} annualized")
        if beta is not None:
            notes.append(
                f"beta versus SPY is {beta:.2f}, so the stock "
                + ("has tended to move opposite the market" if beta < 0 else
                   "amplifies market moves" if beta > 1.1 else
                   "dampens market moves" if beta < 0.9 else "tracks market moves")
            )
        return notes

    def _headline_note(self, evidence):
        web = evidence.get("web") or []
        if not web:
            return ""
        tones = [(item, headline_tone(item.get("text"))) for item in web]
        pos = sum(1 for _, t in tones if t > 0)
        neg = sum(1 for _, t in tones if t < 0)
        stance = 1 if pos > neg else -1 if neg > pos else 0
        fire = sum(1 for item in web if item.get("via") == "Firecrawl")
        cited = next((item for item, t in tones if t == stance and stance != 0), None) or web[0]
        origin = f"{len(web)} sources" + (f", {fire} scraped with Firecrawl" if fire else "")
        note = (
            f"recent coverage ({origin}) leans {WORD[stance]} ({pos} positive / {neg} negative), a read that "
            f"{self._phrase(stance)}; e.g. \"{cited['title'][:90]}\" ({cited['source']})"
        )
        self._record("headline tone", stance)
        return note

    @staticmethod
    def _join(notes):
        return (" Cross-check: " + "; ".join(notes) + ".") if notes else ""

    # ---- key points
    def _recommendation(self, metrics, evidence):
        rec = _value(metrics, "recommendation")
        prediction = _number(_value(metrics, "prediction_pct"))
        confidence = _number(_value(metrics, "confidence"))
        if rec is None and prediction is None:
            return ""

        parts = []
        if rec is not None:
            parts.append(f"**Model Recommendation: {rec}**")
        if prediction is not None:
            parts.append(
                f"the model's next-period prediction is {prediction:+.2f}%, "
                f"a {_sign(prediction)} expected move"
            )
        text = " - ".join(parts) + "."
        if confidence is not None:
            if confidence < 5:
                text += (
                    f" Confidence is only {confidence:.2f}%, so treat this as a very weak "
                    "signal that statistically is close to noise."
                )
            elif confidence < 30:
                text += f" Confidence of {confidence:.2f}% is low; the call should not be relied on alone."
            elif confidence < 60:
                text += f" Confidence of {confidence:.2f}% is moderate."
            else:
                text += f" Confidence of {confidence:.2f}% is relatively high."
        return text + self._join(self._cross_checks(evidence, ("analysts", "signal", "trust", "headlines")))

    def _forecast_curve(self, metrics, evidence):
        points = [(label, _number(_value(metrics, key))) for key, label in HORIZONS]
        points = [(label, v) for label, v in points if v is not None]
        if not points:
            return ""

        shape = ", ".join(f"{label} {v:+.2f}%" for label, v in points)
        signs = {_sign(v) for _, v in points}
        if signs == {"positive"}:
            verdict = "every horizon is positive, which supports a bullish drift."
        elif signs == {"negative"}:
            verdict = "every horizon is negative, which supports a bearish drift."
        else:
            weakest = min(points, key=lambda p: p[1])
            verdict = (
                "horizons disagree, so there is no consistent direction; "
                f"the weakest point is {weakest[0]} ({weakest[1]:+.2f}%), "
                "which is why the call leans to hold rather than act."
            )
        return f"**Forecast horizons:** {shape} - {verdict}" + self._join(self._cross_checks(evidence, ("target",)))

    def _forecast_signals(self, metrics, evidence):
        rating = _value(metrics, "forecast_rating")
        consensus = _value(metrics, "forecast_consensus")
        predictive = _value(metrics, "predictive_rating")
        if rating is None and consensus is None and predictive is None:
            return ""

        parts = []
        if rating is not None:
            parts.append(f"Forecast Rating {rating} reflects the near-term forecast direction")
        if consensus is not None:
            if str(consensus).strip().lower() == "mixed":
                parts.append("Forecast Consensus is Mixed because the individual forecasts do not agree")
            else:
                parts.append(f"Forecast Consensus is {consensus}, meaning the forecasts largely agree")
        if predictive is not None:
            if str(predictive).strip().lower() == "hold":
                parts.append(
                    "Predictive Rating Hold means model accuracy and edge are not strong enough to justify "
                    "a directional bet"
                )
            else:
                parts.append(f"Predictive Rating {predictive} summarizes how much to trust the model's edge")
        return "**Forecast signals:** " + "; ".join(parts) + "."

    def _momentum(self, metrics, evidence):
        rating = _value(metrics, "momentum_rating")
        if rating is None:
            return ""
        meaning = {
            "positive": "price trend and recent returns are strong, a bullish technical input",
            "negative": "price trend and recent returns are weak, a bearish technical input",
            "neutral": "price trend is unremarkable, a neutral technical input",
        }[_tone(rating)]
        text = (f"**Momentum {rating}:** {meaning}. Momentum describes the past trend and does not by itself "
                "predict future returns.")
        return text + self._join(self._cross_checks(evidence, ("momentum",)))

    def _stability(self, metrics, evidence):
        rating = _value(metrics, "stability_rating")
        if rating is None:
            return ""
        meaning = {
            "positive": "price swings and drawdowns have been contained, so a bad outcome is less likely to be sudden",
            "negative": "price swings and drawdowns have been large, which adds risk to any position",
            "neutral": "volatility is average",
        }[_tone(rating)]
        return f"**Stability {rating}:** {meaning}." + self._join(self._cross_checks(evidence, ("volatility",)))

    def _financial_strength(self, metrics, evidence):
        rating = _value(metrics, "financial_strength_rating")
        if rating is None:
            return ""
        tone = _tone(rating)
        meaning = {
            "positive": "the balance sheet, profitability and cash flow support the business",
            "negative": "the balance sheet, leverage or profitability is a weak point",
            "neutral": "the balance sheet is adequate without clear strengths",
        }[tone]
        text = f"**Financial Strength {rating}:** {meaning}."
        return text + self._join(self._sec_notes(metrics, tone))

    @staticmethod
    def _sec_notes(metrics, tone):
        """Reported figures (SEC) that explain, or contradict, the financial-strength rating."""
        notes = []
        equity = _number(_value(metrics, "stockholders_equity"))
        income = _number(_value(metrics, "net_income"))
        operating = _number(_value(metrics, "operating_income"))
        revenue = _number(_value(metrics, "revenue"))
        assets = _number(_value(metrics, "assets"))
        liabilities = _number(_value(metrics, "liabilities"))
        if equity is not None and equity < 0:
            notes.append("SEC filings show negative stockholders' equity (liabilities exceed assets), a key weakness")
        if assets and liabilities:
            ratio = liabilities / assets
            notes.append(f"SEC liabilities are {ratio:.0%} of assets"
                         + (", a heavy debt load" if ratio > 0.75 else ""))
        if revenue and income is not None:
            margin = income / revenue
            notes.append(f"net margin is {margin:.0%}"
                         + (" which shows the business is profitable despite the rating"
                            if tone == "negative" and margin > 0.10 else ""))
        elif operating is not None and operating < 0:
            notes.append("operating income is negative, so the business is not covering its costs")
        return notes

    def _catalysts(self, metrics, evidence):
        earnings = evidence.get("next_earnings")
        if not earnings:
            return ""
        return (f"**Upcoming catalyst:** Robinhood lists the next earnings report on {earnings}. Earnings can "
                "move a stock far more than the quant forecast implies, so signals made before the report carry "
                "extra uncertainty.")

    def _conflicts(self, metrics, evidence):
        """Call out when quality ratings and the model's directional call disagree."""
        rec = _value(metrics, "recommendation")
        if rec is None or self.model == 0:
            return ""

        opposing = []
        for key, label in (
            ("momentum_rating", "Momentum"),
            ("stability_rating", "Stability"),
            ("forecast_rating", "Forecast Rating"),
            ("financial_strength_rating", "Financial Strength"),
        ):
            rating = _value(metrics, key)
            if rating is not None and _stance(rating) not in (0, self.model):
                opposing.append(f"{label} ({rating})")

        if not opposing:
            return ""
        return (
            f"**Mixed signals:** the model recommendation is {rec}, but {', '.join(opposing)} "
            f"{'points' if len(opposing) == 1 else 'point'} the other way. "
            "A split like this usually means waiting for confirmation instead of acting on one input."
        )

    def _cross_reference_verdict(self, metrics, evidence):
        """One-line tally of how many independent checks agree with the quant model."""
        if not self.tally or self.model == 0:
            return ""
        unique = list(dict.fromkeys(self.tally))
        agree = [n for n, v in unique if v == "agrees"]
        conflict = [n for n, v in unique if v == "conflicts"]
        neutral = [n for n, v in unique if v == "neutral"]
        parts = []
        if agree:
            parts.append(f"{len(agree)} agree ({', '.join(agree)})")
        if conflict:
            parts.append(f"{len(conflict)} conflict ({', '.join(conflict)})")
        if neutral:
            parts.append(f"{len(neutral)} neutral ({', '.join(neutral)})")
        if len(agree) > len(conflict):
            read = f"independent evidence mostly reinforces the model's {WORD[self.model]} call"
        elif len(conflict) > len(agree):
            read = f"independent evidence mostly argues against the model's {WORD[self.model]} call, so favor caution"
        else:
            read = f"independent evidence is split on the model's {WORD[self.model]} call"
        return f"**Cross-reference verdict:** of {len(unique)} independent checks, " + "; ".join(parts) + f" - {read}."
