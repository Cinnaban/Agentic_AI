import requests
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from configs.config import Config

class OllamaClient:

    def __init__(self):

        self.endpoint = Config.OLLAMA_GENERATE_ENDPOINT

    def generate(
        self,
        prompt,
        model=Config.HERMES_MODEL,
        options=None
    ):

        if model is None:
            model = Config.HERMES_MODEL

        payload = {
            "model":
                model,

            "prompt":
                prompt,

            "stream":
                False
        }


        if isinstance(
            options,
            dict
        ):

            payload[
                "options"
            ] = options
        
        response = requests.post(
            self.endpoint,
            json=payload
        )

        data = response.json()

        return data

    def health_check(self):

        return True