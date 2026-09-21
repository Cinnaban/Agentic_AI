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

from agents.ollama_client import OllamaClient
from configs.config import Config


client = OllamaClient()


result = client.generate(
    """
Return ONLY this JSON:

{
    "approved": true,
    "issues": [],
    "confidence": 95
}
""",
    model=Config.QUALITY_MODEL
)


print()
print("=" * 60)
print("QUALITY MODEL DIRECT TEST")
print("=" * 60)

print(
    "Configured model:",
    Config.QUALITY_MODEL
)

print(
    "Returned model:",
    result.get("model")
)

print(
    "Done:",
    result.get("done")
)

print(
    "Response:",
    repr(
        result.get(
            "response",
            ""
        )
    )
)

print(
    "Thinking length:",
    len(
        result.get(
            "thinking",
            ""
        )
    )
)

print("=" * 60)