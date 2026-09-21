import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))
    
from agents.ollama_client import OllamaClient
from configs.config import Config

class ResearchAgent:

    def __init__(self):

        self.ollama = OllamaClient()

    def analyze(
        self,
        company,
        market_context=None
    ):
        if market_context is None:

            market_context = {
                "financial_data": {},
                "news": [],
                "sentiment_sources": [],
                "source_status": {}
            }
        sec_facts = (
            market_context
            .get(
                "sec_facts",
                {}
            )
            .get(
                "facts",
                {}
            )
        )
        
        sec_filings = (
            market_context.get(
                "sec_filings",
                []
            )
        )
        research_sec_filings = []

        for filing in sec_filings:
            if not isinstance(
                filing,
                dict
            ):
                continue
            research_sec_filings.append(
                {
                    "form":
                        filing.get(
                            "form"
                        ),
                    "filing_date":
                        filing.get(
                            "filing_date"
                        ),
                    "source":
                        "SEC"
                }
            )
            
        research_sec_facts = {}
        for name, fact in sec_facts.items():
            if not isinstance(
                fact,
                dict
            ):
                continue

            research_sec_facts[
                name
            ] = {
                "value":
                    fact.get(
                        "value"
                    ),
                "unit":
                    fact.get(
                        "unit"
                    ),
                "filed":
                    fact.get(
                        "filed"
                    ),
                "form":
                    fact.get(
                        "form"
                    ),
                "period_end":
                    fact.get(
                        "period_end"
                    )
            }
            
        research_context = {
            "financial_data":
                market_context.get(
                    "financial_data",
                    {}
                ),

            "sec_facts":
                research_sec_facts,

            "sec_filings":
                research_sec_filings,

            "news":
                market_context.get(
                    "news",
                    []
                ),
            "source_status": {
                "financial_data":
                    market_context
                    .get(
                        "source_status",
                        {}
                    )
                    .get(
                        "financial_data"
                    ),

                "sec_facts":
                    market_context
                    .get(
                        "source_status",
                        {}
                    )
                    .get(
                        "sec_facts"
                    ),

                "sec_filings":
                    market_context
                    .get(
                        "source_status",
                        {}
                    )
                    .get(
                        "sec_filings"
                    ),
                "macro_facts":
                    market_context.get(
                            "macro_facts",
                            {}
                        ),
                "macro":
                    market_context.get(
                        "source_status",
                        {}
                    )
                    .get(
                        "macro"
                    ),
                "news":
                    market_context
                    .get(
                        "source_status",
                        {}
                    )
                    .get(
                        "news"
                    ),

                "sentiment_sources":
                    market_context
                    .get(
                        "source_status",
                        {}
                    )
                    .get(
                        "sentiment_sources"
                    )
            }
        }        
        
        prompt = f"""
You are a professional market research analyst.

Provide:

1. Company Overview
2. Business Model
3. Competitive Position
4. Major Risks
5. Key Strengths

Company:

{company}

Market Context:

{json.dumps(
    research_context,
    indent=2
)}
EVIDENCE HIERARCHY:

SEC Facts
   - Treat SEC facts as authoritative reported company
     financial evidence.
   - These values come from company filings reported
     through the SEC.
   - When SEC facts and model-derived financial ratings
     differ, clearly distinguish the two instead of
     silently choosing one.

SEC Filings
   - SEC filing metadata proves that a filing occurred.
   - Filing metadata does NOT prove what the filing says.
   - Do not claim filing contents unless filing content
     is explicitly supplied.

Macroeconomic Facts
   - Macro Facts contain public FRED economic data and
     deterministic calculations derived from that data.
   - Treat raw observations and derived observations separately.
   - inflation_index is a CPI index level, not an inflation rate.
   - inflation_yoy is the derived year-over-year CPI change.
   - real_gdp is a reported real GDP level.
   - real_gdp_change is a derived period-over-period percentage change.
   - interest_rate_change and unemployment_change are changes
     measured in percentage points.
   - Do not infer a direct company-specific effect from macroeconomic
     data unless supported by other supplied evidence.
     
Financial Data
   - Financial Data contains analytical and model-derived
     market evidence from the quantitative system.
   - Ratings, recommendations, forecasts, and scores
     must be described as quantitative model outputs.
   - Do not describe them as SEC-reported facts,
     analyst opinions, or verified market sentiment.

News
   - Use News only when source_status.news is available.
   - Do not invent current news when News is unavailable.

Sentiment Sources
   - Use these only when
     source_status.sentiment_sources is available.

General model knowledge
   - General knowledge may be used only as background.
   - Never present general model knowledge as current,
     reported, or independently verified evidence.

FINANCIAL INTERPRETATION RULES:
- Do not infer specific balance-sheet conditions from a
  model rating when SEC facts are available.

- Do not infer investor sentiment from valuation,
  momentum, recommendation, market capitalization,
  P/E ratios, or other quantitative fields.

- Do not infer competitive dominance solely from a
  financial score or market capitalization.

- Do not infer operational stability solely from a
  stability rating.

- Clearly distinguish:
  reported financial facts,
  quantitative model assessments,
  and qualitative background context.

- If SEC-reported evidence directly supports a financial
  statement, prefer that evidence and identify it as
  SEC-reported.

MACRO INTERPRETATION RULES:

- Do not describe CPI index levels as inflation percentages.
- Do not describe real GDP levels as GDP growth rates.
- Use inflation_yoy when discussing the supplied inflation rate.
- Use real_gdp_change when discussing supplied GDP change.
- Do not claim that macroeconomic conditions caused a company's
  financial performance unless evidence for that relationship
  is explicitly supplied.
- Clearly identify FRED-derived observations as macroeconomic
  context rather than company-specific evidence.

GROUNDING RULES:
- Use Market Context as the authoritative source for
  current or time-sensitive information.

- If a source_status value is "unavailable", do not claim
  to have current information from that source.

- Do not invent a current date for the research.

- Do not describe historical information as current.

- Do not describe an acquisition, earnings result, market event,
  product release, regulatory event, or analyst opinion as recent
  unless it appears in Market Context.

- If current evidence is unavailable, clearly state that the
  corresponding section is based on general company context
  rather than current verified information.

- Do not create or display a Date of Analysis unless an
  explicit analysis date is supplied in Market Context.

- Observation dates attached to SEC or FRED evidence apply
  only to those individual observations and must not be
  presented as the overall analysis date.
"""
        
        response = self.ollama.generate(
            prompt,
            model=Config.RESEARCH_MODEL,
            options={
                "num_predict":
                    Config.RESEARCH_NUM_PREDICT,
                "num_ctx":
                    Config.RESEARCH_NUM_CTX
            }
        )

        model_response = response.get(
        "response",
            ""
        )

        if not model_response.strip():

            return (
                "Research analysis unavailable: "
                "the research model returned "
                "an empty response."
            )

        return model_response