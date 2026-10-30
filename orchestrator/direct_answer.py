import re

MARKER = "**Direct Answer**"
MIN_RESPONSE_CHARS = 400
MAX_EVIDENCE_CHARS = 12000

PROMPT = """You are answering a user's question using ONLY the research results below.

Question:
{question}

Research results (tables, quant review, evidence):
{evidence}

Write the direct answer to the question:
- Start with the verdict in one short sentence (for example "Yes", "No", "Mixed", or "Cannot be determined"), then say why.
- Use 3 to 5 short sentences. Cite the specific numbers from the results that drive the verdict.
- If signals conflict or confidence is low, say so plainly and name what would change the answer.
- Do not invent figures that are not in the results. Do not mention portfolio values or account balances.
- Finish with: "Not financial advice."
- Plain text only, no headings, no bullets, no tables.
"""


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
        return MARKER not in response

    def answer(self, question, response):
        evidence = re.sub(r"\n{3,}", "\n\n", response)[:MAX_EVIDENCE_CHARS]
        kwargs = {"options": {"temperature": 0.2, "num_predict": 350}}
        if self._model:
            kwargs["model"] = self._model
        out = self.client.generate(
            PROMPT.format(question=str(question).strip(), evidence=evidence), **kwargs
        )
        text = (out or {}).get("response", "") if isinstance(out, dict) else ""
        text = text.strip()
        return text if len(text) >= 20 else ""

    def apply(self, question, response):
        """Returns the response with the direct answer on top; unchanged if unavailable."""
        if not self.applies(question, response):
            return response
        try:
            answer = self.answer(question, response)
        except Exception as exc:
            print("DIRECT ANSWER FAILED:", repr(exc))
            return response
        if not answer:
            return response
        return f"{MARKER}\n{answer}\n\n{response}"
