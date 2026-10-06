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


from orchestrator.hermes import Hermes


QUERIES = [

    "Analyze NVIDIA",

    "Analyze Tesla",

    "Analyze AMD",

    "Compare Apple and Microsoft",

    "What are developers saying about Ollama?",

    "What are users discussing about local AI coding tools?"
]


if __name__ == "__main__":

    hermes = Hermes()

    for query in QUERIES:

        print()
        print("=" * 80)
        print(query)
        print("=" * 80)

        result = hermes.process_request(
            query
        )

        response = ""

        if isinstance(
            result,
            dict
        ):
            response = (
                result.get(
                    "response",
                    ""
                )
            )

        print(response[:2000])

        assert response

    print()
    print(
        "RELEASE READINESS TEST PASSED"
    )