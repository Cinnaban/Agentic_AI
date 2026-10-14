import gspread
import yfinance as yf
import discord
import os
import sys

from pathlib import Path


ROOT_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

if str(ROOT_DIR) not in sys.path:
    sys.path.append(
        str(ROOT_DIR)
    )

from data.providers.live.public_topic_news_backend import (
    PublicTopicNewsBackend
)
from datetime import datetime
from google.oauth2.service_account import Credentials
from configs.config import (
    Config
)
from data.providers.etf_fund_provider import ETFFundProvider
from agents.ollama_client import (
    OllamaClient
)
from workers.etf_portfolio_evaluation import (
    format_change_direction,
    generate_etf_portfolio_appendix
)
from workers.etf_portfolio_insights import (
    build_evidence_based_update_summary,
    find_unapproved_ticker_mentions,
    filter_recent_news,
    format_holding_insights,
    is_complete_portfolio_update,
    parse_asset_rows,
    retrieve_holding_insights
)


GOOGLE_SHEET_NAME = os.getenv(
    "GOOGLE_SHEET_NAME"
)
if not GOOGLE_SHEET_NAME:
    raise RuntimeError(
        "GOOGLE_SHEET_NAME "
        "is not configured"
    )

GOOGLE_ASSET_TAB = os.getenv(
    "GOOGLE_ASSET_TAB"
)
if not GOOGLE_ASSET_TAB:
    raise RuntimeError(
        "GOOGLE_ASSET_TAB "
        "is not configured"
    )

CREDENTIALS_FILE = os.getenv(
    "GOOGLE_CREDENTIALS_FILE"
)
if not CREDENTIALS_FILE:
    raise RuntimeError(
        "GOOGLE_CREDENTIALS_FILE "
        "is not configured"
    )
    
today = datetime.now().strftime("%Y-%m-%d")


# Record Logs
import logging

ETF_LOG_DIRECTORY = (
    ROOT_DIR
    / "logs"
)


ETF_LOG_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True
)


logging.basicConfig(
    filename=(
        ETF_LOG_DIRECTORY
        / f"etf_update_{today}.log"
    ),
    level=logging.INFO
)

logging.info("ETF Update Started")

# Summary Function
def generate_summary(results):
	lines =[]
	
	lines.append("===== MIXED STOCK / ETF UPDATE SUMMARY =====")
	lines.append(f"Run Date: {results['run_date']}")
	lines.append(f"Holdings Checked: {results['holdings_checked']}")
	lines.append(f"Source Worksheet: {results['source_worksheet']}")
	lines.append(
		f"Classified stocks: {results['stock_count']} | "
		f"Classified ETFs: {results['etf_count']} | "
		f"Unresolved: {results['unresolved_count']}"
	)
	lines.append(f"Updates Applied: {results['updates_applied']}")
	if results["skipped_rows"]:
		lines.append(
			f"Skipped invalid ticker cells at worksheet rows: "
			+ ", ".join(
				str(item["row"])
				for item in results["skipped_rows"]
			)
		)
	lines.append("")

	if results["changes"]:

		lines.append(
			f"Changes Found: {len(results['changes'])}"
		)
		lines.append("")

		for change in results["changes"]:
			direction = format_change_direction(
				change.get("field"),
				change.get("old"),
				change.get("new")
			)
			direction_label = (
				f" | {direction}"
				if direction
				else ""
			)

			lines.append(
				f"{change['ticker']} | "
				f"{change['field']} | "
				f"{change['old']} -> "
				f"{change['new']}"
				f"{direction_label}"
			)

	else:
		lines.append(
			"No changes detected."
		)

	if results["errors"]:
		lines.append("")
		lines.append(
			f"Errors: {len(results['errors'])}"
		)

		for error in results["errors"]:
			lines.append(
				f"{error['ticker']}: "
				f"{error['error']}"
		)
	return "\n".join(lines)

# Hermes Analysis Function
def ai_summarize(
    research_prompt,
    beta_analysis
):

    ollama = OllamaClient()


    response = ollama.generate(
        prompt=research_prompt,
        model=Config.HERMES_MODEL
    )


    model_response = response.get(
        "response",
        ""
    )


    if not isinstance(
        model_response,
        str
    ):

        raise RuntimeError(
            "ETF summary model returned "
            "an invalid response"
        )


    model_response = (
        model_response.strip()
    )


    if not model_response:

        raise RuntimeError(
            "ETF summary model returned "
            "an empty response"
        )


    return model_response

# Market Research Prompt
def build_market_research_prompt(
    portfolio_summary,
    market_sentiment,
    news_headlines,
    beta_analysis,
    holding_insights=""
):

    return f"""
{Config.SYSTEM_PROMPT}

Portfolio Update:

{portfolio_summary}

Market Sentiment:

{market_sentiment}

News Headlines:

{news_headlines}

Beta Analysis:

{beta_analysis}

Classified Holding Insights:

{holding_insights or "No per-holding classification or financial insights were retrieved."}

Objective:

Write a concise portfolio brief using the format below. Include a real
evidence-based analysis of the holdings, not just a list of unavailable data.
Summarize actual worksheet changes, meaningful available performance or
quarterly metrics, and timestamp-verified news. Limit each section to a few
focused bullets.

EVIDENCE RULES:

- Classified Holding Insights contains retrieved market and statement data.
- The exact included worksheet ticker list in Classified Holding Insights is
  the complete portfolio. Treat it as a closed set.
- Never add, infer, recommend, or list a stock, ETF, company, or ticker that
  is not in the included worksheet ticker list. This includes securities held
  inside an ETF, market indices, and comparison examples; they are not
  portfolio positions.
- Do not create a separate "Holdings and Classification" inventory. Only
  describe changes and analysis for the included worksheet holdings.
- Stock financial statements describe the issuer; ETF fund profile metrics
  describe the fund. Never treat an ETF's underlying holdings as the fund's
  own issuer financial statements.
- Use only the most recent quarterly period provided, identify its period end,
  and distinguish quarter-over-quarter change from year-over-year growth.
- Compare same-industry stocks only against the explicitly listed
  in-portfolio peer cohort, and identify it as partial rather than an
  industry-wide benchmark. Sector/industry labels alone are not benchmarks.
- The news list contains only ticker-associated stories with a publication
  timestamp verified to be within the preceding 48 hours. Do not call an
  undated story recent.
- Missing metrics are unavailable, not zero. Explain when evidence is
  insufficient to call a holding stable, growing, or strong.
- Do not infer buy/sell recommendations, unsupported causal explanations,
  financial trends from a single quarter, or portfolio-weighted conclusions
  because sheet position sizes are not supplied.

- News Headlines contain recently retrieved
  public reporting.

- Do not describe headlines as independently
  verified financial facts.

- Do not invent current events beyond the
  supplied headlines.

- Do not infer investor sentiment unless
  sentiment evidence was explicitly supplied.

- Beta Analysis is quantitative portfolio context.

Format:

# Daily Portfolio Update

## Portfolio Changes

## Brief Analysis

## Current Market Context

## Risk Watch

## Opportunities

## Short-Term Watch

"""
# Beta Analysis 
def generate_beta_analysis(beta_values):

    if not beta_values:
        return "No beta data available."

    high_beta = sorted(
        beta_values,
        key=lambda x: x["beta"],
        reverse=True
    )[:5]

    low_beta = sorted(
        beta_values,
        key=lambda x: x["beta"]
    )[:5]

    return f"""
Highest Beta Holdings:
{high_beta}

Lowest Beta Holdings:
{low_beta}
"""

# Discord Posting
TOKEN = os.getenv(
    "DISCORD_BOT_TOKEN"
)

CHANNEL_ID = os.getenv(
    "DISCORD_UPDATES_CHANNEL_ID"
)


if not TOKEN:

    raise RuntimeError(
        "DISCORD_BOT_TOKEN "
        "is not configured"
    )


if not CHANNEL_ID:

    raise RuntimeError(
        "DISCORD_UPDATES_CHANNEL_ID "
        "is not configured"
    )


CHANNEL_ID = int(
    CHANNEL_ID
)

discord_client = discord.Client(
	intents=discord.Intents.default()
)

async def post_to_discord(channel, message):

    MAX_LENGTH = 2000

    for i in range(
        0,
        len(message),
        MAX_LENGTH
    ):

        await channel.send(
            message[i:i + MAX_LENGTH]
        )
		
@discord_client.event
async def on_ready():
    try:
        print(
            f"Logged in as {discord_client.user}"
        )
        channel = await discord_client.fetch_channel(
            CHANNEL_ID
        )
        print("Posting summary to Discord...")
        await post_to_discord(
            channel,
            ai_summary
        )
        print("Summary posted successfully.")
        
        
        logging.info(
            "Discord ETF update posted successfully"
        )
    except Exception as e:
        print(
            f"DISCORD ERROR: {e}"
        )
        logging.error(
            f"DISCORD ERROR: {e}"
        )
    finally:
        await discord_client.close()

# Google Authentication
SCOPES = [
 "https://www.googleapis.com/auth/spreadsheets",
 "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file(
 CREDENTIALS_FILE,
 scopes=SCOPES
)

google_client = gspread.authorize(creds)

worksheet = google_client.open(
 GOOGLE_SHEET_NAME
).worksheet(GOOGLE_ASSET_TAB)

# Read all rows
rows = worksheet.get_all_values()
sheet_holdings, skipped_rows = parse_asset_rows(rows)
for skipped_row in skipped_rows:
	logging.warning(
		"Skipping invalid ticker value in worksheet row %s",
		skipped_row["row"]
	)

# Set up change variables
changes = []
pending_updates = []
holdings_checked = len(sheet_holdings)
errors = []
beta_values = []
portfolio_evaluation_holdings = []
holding_insights = []
news_by_ticker = {}
ai_summary = ""
fund_classifier = ETFFundProvider()

# Result Variables
market_sentiment = (
    "Not independently measured."
)
live_news_backend = (
    PublicTopicNewsBackend(
        max_results=8
    )
)

live_news = filter_recent_news(
    live_news_backend.search(
        company=None,
        query=(
            "US stock market ETF "
            "economy latest news"
        )
    )
)


headline_lines = []


for item in live_news[:5]:

    title = item.get(
        "title"
    )

    source = item.get(
        "source"
    )

    published_at = item.get(
        "published_at"
    )
    
    url = item.get(
        "url"
    )

    if not title:
        continue

    headline_lines.append(
        (
            f"- {title}\n"
            f"  Source: {source}\n"
            f"  Date: {published_at}\n"
            f"  URL: {url}"
        )
    )


news_headlines = (
    "\n".join(
        headline_lines
    )
    if headline_lines
    else
    "No current headlines retrieved."
)

# Skip header row
for holding in sheet_holdings:
	
	row_num = holding["row"]
	row = holding["values"]
	row_changed = False

	ticker = holding["ticker"]

	print(f"Checking {ticker}")

	evaluation_record = {
		"ticker": ticker,
		"expense_ratio": None,
		"dividend_yield": None,
			"beta": None,
			"entity_type": "unresolved",
			"classification_status": "unavailable"
	}
	portfolio_evaluation_holdings.append(
		evaluation_record
	)

	try: 
		fund = yf.Ticker(ticker)
		info = fund.info
		classification = fund_classifier.resolve(
			ticker,
			message=""
		)
		entity_type = classification.get("entity_type", "unresolved")
		if entity_type not in {"stock", "etf"}:
			quote_type = str(info.get("quoteType") or "").upper()
			if quote_type == "EQUITY":
				entity_type = "stock"
			elif quote_type == "ETF":
				entity_type = "etf"

		evaluation_record.update({
			"entity_type": entity_type,
			"classification_status": classification.get(
				"classification_status",
				"unavailable"
			),
			"classification_source": classification.get(
				"classification_source",
				"Yahoo Finance quote type"
			),
			"sector": classification.get("sector") or info.get("sector"),
			"industry": classification.get("industry") or info.get("industry")
		})
		insight = retrieve_holding_insights(
			yf_ticker=fund,
			ticker=ticker,
			entity_type=entity_type,
			info=info,
			fund_context=classification.get("etf_context")
		)
		insight["classification_status"] = classification.get(
			"classification_status",
			"unavailable"
		)
		insight["classification_source"] = classification.get(
			"classification_source",
			"Yahoo Finance quote type"
		)
		insight["sector"] = (
			classification.get("sector")
			or insight.get("sector")
		)
		insight["industry"] = (
			classification.get("industry")
			or insight.get("industry")
		)
		holding_insights.append(insight)

		search_name = (
			info.get("shortName")
			or info.get("longName")
			or ticker
		)
		news_by_ticker[ticker] = filter_recent_news(
			live_news_backend.search(
				company={"name": search_name, "ticker": ticker},
				query=f'"{search_name}" {ticker} company stock fund news'
			)
		)

		expense_ratio = (
			info.get("annualReportExpenseRatio")
			if info.get("annualReportExpenseRatio") is not None
			else info.get("netExpenseRatio")
		) if entity_type == "etf" else None
		dividend_yield = (
			info.get("dividendYield")
			if info.get("dividendYield") is not None
			else info.get("yield")
		)
		eps = (
			info.get("trailingEps")
			if info.get("trailingEps") is not None
			else info.get("epsTrailingTwelveMonths")
		) if entity_type == "stock" else None
		TPE = info.get("trailingPE") if entity_type == "stock" else None
		beta = info.get("beta")
		evaluation_record.update({
			"expense_ratio": expense_ratio,
			"dividend_yield": dividend_yield,
			"beta": beta
		})

		# Format values
		if expense_ratio is not None:
			expense_ratio = f"{expense_ratio * 100:.2f}%"

		if dividend_yield is not None:
			dividend_yield = f"{dividend_yield * 100:.2f}%"
		
		if eps is not None:
			eps =f"{eps:.2f}"

		if TPE is not None:
			TPE = f"{TPE:.2f}"

		if beta is not None:
			beta_values.append(
				{
					"ticker": ticker,
					"beta": beta
				}
			)
			
		# Current Expense Ratio, Dividend Rate
		current_expense = row[4]
		current_dividend = row[5]
		current_eps = row[6]
		current_Tpe = row[7]
		current_beta = row[8]

		# Update Expense Ratio (Column 5) 
		if expense_ratio is not None and current_expense != expense_ratio:
			row_changed = True			
	
			changes.append({
				"ticker": ticker,
				"row": row_num,
				"field": "Expense Ratio",
				"old": current_expense,
				"new": expense_ratio
			})

			pending_updates.append({
				"range": f"E{row_num}",
				"values": [[expense_ratio]]
			})
		
		# Update Dividend Rate (Column 6)
		if dividend_yield is not None and current_dividend != dividend_yield:
			row_changed = True
		
			changes.append({
				"ticker": ticker,
				"row": row_num,
				"field": "Dividend Yield",
				"old": current_dividend,
				"new": dividend_yield
			})

			pending_updates.append({
				"range": f"F{row_num}",
				"values": [[dividend_yield]]
			})
		
		# Update Dividend Rate (Column 7)
		if eps is not None and current_eps != eps:
			row_changed = True
		
			changes.append({
				"ticker": ticker,
				"row": row_num,
				"field": "EPS",
				"old": current_eps,
				"new": eps
			})

			pending_updates.append({
				"range": f"G{row_num}",
				"values": [[eps]]
			})

		# Update Dividend Rate (Column 8)
		if TPE is not None and current_Tpe != TPE:
			row_changed = True
		
			changes.append({
				"ticker": ticker,
				"row": row_num,
				"field": "TPE",
				"old": current_Tpe,
				"new": TPE
			})

			pending_updates.append({
				"range": f"H{row_num}",
				"values": [[TPE]]
			})

		# Update Beta (Column 9)
		if beta is not None and current_beta != beta:
			row_changed = True
		
			changes.append({
				"ticker": ticker,
				"row": row_num,
				"field": "beta",
				"old": current_beta,
				"new": beta
			})

			pending_updates.append({
				"range": f"I{row_num}",
				"values": [[beta]]
			})
		# Latest Updated 
		if row_changed:
			pending_updates.append({
				"range": f"K{row_num}",
				"values": [[today]]
			})

		# Last Checked
		pending_updates.append({
			"range": f"J{row_num}",
			"values": [[today]]
		})

	except Exception as e:
		
		errors.append({
			"ticker": ticker,
			"error": str(e)
		})

		print(f"Error with {ticker}: {e}")
		holding_insights.append({
			"ticker": ticker.upper(),
			"entity_type": "unresolved",
			"classification_status": "unavailable",
			"classification_source": "unavailable",
			"name": ticker,
			"sector": None,
			"industry": None,
			"metrics": {},
			"quarterly": {},
			"market_performance_3m_pct": None
		})

if pending_updates:
	worksheet.batch_update(
		pending_updates
	)
	
	print(
		f"\nApplied {len(changes)} batched updates."
	)

results = {
	"run_date": today,
	"holdings_checked": holdings_checked,
	"source_worksheet": GOOGLE_ASSET_TAB,
	"skipped_rows": skipped_rows,
	"stock_count": sum(
		1 for item in holding_insights
		if item.get("entity_type") == "stock"
	),
	"etf_count": sum(
		1 for item in holding_insights
		if item.get("entity_type") == "etf"
	),
	"unresolved_count": sum(
		1 for item in holding_insights
		if item.get("entity_type") == "unresolved"
	),
	"updates_applied": len(pending_updates),
	"holdings_classified": len(holding_insights),
	"changes": changes,
	"errors": errors
}

if not changes:
	print(
		"No ETF changes detected. "
		"Skipping Discord post."
	)

else:
	summary = generate_summary(results)

# Hermes Summary

summary = generate_summary(
    results
)


beta_analysis = generate_beta_analysis(
    beta_values
)

holding_insights_text = format_holding_insights(
    holding_insights,
    news_by_ticker
)
holding_insights_text = (
    f"Source worksheet: {GOOGLE_ASSET_TAB}. "
    f"Valid ticker cells: {holdings_checked}. "
    f"Skipped invalid ticker cells: {len(skipped_rows)}.\n\n"
    + holding_insights_text
)

research_prompt = (
    build_market_research_prompt(
        portfolio_summary=
            summary,

        market_sentiment=
            market_sentiment,

        news_headlines=
            news_headlines,

        beta_analysis=
            beta_analysis,

        holding_insights=
            holding_insights_text
    )
)


print()
print("=" * 60)
print("ETF UPDATE EVIDENCE")
print("=" * 60)

print(
    "Headlines retrieved:",
    len(
        live_news
    )
)

print()

print(
    news_headlines
)

print()
print("PER-HOLDING INSIGHTS")
print(holding_insights_text)
print("=" * 60)


ai_summary = ai_summarize(
    research_prompt,
    beta_analysis
)

unapproved_tickers = find_unapproved_ticker_mentions(
    ai_summary,
    [
        holding.get("ticker")
        for holding in holding_insights
    ],
    [
        holding.get("name")
        for holding in holding_insights
    ]
)
if unapproved_tickers or not is_complete_portfolio_update(ai_summary):
    if unapproved_tickers:
        logging.warning(
            "ETF summary mentioned tickers outside the worksheet portfolio "
            "(%s); replacing it with a worksheet-grounded brief",
            ", ".join(unapproved_tickers)
        )
    else:
        logging.warning(
            "ETF summary omitted the required report sections or a "
            "quantified brief analysis; replacing it with a "
            "worksheet-grounded brief"
        )
    ai_summary = build_evidence_based_update_summary(
        results=results,
        holdings=holding_insights,
        market_headlines=live_news,
        news_by_ticker=news_by_ticker
    )

ai_summary = (
    ai_summary.rstrip()
    + "\n\n"
    + generate_etf_portfolio_appendix(
        portfolio_evaluation_holdings
    )
)


print(
    "Hermes summary complete."
)


# Discord Summary

print(
    "Starting Discord client..."
)

discord_client.run(
    TOKEN
)