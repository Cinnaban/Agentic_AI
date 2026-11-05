import json
import re

MARKER = "**Direct Answer**"
MIN_RESPONSE_CHARS = 400
MAX_EVIDENCE_CHARS = 12000

PROMPT = """You are answering a user's question using ONLY the research results below.

Question:
{question}

Research results (tables, quant review, evidence):
{evidence}

Return ONLY a JSON object with this shape:
{{"answer": "...", "leans": [{{"ticker": "XYZ", "sell": 20, "hold": 50, "accumulate": 30}}]}}

Rules for "answer":
- Start with the verdict in one short sentence (for example "Yes", "No", "Mixed", or "Cannot be determined"), then say why.
- Use 3 to 5 short sentences. Cite the specific numbers from the results that drive the verdict.
- If signals conflict or confidence is low, say so plainly and name what would change the answer.
- Do not invent figures that are not in the results. Do not mention portfolio values or account balances.
- Finish with: "Not financial advice."
- Plain text only, no headings, no bullets, no tables.

Rules for "leans":
- Include one entry per analyzed stock or ETF (at most 5) when the research is about holding, buying or selling it. Otherwise return an empty list.
- sell, hold and accumulate are whole-number percentages that sum to exactly 100 and express how the evidence leans.
- Base them on the quantitative recommendation and forecasts, risk level, valuation, momentum and any quality-review limitations in the results.
- Weak, conflicting or missing evidence must move weight toward hold; do not output extreme values (above 80) unless nearly all signals agree.
"""

LEAN_LABELS = (("accumulate", "Accumulate"), ("hold", "Hold"), ("sell", "Sell"))


def normalize_lean(entry):
    """Whole-number percentages summing to 100, or None when the entry is unusable."""
    if not isinstance(entry, dict):
        return None
    values = {}
    for key, _ in LEAN_LABELS:
        value = entry.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            return None
        values[key] = float(value)
    total = sum(values.values())
    if total <= 0:
        return None
    scaled = {k: v * 100 / total for k, v in values.items()}
    floored = {k: int(v) for k, v in scaled.items()}
    leftover = 100 - sum(floored.values())
    for key in sorted(scaled, key=lambda k: scaled[k] - floored[k], reverse=True)[:leftover]:
        floored[key] += 1
    return floored


def format_leans(leans):
    lines = []
    for entry in leans[:5]:
        pct = normalize_lean(entry)
        if not pct:
            continue
        ticker = str(entry.get("ticker") or "").strip().upper()
        body = " | ".join(f"{label} {pct[key]}%" for key, label in LEAN_LABELS)
        lines.append(f"{ticker + ': ' if ticker else ''}{body}")
    if not lines:
        return ""
    return "Evidence lean:\n" + "\n".join(lines)


class DirectAnswerAgent:
    """Reads the question plus the finished research output and states the answer."""

    def __init__(self, client=None, model=None):
        self._client = client
        self._model = model

    @property
    def client(self):
        if self._client is None:
            from agents.ollama_client import OllamaClient
            self._client = OllamaClient()
        return self._client

    @staticmethod
    def applies(question, response):
        text = str(question or "").strip()
        if not text or text.startswith("/"):
            return False
        if not isinstance(response, str) or len(response) < MIN_RESPONSE_CHARS:
            return False
        if MARKER in response:
            return False
        # Research briefings (Summary / Answer / Assessment / Sources) already answer directly.
        if all(re.search(rf"^{h}:", response, re.MULTILINE) for h in ("Summary", "Answer", "Assessment")):
            return False
        return True

    def answer(self, question, response):
        """Returns (answer_text, leans_text)."""
        evidence = re.sub(r"\n{3,}", "\n\n", response)[:MAX_EVIDENCE_CHARS]
        kwargs = {"options": {"temperature": 0.2, "num_predict": 500}}
        if self._model:
            kwargs["model"] = self._model
        out = self.client.generate(
            PROMPT.format(question=str(question).strip(), evidence=evidence), **kwargs
        )
        text = ((out or {}).get("response", "") if isinstance(out, dict) else "").strip()
        data = self._parse_json(text)
        if data is None:
            return (text if len(text) >= 20 and not text.startswith("{") else ""), ""
        answer = str(data.get("answer") or "").strip()
        leans = data.get("leans")
        return (answer if len(answer) >= 20 else ""), format_leans(leans if isinstance(leans, list) else [])

    @staticmethod
    def _parse_json(text):
        try:
            data = json.loads(text)
        except ValueError:
            start, end = text.find("{"), text.rfind("}")
            if start < 0 or end <= start:
                return None
            try:
                data = json.loads(text[start:end + 1])
            except ValueError:
                return None
        return data if isinstance(data, dict) else None

    def apply(self, question, response):
        """Returns the response with the direct answer on top; unchanged if unavailable."""
        if not self.applies(question, response):
            return response
        try:
            answer, leans = self.answer(question, response)
        except Exception as exc:
            print("DIRECT ANSWER FAILED:", repr(exc))
            return response
        if not answer:
            return response
        lean_block = f"\n\n{leans}" if leans else ""
        return f"{MARKER}\n{answer}{lean_block}\n\n{response}"
