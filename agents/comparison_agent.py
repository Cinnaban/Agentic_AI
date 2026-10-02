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
        company_results,
        comparison_plan=None,
        custom_formula=None
    ):

        if not isinstance(
            comparison_plan,
            dict
        ):

            comparison_plan = {}
 
        if not isinstance(
            custom_formula,
            dict
        ):

            custom_formula = {}
 
        dimensions = comparison_plan.get(
            "dimensions",
            []
        )
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

REQUESTED COMPARISON DIMENSIONS:

{json.dumps(
    dimensions,
    indent=2
)}

COMPARISON PLAN:

{json.dumps(
    comparison_plan,
    indent=2
)}

CUSTOM ANALYTICAL FORMULA:

{json.dumps(
    custom_formula,
    indent=2,
    default=str
)}


PRIMARY TASK:

Answer the user's exact question first.

Use Company Evidence to support the answer.

Use the Custom Analytical Formula only as an
additional analytical lens when supplied.

Do not let the formula replace the user's question.

Do not produce a generic company profile when the
user asks a focused comparison question.

The Requested Comparison Dimensions identify the
specific dimensions the user wants compared.

Do not automatically generate a generic full company
report.

If formula opportunity is "helpful":

- Answer using the broader evidence first.
- Present the custom formula as a supporting lens.
- Explain whether the formula supports or conflicts
  with the broader evidence.

If formula opportunity is "central":

- The formula may be a primary analytical framework.
- Still show the underlying evidence.
- Explain why the formula was created.
- Explain how the weights were chosen.
- Explain why the formula is useful.
- Explain important limitations.

If one or more specific dimensions are requested:

- Focus the response on those dimensions.
- Compare every supplied company directly.
- State which company appears strongest for each
  requested dimension when the evidence allows it.
- Explain why using supplied evidence.
- If the evidence does not establish a winner, say so.
- Do not fill missing values with model knowledge.

If "overview" or multiple broad dimensions are
requested:

- Provide a broader side-by-side comparison.
- Still organize the response comparatively rather
  than producing separate standalone company reports.

EVIDENCE RULES:

- Only use evidence supplied in Company Evidence.
- Keep each company's metrics attributed to that
  company.
- Quantitative model results are model-derived
  evidence.
- Public reporting remains attributed to its original
  publisher.
- Do not use model memory as evidence for current
  financial facts.
- Preserve disagreements between supplied signals.

RESPONSE STYLE:

Begin with a direct answer to the user's question.

Then provide supporting comparison details.

Prefer concise side-by-side sections over three long
independent company profiles.

RESPONSE STRUCTURE:

If the user asks about one or a few specific
dimensions:

- Answer those requested dimensions first.
- Do not include unrelated sections merely to fill
  out a standard report format.
- Include a short conclusion answering the exact
  question.

If the user requests a broad comparison:

Use relevant sections such as:

- Comparison Snapshot
- Growth
- Profitability
- Financial Strength
- Valuation
- Momentum
- Risk
- Competitive Position
- Key Trade-offs
- Bottom Line

Only include sections supported by the user's
question and supplied evidence.
CUSTOM FORMULA RULES:

The Custom Analytical Formula is an additional
analytical lens created specifically for this
financial question.

If a custom formula is supplied:

- Explain why the formula was created.
- Explain which supplied metrics were selected.
- Explain why those metrics matter to the user's
  question.
- Explain the weighting rationale.
- Explain what higher or lower scores mean.
- Present the deterministic ranking.
- Discuss whether the formula agrees or disagrees
  with the broader supplied evidence.
- Clearly state the formula's limitations.

Do not describe the custom formula as an industry
standard, academic model, established valuation
method, or investment guarantee.

Do not replace the underlying evidence with the
formula.

The formula supplements the evidence.
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
        