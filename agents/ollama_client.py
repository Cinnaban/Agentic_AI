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
        options=None,
        keep_alive=None
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
        
        if keep_alive is not None:
            payload[
                "keep_alive"
            ] = keep_alive


        if isinstance(
            options,
            dict
        ):

            payload[
                "options"
            ] = options
        
        try:

            response = requests.post(
                self.endpoint,
                json=payload,
                timeout=Config.OLLAMA_TIMEOUT
            )

            response.raise_for_status()

            data = response.json()

            if not isinstance(
                data,
                dict
            ):
                return {
                    "status": "failed",
                    "error": (
                        "Ollama returned an "
                        "invalid response"
                    )
                }

            return data

        except requests.Timeout:

            return {
                "status": "failed",
                "error": (
                    "Ollama request timed out"
                )
            }

        except requests.RequestException as error:

            return {
                "status": "failed",
                "error": (
                    "Ollama request failed: "
                    f"{error}"
                )
            }

        except ValueError:

            return {
                "status": "failed",
                "error": (
                    "Ollama returned invalid JSON"
                )
            }

    def health_check(self):
        try:
            response = requests.get(
                Config.OLLAMA_HEALTH_ENDPOINT,
                timeout=5
            )

            return response.ok

        except requests.RequestException:
            return False