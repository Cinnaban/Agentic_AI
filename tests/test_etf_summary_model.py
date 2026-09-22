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


from agents.ollama_client import (
    OllamaClient
)

from configs.config import (
    Config
)


ollama = OllamaClient()


response = ollama.generate(
    prompt=(
        "Provide one concise sentence "
        "confirming the ETF update "
        "summary system is working."
    ),

    model=Config.HERMES_MODEL
)


text = response.get(
    "response",
    ""
)


print()
print("=" * 60)
print("ETF SUMMARY MODEL TEST")
print("=" * 60)


print(
    "Response received:",
    bool(
        text
    )
)


assert text


print()
print(
    text
)


print()
print(
    "ETF SUMMARY MODEL TEST PASSED"
)

print("=" * 60)