import sys
import traceback
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from agents.company_detection_agent import CompanyDetectionAgent
from orchestrator.freshness_detector import FreshnessDetector
from data.providers.live_market_providers import LiveMarketProvider
from agents.general_response_agent import GeneralResponseAgent
from agents.current_topic_agent import CurrentTopicAgent

company = CompanyDetectionAgent()
freshness = FreshnessDetector()
live = LiveMarketProvider()
general = GeneralResponseAgent()
current = CurrentTopicAgent()

queries = [
    "Tell me the latest about INTC",
    "Tell me about i9 14900KS",
    "Tell me about Steam Deck",
    "What is the Steam Deck",
]

for query in queries:
    print("\n" + "=" * 70)
    print("QUERY:", query)
    print("=" * 70)

    try:
        detection = company.analyze(query)
        print("DETECTION:", detection)
    except Exception as exc:
        print("DETECTION ERROR:", repr(exc))
        traceback.print_exc()
        continue

    try:
        needs_live = freshness.requires_live_data(query)
        print("REQUIRES LIVE:", needs_live)
    except Exception as exc:
        print("FRESHNESS ERROR:", repr(exc))
        traceback.print_exc()
        continue

    is_company = bool(detection.get("is_company_request")) if isinstance(detection, dict) else False

    if not is_company and needs_live:
        try:
            ctx = live.get_context(company={}, query=query)
            print("LIVE AVAILABLE:", ctx.get("available"))
            print("LIVE RESULTS:", len(ctx.get("results", [])))
        except Exception as exc:
            print("LIVE ERROR:", repr(exc))
            traceback.print_exc()
            continue

        try:
            result = current.analyze(message=query, live_context=ctx)
            print("CURRENT RESULT:", result)
        except Exception as exc:
            print("CURRENT AGENT ERROR:", repr(exc))
            traceback.print_exc()

    elif not is_company:
        try:
            result = general.analyze(query)
            print("GENERAL RESULT:", result)
        except Exception as exc:
            print("GENERAL AGENT ERROR:", repr(exc))
            traceback.print_exc()
    else:
        print("COMPANY/SECURITY ROUTE SELECTED")
