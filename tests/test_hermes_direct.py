import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))


from agents.ollama_client import OllamaClient
from configs.config import Config

client = OllamaClient()

print(
    client.generate(
        "Say HELLO",
        model=Config.HERMES_MODEL
    )
)