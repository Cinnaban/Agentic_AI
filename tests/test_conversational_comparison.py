import sys

from pathlib import Path


ROOT_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)


if str(
    ROOT_DIR
) not in sys.path:

    sys.path.append(
        str(
            ROOT_DIR
        )
    )


from orchestrator.hermes import (
    Hermes
)


hermes = Hermes()


source = (
    "telegram"
)

channel_id = (
    "comparison_chat"
)

user_id = (
    "comparison_user"
)


print()
print("=" * 70)
print("CONVERSATIONAL COMPARISON TEST")
print("=" * 70)


first = (
    hermes.process_request(
        message=(
            "Compare Nvidia, Intel and AMD"
        ),

        source=source,

        channel_id=channel_id,

        user_id=user_id
    )
)


print(
    "FIRST STATUS:",
    first.get(
        "status"
    )
)


second = (
    hermes.process_request(
        message=(
            "Which has the strongest "
            "balance sheet?"
        ),

        source=source,

        channel_id=channel_id,

        user_id=user_id
    )
)


print(
    "SECOND STATUS:",
    second.get(
        "status"
    )
)


print(
    "SECOND APPROVED:",
    second.get(
        "approved"
    )
)


print(
    "SECOND RESPONSE AVAILABLE:",
    bool(
        second.get(
            "response"
        )
    )
)


print()
print(
    second.get(
        "response",
        ""
    )
)


assert (
    second.get(
        "status"
    )
    == "completed"
)


assert second.get(
    "response"
)


key = (
    hermes.conversation_context
    .make_key(
        source=source,

        channel_id=channel_id,

        user_id=user_id
    )
)


state = (
    hermes.conversation_context
    .get(
        key
    )
)


tickers = {
    entity.get(
        "ticker"
    )

    for entity
    in state.get(
        "active_entities",
        []
    )
}


assert tickers >= {
    "NVDA",
    "INTC",
    "AMD"
}


print()
print(
    "CONVERSATIONAL COMPARISON TEST PASSED"
)

print("=" * 70)