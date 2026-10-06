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


TEST_QUERIES = [

    "Analyze NVIDIA",

    "Analyze Tesla",

    "Analyze AMD",

    "Compare Microsoft and Apple",

    "What are developers saying about Ollama?",

    "What are users discussing about local AI coding tools?"
]


if __name__ == "__main__":

    hermes = Hermes()

    for query in TEST_QUERIES:

        print()
        print("=" * 80)
        print(query)
        print("=" * 80)

        result = hermes.process_request(
            query
        )

        if isinstance(
            result,
            dict
        ):
            print(
                result.get(
                    "response",
                    result
                )
            )
        else:
            print(result)

        print()
        print("=" * 80)
        print("END RESPONSE")
        print("=" * 80)