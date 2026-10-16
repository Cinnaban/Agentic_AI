"""Rule-based explanation of why each quant metric reads bullish/bearish/good/hold."""

POSITIVE = {"bullish", "buy", "strong buy", "excellent", "good", "strong", "high"}
NEGATIVE = {"bearish", "sell", "strong sell", "poor", "weak", "low", "very low"}
HORIZONS = (
    ("forecast_5d", "5-day"),
    ("forecast_30d", "30-day"),
    ("forecast_90d", "90-day"),
    ("forecast_180d", "180-day"),
)


def _value(metrics, key):
    metric = metrics.get(key)
    return metric.get("value") if isinstance(metric, dict) else None


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _tone(value):
    text = str(value).strip().lower()
    if text in POSITIVE:
        return "positive"
    if text in NEGATIVE:
        return "negative"
    return "neutral"


def _sign(value):
    return "positive" if value > 0 else "negative" if value < 0 else "flat"


class QuantSummaryReviewer:

    def build(self, metrics):
        """Return a 'Quant Summary Review' section, or '' when there are no quant metrics."""
        if not isinstance(metrics, dict):
            return ""

        lines = []
        for builder in (
            self._recommendation,
            self._forecast_curve,
            self._forecast_signals,
            self._momentum,
            self._stability,
            self._financial_strength,
            self._conflicts,
        ):
            line = builder(metrics)
            if line:
                lines.append(line)

        if not lines:
            return ""

        return "**Quant Summary Review**\n\n" + "\n".join(f"- {line}" for line in lines)

    def _recommendation(self, metrics):
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
        return text

    def _forecast_curve(self, metrics):
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
        return f"**Forecast horizons:** {shape} - {verdict}"

    def _forecast_signals(self, metrics):
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

    def _momentum(self, metrics):
        rating = _value(metrics, "momentum_rating")
        if rating is None:
            return ""
        tone = _tone(rating)
        meaning = {
            "positive": "price trend and recent returns are strong, a bullish technical input",
            "negative": "price trend and recent returns are weak, a bearish technical input",
            "neutral": "price trend is unremarkable, a neutral technical input",
        }[tone]
        return f"**Momentum {rating}:** {meaning}. Momentum describes the past trend and does not by itself predict future returns."

    def _stability(self, metrics):
        rating = _value(metrics, "stability_rating")
        if rating is None:
            return ""
        tone = _tone(rating)
        meaning = {
            "positive": "price swings and drawdowns have been contained, so a bad outcome is less likely to be sudden",
            "negative": "price swings and drawdowns have been large, which adds risk to any position",
            "neutral": "volatility is average",
        }[tone]
        return f"**Stability {rating}:** {meaning}."

    def _financial_strength(self, metrics):
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
        equity = _number(_value(metrics, "stockholders_equity"))
        if tone == "negative" and equity is not None and equity < 0:
            text += " Negative stockholders' equity (liabilities exceed assets) is a key driver of this score."
        return text

    def _conflicts(self, metrics):
        """Call out when quality ratings and the model's directional call disagree."""
        rec = _value(metrics, "recommendation")
        if rec is None:
            return ""
        rec_tone = _tone(rec)
        if rec_tone == "neutral":
            return ""

        opposing = []
        for key, label in (
            ("momentum_rating", "Momentum"),
            ("stability_rating", "Stability"),
            ("forecast_rating", "Forecast Rating"),
            ("financial_strength_rating", "Financial Strength"),
        ):
            rating = _value(metrics, key)
            if rating is not None and _tone(rating) not in ("neutral", rec_tone):
                opposing.append(f"{label} ({rating})")

        if not opposing:
            return ""
        return (
            f"**Mixed signals:** the model recommendation is {rec}, but {', '.join(opposing)} point the other way. "
            "A split like this usually means waiting for confirmation instead of acting on one input."
        )
