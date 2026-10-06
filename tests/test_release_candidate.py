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

    failures = []

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

        print(
            response[:3000]
        )

        if not response.strip():

            failures.append(
                query
            )

    print()

    if failures:

        print(
            "FAILED QUERIES:"
        )

        for failure in failures:

            print(
                failure
            )

        raise RuntimeError(
            "Release Candidate Failed"
        )

    print(
        "RELEASE CANDIDATE PASSED"
    )