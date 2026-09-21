# tests/test_hermes_model.py

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from agents.ollama_client import OllamaClient
from configs.config import Config

ollama = OllamaClient()

response = ollama.generate(
    "What company owns the ticker NVDA?",
    model=Config.HERMES_MODEL
)

print(response)