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
from agents.ollama_client import (
    OllamaClient
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
	
	lines.append("===== ETF UPDATE SUMMARY =====")
	lines.append(f"Run Date: {results['run_date']}")
	lines.append(f"ETFs Checked: {results['etfs_checked']}")
	lines.append(f"Updates Applied: {results['updates_applied']}")
	lines.append("")

	if results["changes"]:

		lines.append(
			f"Changes Found: {len(results['changes'])}"
		)
		lines.append("")

		for change in results["changes"]:

			lines.append(
				f"{change['ticker']} | "
				f"{change['field']} | "
				f"{change['old']} -> "
				f"{change['new']}"
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
    beta_analysis
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

Objective:

Provide:

1. Portfolio observations
2. Current market-news context
3. Sector observations
4. Notable risks
5. Opportunities
6. Short-term watch items

EVIDENCE RULES:

- Portfolio Update contains spreadsheet/ETF data.

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

# Daily ETF Update

## Portfolio Changes

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
Highest Beta ETFs:
{high_beta}

Lowest Beta ETFs:
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

# Set up change variables
changes = []
pending_updates = []
etf_count = 0
errors = []
beta_values = []
ai_summary = ""

# Result Variables
market_sentiment = (
    "Not independently measured."
)
live_news_backend = (
    PublicTopicNewsBackend(
        max_results=8
    )
)

live_news = (
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
for row_num, row in enumerate(rows[1:], start=2):
	
	row_changed = False

	ticker = row[0].strip()

	if not ticker:
		continue
	
	etf_count += 1

	print(f"Checking {ticker}")

	try: 
		fund = yf.Ticker(ticker)
		info = fund.info
		expense_ratio = info.get("netExpenseRatio")
		dividend_yield = info.get("yield")
		eps = info.get("epsTrailingTwelveMonths")
		TPE = info.get("trailingPE")
		beta = info.get("beta")

		# Format values
		if expense_ratio is not None:
			expense_ratio = f"{expense_ratio :.2f}%"

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
		if current_expense != expense_ratio:
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
		if current_dividend != dividend_yield:
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
		if current_eps != eps:
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
		if current_Tpe != TPE:
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
		if current_beta != beta:
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

if pending_updates:
	worksheet.batch_update(
		pending_updates
	)
	
	print(
		f"\nApplied {len(changes)} batched updates."
	)

results = {
	"run_date": today,
	"etfs_checked": etf_count,
	"updates_applied": len(pending_updates),
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


research_prompt = (
    build_market_research_prompt(
        portfolio_summary=
            summary,

        market_sentiment=
            market_sentiment,

        news_headlines=
            news_headlines,

        beta_analysis=
            beta_analysis
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

print("=" * 60)


ai_summary = ai_summarize(
    research_prompt,
    beta_analysis
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