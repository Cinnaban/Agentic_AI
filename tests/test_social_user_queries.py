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


TEST_QUERIES = [

    "What are developers saying about local AI models?",

    "What are people discussing about NVIDIA?",

    "What are users saying about AMD GPUs?",

    "What is the public reaction to open source AI?",

    "What are developers saying about Ollama?"
]


if __name__ == "__main__":

    provider = (
        GenericEvidenceProvider()
    )

    agent = (
        GenericEvidenceAgent()
    )

    for query in TEST_QUERIES:

        print()
        print("=" * 80)
        print("QUERY")
        print("=" * 80)
        print(query)

        evidence = (
            provider.get_context(
                query=query
            )
        )

        response = (
            agent.analyze(
                message=query,
                evidence=evidence
            )
        )

        print()
        print("=" * 80)
        print("RESPONSE")
        print("=" * 80)

        print(response)