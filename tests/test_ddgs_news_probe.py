from ddgs import (
    DDGS
)


print()
print("=" * 60)
print("DDGS NEWS PROBE")
print("=" * 60)


query = (
    "Pokemon latest news"
)


try:

    with DDGS() as ddgs:

        results = list(
            ddgs.news(
                query,
                max_results=5
            )
        )


    print(
        "Results:",
        len(
            results
        )
    )


    for result in results:

        print()
        print(result)


except Exception as exc:

    print(
        "DDGS ERROR:",
        repr(
            exc
        )
    )

    raise


print()
print("=" * 60)