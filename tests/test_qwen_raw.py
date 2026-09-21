# tests/test_qwen_raw.py

import requests

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "qwen3:30b",
        "prompt": "Say hello",
        "stream": False
    }
)

print(response.status_code)
print(response.text)
