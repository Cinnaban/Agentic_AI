import json

from agents.ollama_client import (
    OllamaClient
)

from configs.config import (
    Config
)


class ComparisonAgent:

    def __init__(
        self
    ):

        self.ollama = (
            OllamaClient()
        )


    def analyze(
        self,
        message,
        companies,
        company_results
    ):

        prompt = f"""
You are a comparative market research analyst.

USER REQUEST:

{message}

COMPANIES:

{json.dumps(
    companies,
    indent=2
)}

COMPANY EVIDENCE:

{json.dumps(
    company_results,
    indent=2,
    default=str
)}

RULES:

- Compare the companies directly.

- Organize the response around comparison
  dimensions, not separate standalone reports.

- Only compare metrics supplied in the evidence.

- Never invent a missing metric.

- Preserve conflicting quantitative signals.

- Clearly distinguish model-derived quantitative
  evidence from externally reported facts.

- Do not use general model knowledge as evidence
  for current financial facts.

- If current live evidence is present, preserve
  publisher attribution and publication dates.

Provide:

1. Comparison Snapshot
2. Growth
3. Profitability
4. Financial Strength
5. Valuation
6. Momentum
7. Risk
8. Competitive Position
9. Key Trade-offs
10. Bottom Line
"""


        response = (
            self.ollama.generate(
                prompt,
                model=Config.HERMES_MODEL
            )
        )


        text = response.get(
            "response",
            ""
        )


        if not isinstance(
            text,
            str
        ):

            text = ""


        text = text.strip()


        return {
            "status":
                "completed",

            "response":
                text
        }
        