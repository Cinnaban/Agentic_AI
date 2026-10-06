import json
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
from data.providers.generic_evidence_provider import (
    GenericEvidenceProvider
)

from agents.generic_evidence_agent import (
    GenericEvidenceAgent
)


def print_header(title):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


if __name__ == "__main__":

    query = (
        "What are developers saying "
        "about local AI coding tools?"
    )

    print_header(
        "SOCIAL RESEARCH TEST"
    )

    print()
    print(
        "QUERY:"
    )
    print(query)

    provider = (
        GenericEvidenceProvider()
    )

    evidence = (
        provider.get_context(
            query=query
        )
    )

    print_header(
        "SOCIAL SUMMARY"
    )

    print(
        json.dumps(
            evidence.get(
                "social_summary",
                {}
            ),
            indent=2,
            default=str
        )
    )

    print_header(
        "AGENT RESPONSE"
    )

    agent = (
        GenericEvidenceAgent()
    )

    response = (
        agent.analyze(
            message=query,
            evidence=evidence
        )
    )

    print(response)