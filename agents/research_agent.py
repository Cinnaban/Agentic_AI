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
            
        social_summary = (
            market_context.get(
                "social_summary",
                {}
            )
        )
        if not isinstance( 
                social_summary,
                dict 
            ): 
                social_summary = {}
            
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
            
            "live_market_context":
                market_context.get(
                    "live_market_context",
                    {}
                ),

            "etf_fund_data":
                market_context.get(
                    "etf_fund_data",
                    {}
                ),

            "news":
                market_context.get(
                    "news",
                    []
                ),
                
            "macro_facts":
                market_context.get( 
                    "macro_facts",
                    {} 
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

                "etf_fund_data":
                    market_context
                    .get(
                        "source_status",
                        {}
                    )
                    .get(
                        "etf_fund_data"
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
                
                "live_market_context":
                    market_context
                    .get(
                        "source_status",
                        {}
                    )
                    .get(
                        "live_market_context"
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
                
                "social": 
                    market_context 
                    .get( 
                         "source_status", 
                         {} 
                    ) 
                    .get( 
                         "social"
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
        
        is_etf = (
            isinstance(company, dict)
            and company.get("entity_type") == "etf"
        )
        if is_etf:
            sec_fact_guidance = """
- SEC company facts are not operating-fund financial statements.
- No issuer revenue, earnings, or balance-sheet claim may be
  inferred from an ETF's holdings or from unavailable SEC facts.
- Use only supplied ETF fund profile data for fund-level evidence.
"""
            current_subject = "fund"
            financial_interpretation_guidance = """
- SEC company financial facts are not applicable to this ETF
  evaluation unless explicitly supplied and identified as belonging
  to the fund itself.
- Distinguish fund-level profile and exposure data from the
  operating-company fundamentals of underlying holdings.
"""
            analysis_instructions = """
Provide:

1. Fund Profile and Stated Strategy
2. Portfolio and Sector Exposure
3. Fees and Fund Structure
4. Performance or Risk Characteristics only when supplied
5. Material Risks and Evidence Limitations

Treat this instrument as an ETF, not as an operating company.
Use the supplied fund profile, holdings, asset classes, and
sector weights as fund-level evidence. Do not describe ETF
holdings as the fund issuer's revenue, earnings, or business
segments. Do not infer missing fund characteristics.
"""
        else:
            sec_fact_guidance = """
- Treat SEC facts as authoritative reported company financial evidence.
- These values come from company filings reported through the SEC.
- When SEC facts and model-derived financial ratings differ, clearly
  distinguish the two instead of silently choosing one.
"""
            current_subject = "company"
            financial_interpretation_guidance = """
- If SEC-reported evidence directly supports a financial statement,
  prefer that evidence and identify it as SEC-reported.
"""
            analysis_instructions = """
Provide:

1. Company Overview
2. Business Model
3. Competitive Position
4. Major Risks
5. Key Strengths
6. Social Considerations
"""

        prompt = f"""
You are a professional market research analyst.

{analysis_instructions}

- Discuss only when materially relevant.
- Do not repeat discussion volume.
- Do not repeat discussion platforms.
- Do not repeat discussion themes verbatim.
- Interpret significance instead.

Instrument:

{company}

Market Context:

{json.dumps(
    research_context,
    indent=2
)}

SOCIAL DISCUSSION SUMMARY:

{json.dumps(
    social_summary,
    indent=2,
    default=str
)}
EVIDENCE HIERARCHY:

SEC Facts
{sec_fact_guidance}

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

LIVE MARKET CONTEXT:

- Live Market Context contains recently retrieved
  public web evidence.
- Each result may contain:
  title,
  publication date,
  publisher/source,
  search summary,
  URL,
  and Firecrawl-extracted page content.
- When "content" is present, prefer the supplied
  extracted page content over the shorter search
  result summary.
- The publisher/source remains the evidence source.
- Firecrawl is only the retrieval mechanism and
  must not be described as the publisher.
- Preserve publication dates and publisher
  attribution when discussing current events.
- Public reporting is not automatically an
  independently verified fact.
- When multiple independent supplied sources report
  the same development, you may describe the event
  as supported by multiple supplied sources.
- Do not invent current developments that are not
  represented in the supplied evidence.

CURRENT INFORMATION RULES:

- Do not use general model knowledge as evidence
  for current events.
- Do not invent a current date.
- If the user asks for "current", "today", "latest",
  "recent", "recently", "now", "this week",
  "this month", or another time-sensitive request,
  current-event claims must be grounded in supplied
  timestamped evidence.
- For current {current_subject} developments, prefer supplied
  Live Market Context over model memory.
- {("SEC remains authoritative for supplied company-reported financial facts." if not is_etf else "Do not treat underlying holdings' SEC filings as facts about the ETF itself.")}
- FRED remains authoritative for supplied
  macroeconomic observations.
- Gaming PC quantitative fields remain model-derived
  quantitative evidence.
- Live Market Context represents externally retrieved
  public reporting, except results marked
  "authoritative": true (rank 0), which are real-time broker
  quotes: use them first for current price, change and
  analyst consensus, and prefer them over any scraped price.
  Never report portfolio values.
- Do not use a web article to override an
  SEC-reported financial fact.
- Do not use general web reporting to replace
  supplied FRED macroeconomic observations.
- If current information was requested but
  source_status.live_market_context is unavailable,
  explicitly state that current external verification
  is unavailable.

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

SOCIAL DISCUSSION RULES:

- Social discussion represents public discussion
  and not verified fact.

- Use social discussion to identify:
  - recurring themes
  - public concerns
  - user experiences
  - community reaction

- Do not treat social discussion as:
  - company-reported facts
  - SEC disclosures
  - financial statements
  - verified market data

- If social discussion conflicts with SEC,
  SEC takes precedence.

- Clearly distinguish discussion signals
  from verified evidence.
  
- If source_status.social is unavailable, do not claim to have retrieved social discussion. 
- If social_summary.available is false, omit the Public Discussion Signals section. 
- Prefer social_summary themes and patterns over repeating individual posts. 
- Do not infer public consensus from a small, unrepresentative, or unknown-size sample. 
- If sample posts are supplied, treat them only as examples of retrieved public discussion.
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

{financial_interpretation_guidance}

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

LIVE MARKET RULES:
- Live Market Context contains externally retrieved
  current web/news evidence.
- Use publication dates and source attribution when
  discussing recent or current developments.
- Do not describe general model knowledge as current
  information.
- If the user asks for current, latest, recent, today,
  this week, or similar time-sensitive information,
  current-event claims must be grounded in supplied
  Live Market Context or another supplied timestamped source.
- Retrieved search results represent public reporting.
  They are not automatically independently verified facts.
- When multiple sources describe the same development,
  distinguish corroboration from single-source reporting.
- SEC remains authoritative for supplied company-reported
  financial facts.
- FRED remains authoritative for supplied macroeconomic facts.
- Gaming PC data remains quantitative model evidence.
- Do not replace SEC or FRED evidence with web claims.
- If live data was requested but Live Market Context is
  unavailable, explicitly state that current external
  verification is unavailable.
  
GROUNDING RULES:
- Use Market Context as the authoritative source for
  current or time-sensitive information.

- For current/latest/recent claims, use only live results
  that survived the supplied recency policy.

- Never use the model training cutoff as a substitute
  for a current-information date.

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
            },

            keep_alive=(
                Config.OLLAMA_KEEP_ALIVE_REASONING
            )
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